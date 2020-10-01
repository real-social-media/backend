import logging
import os
import random
import re
from functools import partialmethod

import pendulum

from app import models
from app.mixins.base import ManagerBase
from app.mixins.trending.manager import TrendingManagerMixin
from app.models.appstore.enums import AppStoreSubscriptionStatus
from app.models.card.templates import ContactJoinedCardTemplate
from app.models.follower.enums import FollowStatus
from app.models.post.enums import PostStatus
from app.utils import GqlNotificationType

from .dynamo import UserContactAttributeDynamo, UserDynamo
from .enums import UserDatingStatus, UserStatus, UserSubscriptionLevel
from .exceptions import UserAlreadyExists, UserException, UserValidationException
from .model import User

logger = logging.getLogger()

S3_PLACEHOLDER_PHOTOS_DIRECTORY = os.environ.get('S3_PLACEHOLDER_PHOTOS_DIRECTORY')


class UserManager(TrendingManagerMixin, ManagerBase):

    client_names = [
        'apple',
        'appsync',
        'cloudfront',
        'cognito',
        'elasticsearch',
        'dynamo',
        'facebook',
        'google',
        'pinpoint',
        'real_dating',
        's3_uploads',
        's3_placeholder_photos',
    ]
    item_type = 'user'

    # username restrictions: same as other social networks
    username_regex = re.compile('[a-zA-Z0-9_.]{3,30}')
    username_tag_regex = re.compile('@' + username_regex.pattern)

    def __init__(self, clients, managers=None, placeholder_photos_directory=S3_PLACEHOLDER_PHOTOS_DIRECTORY):
        super().__init__(clients, managers=managers)
        managers = managers or {}
        managers['user'] = self
        self.album_manager = managers.get('album') or models.AlbumManager(clients, managers=managers)
        self.block_manager = managers.get('block') or models.BlockManager(clients, managers=managers)
        self.card_manager = managers.get('card') or models.CardManager(clients, managers=managers)
        self.chat_manager = managers.get('chat') or models.ChatManager(clients, managers=managers)
        self.comment_manager = managers.get('comment') or models.CommentManager(clients, managers=managers)
        self.follower_manager = managers.get('follower') or models.FollowerManager(clients, managers=managers)
        self.like_manager = managers.get('like') or models.LikeManager(clients, managers=managers)
        self.post_manager = managers.get('post') or models.PostManager(clients, managers=managers)

        self.clients = clients
        for client_name in self.client_names:
            if client_name in clients:
                setattr(self, f'{client_name}_client', clients[client_name])
        if 'dynamo' in clients:
            self.dynamo = UserDynamo(clients['dynamo'])
            self.email_dynamo = UserContactAttributeDynamo(clients['dynamo'], 'userEmail')
            self.phone_number_dynamo = UserContactAttributeDynamo(clients['dynamo'], 'userPhoneNumber')
        self.placeholder_photos_directory = placeholder_photos_directory

    @property
    def real_user_id(self):
        "The userId of the 'real' user, if they exist"
        if not hasattr(self, '_real_user_id'):
            real_user = self.get_user_by_username('real')
            self._real_user_id = real_user.id if real_user else None
        return self._real_user_id

    def get_user(self, user_id, strongly_consistent=False):
        user_item = self.dynamo.get_user(user_id, strongly_consistent=strongly_consistent)
        return self.init_user(user_item) if user_item else None

    def get_user_by_username(self, username):
        user_item = self.dynamo.get_user_by_username(username)
        return self.init_user(user_item) if user_item else None

    def init_user(self, user_item):
        kwargs = {
            'dynamo': getattr(self, 'dynamo', None),
            'trending_dynamo': getattr(self, 'trending_dynamo', None),
            'album_manager': getattr(self, 'album_manager', None),
            'block_manager': getattr(self, 'block_manager', None),
            'chat_manager': getattr(self, 'chat_manager', None),
            'comment_manager': getattr(self, 'comment_manager', None),
            'follower_manager': getattr(self, 'follower_manager', None),
            'like_manager': getattr(self, 'like_manager', None),
            'post_manager': getattr(self, 'post_manager', None),
            'user_manager': self,
        }
        return User(user_item, self.clients, **kwargs) if user_item else None

    def get_available_placeholder_photo_codes(self):
        # don't want to foce the test suite to always pass in this parameter
        if not self.placeholder_photos_directory:
            return []
        paths = self.s3_placeholder_photos_client.list_common_prefixes(self.placeholder_photos_directory + '/')
        return [path.split('/')[-2] for path in paths]

    def get_random_placeholder_photo_code(self):
        codes = self.get_available_placeholder_photo_codes()
        return random.choice(codes) if codes else None

    def generate_username(self):
        # using the crockford base 32 character set'
        chars = '0123456789abcdefghjkmnpqrstvwxyz'
        return ''.join(random.choice(chars) for _ in range(12))

    def validate_username(self, username):
        if not username:
            raise UserValidationException('Empty username')
        matched_username = self.username_regex.match(username)  # matches only from beginging of string
        if not matched_username or matched_username[0] != username:
            raise UserValidationException(f'Username `{username}` does not validate')

    def create_anonymous_user(self, user_id):
        username = self.generate_username()
        try:
            self.validate_username(username)
        except UserValidationException as err:
            raise Exception(f'Auto-generated username `{username}` failed vaildation: {err}') from err

        # set the user up in cognito, claims the username at the same time
        try:
            self.cognito_client.create_user_pool_entry(user_id, username)
        except (
            # Note: Cognito raises UsernameExistsException for more than just usernames.
            self.cognito_client.user_pool_client.exceptions.UsernameExistsException,
            self.cognito_client.user_pool_client.exceptions.AliasExistsException,
        ) as err:
            # Not ideal: relying on cognito not to change these exact error messages.
            if 'Already found an entry for the provided username' in str(err):
                raise UserValidationException(f'Username `{username}` already taken') from err
            if 'User account already exists' in str(err):
                raise UserValidationException(f'An account for userId `{user_id}` already exists') from err
            raise UserValidationException(str(err)) from err

        tokens = self.cognito_client.get_user_pool_tokens(user_id)
        try:
            self.cognito_client.link_identity_pool_entries(user_id, cognito_token=tokens['IdToken'])
        except Exception as err:
            # try to clean up: remove the user from cognito
            self.cognito_client.delete_user_pool_entry(user_id)
            raise UserException(f'Failed to link identity pool entries: {err}') from err

        # create new user in the DB, have them follow the real user if they exist
        photo_code = self.get_random_placeholder_photo_code()
        item = self.dynamo.add_user(
            user_id, username, placeholder_photo_code=photo_code, status=UserStatus.ANONYMOUS
        )
        user = self.init_user(item)
        self.follow_real_user(user)
        return user, tokens

    def create_cognito_only_user(self, user_id, username, full_name=None):
        # try to claim the new username, will raise an validation exception if already taken
        self.validate_username(username)
        full_name = None if full_name == '' else full_name  # treat empty string like null

        try:
            attrs = self.cognito_client.get_user_attributes(user_id)
        except self.cognito_client.user_pool_client.exceptions.UserNotFoundException as err:
            raise UserValidationException(
                f'No entry found in cognito user pool with cognito username `{user_id}`'
            ) from err
        preferred_username = attrs.get('preferred_username', None)
        email = attrs.get('email') if attrs.get('email_verified', 'false') == 'true' else None
        phone = attrs.get('phone_number') if attrs.get('phone_number_verified', 'false') == 'true' else None
        if not email and not phone:
            raise UserValidationException(f'User `{user_id}` has neither verified email nor phone')

        # set the lowercased version of username in cognito
        # this is part of allowing case-insensitive logins
        try:
            self.cognito_client.set_user_attributes(user_id, {'preferred_username': username.lower()})
        except self.cognito_client.user_pool_client.exceptions.AliasExistsException as err:
            raise UserValidationException(
                f'Username `{username}` already taken (case-insensitive comparison)'
            ) from err

        # create new user in the DB, have them follow the real user if they exist
        photo_code = self.get_random_placeholder_photo_code()
        try:
            item = self.dynamo.add_user(
                user_id,
                username,
                full_name=full_name,
                email=email,
                phone=phone,
                placeholder_photo_code=photo_code,
            )
        except UserAlreadyExists:
            # un-claim the username in cognito
            if preferred_username:
                self.cognito_client.set_user_attributes(user_id, {'preferred_username': preferred_username})
            else:
                self.cognito_client.clear_user_attribute(user_id, 'preferred_username')
            raise

        user = self.init_user(item)
        self.follow_real_user(user)
        return user

    def create_federated_user(self, provider, user_id, username, token, full_name=None):
        assert provider in ('apple', 'facebook', 'google'), f'Unrecognized identity provider `{provider}`'
        provider_client = self.clients[provider]

        # do operations that do not alter state first
        self.validate_username(username)
        full_name = None if full_name == '' else full_name  # treat empty string like null

        try:
            email = provider_client.get_verified_email(token).lower()
        except ValueError as err:
            logger.warning(str(err))
            raise UserValidationException(str(err)) from err

        # set the user up in cognito, claims the username at the same time
        try:
            self.cognito_client.create_user_pool_entry(user_id, username, verified_email=email)
        except (
            # Note: Cognito raises UsernameExistsException for more than just usernames.
            self.cognito_client.user_pool_client.exceptions.UsernameExistsException,
            self.cognito_client.user_pool_client.exceptions.AliasExistsException,
        ) as err:
            # Not ideal: relying on cognito not to change these exact error messages.
            if 'Already found an entry for the provided username' in str(err):
                raise UserValidationException(f'Username `{username}` already taken') from err
            if 'An account with the email already exists' in str(err):
                raise UserValidationException(f'Email `{email}` already taken') from err
            if 'User account already exists' in str(err):
                raise UserValidationException(f'An account for userId `{user_id}` already exists') from err
            raise UserValidationException(str(err)) from err

        tokens = {
            'cognito_token': self.cognito_client.get_user_pool_tokens(user_id)['IdToken'],
            provider + '_token': token,
        }
        try:
            self.cognito_client.link_identity_pool_entries(user_id, **tokens)
        except Exception as err:
            # try to clean up: remove the user from cognito
            self.cognito_client.delete_user_pool_entry(user_id)
            raise UserException(f'Failed to link identity pool entries: {err}') from err

        # create new user in the DB, have them follow the real user if they exist
        photo_code = self.get_random_placeholder_photo_code()
        item = self.dynamo.add_user(
            user_id, username, full_name=full_name, email=email, placeholder_photo_code=photo_code
        )
        user = self.init_user(item)
        self.follow_real_user(user)
        return user

    def follow_real_user(self, user):
        real_user = self.get_user_by_username('real')
        if real_user and real_user.id != user.id:
            self.follower_manager.request_to_follow(user, real_user)

    def get_text_tags(self, text):
        """
        Given a fragment of text, return a list of objects of form
            {'tag': '@username', 'userId': '...'}
        representing all the users tagged in the text.
        """
        username_tags = set(re.findall(self.username_tag_regex, text))
        # note that dynamo does not support batch gets using GSI's, and the username is in a GSI
        text_tags = []
        for tag in username_tags:
            user_item = self.dynamo.get_user_by_username(tag[1:])
            if user_item:
                text_tags.append({'tag': tag, 'userId': user_item['userId']})
        return text_tags

    def clear_expired_subscriptions(self, now=None):
        "Clear expired subscriptions. Return a count of how many were cleared"
        now = now or pendulum.now('utc')
        count = 0
        for sub_level in UserSubscriptionLevel._PAID:
            for user_id in self.dynamo.generate_user_ids_by_subscription_level(sub_level, max_expires_at=now):
                self.dynamo.clear_subscription(user_id)
                count += 1
        return count

    def fire_gql_subscription_chats_with_unviewed_messages_count(self, user_id, new_item, old_item=None):
        self.appsync_client.fire_notification(
            user_id,
            GqlNotificationType.USER_CHATS_WITH_UNVIEWED_MESSAGES_COUNT_CHANGED,
            userChatsWithUnviewedMessagesCount=int(new_item.get('chatsWithUnviewedMessagesCount', 0)),
        )

    def on_comment_add(self, comment_id, new_item):
        self.dynamo.increment_comment_count(new_item['userId'])

    def on_comment_delete(self, comment_id, old_item):
        user_id = old_item['userId']
        self.dynamo.decrement_comment_count(user_id)
        self.dynamo.increment_comment_deleted_count(user_id)

    def on_card_add_increment_count(self, card_id, new_item):
        card = self.card_manager.init_card(new_item)
        self.dynamo.increment_card_count(card.user_id)

    def on_card_delete_decrement_count(self, card_id, old_item):
        card = self.card_manager.init_card(old_item)
        self.dynamo.decrement_card_count(card.user_id)

    def on_user_add_delete_user_deleted_subitem(self, user_id, new_item):
        # the integration test suite reuses deleted users as a performance enhancement
        self.dynamo.delete_user_deleted(user_id)

    def on_user_delete(self, user_id, old_item):
        "Delete various user-related objects/items"
        self.dynamo.add_user_deleted(user_id)
        self.elasticsearch_client.delete_user(user_id)
        self.pinpoint_client.delete_user_endpoints(user_id)
        self.real_dating_client.remove_user(user_id, fail_soft=True)

        user = self.init_user(old_item)
        user.clear_photo_s3_objects()
        user.trending_delete()

    def on_criteria_sync_user_status(self, check_method_name, forced_by, user_id, new_item, old_item=None):
        user = self.init_user(new_item)
        if getattr(user, check_method_name)():
            user.disable(forced_by=forced_by)

    on_user_chat_message_forced_deletion_sync_user_status = partialmethod(
        on_criteria_sync_user_status, 'is_forced_disabling_criteria_met_by_chat_messages', 'chatMessages'
    )
    on_user_comment_forced_deletion_sync_user_status = partialmethod(
        on_criteria_sync_user_status, 'is_forced_disabling_criteria_met_by_comments', 'comments'
    )
    on_user_post_forced_archiving_sync_user_status = partialmethod(
        on_criteria_sync_user_status, 'is_forced_disabling_criteria_met_by_posts', 'posts'
    )

    def sync_elasticsearch(self, user_id, new_item, old_item=None):
        self.elasticsearch_client.put_user(user_id, new_item['username'], new_item.get('fullName'))

    def sync_pinpoint_attribute(self, dynamo_name, pinpoint_name, user_id, new_item, old_item=None):
        value = new_item.get(dynamo_name)
        if value is not None:
            self.pinpoint_client.update_user_endpoint(user_id, pinpoint_name, value)
        else:
            self.pinpoint_client.delete_user_endpoint(user_id, pinpoint_name)

    sync_pinpoint_email = partialmethod(sync_pinpoint_attribute, 'email', 'EMAIL')
    sync_pinpoint_phone = partialmethod(sync_pinpoint_attribute, 'phoneNumber', 'SMS')

    def sync_pinpoint_user_status(self, user_id, new_item, old_item=None):
        status = new_item.get('userStatus', UserStatus.ACTIVE)
        if status == UserStatus.ACTIVE:
            self.pinpoint_client.enable_user_endpoints(user_id)
        if status == UserStatus.DISABLED:
            self.pinpoint_client.disable_user_endpoints(user_id)
        if status == UserStatus.DELETING:
            self.pinpoint_client.delete_user_endpoints(user_id)

    def sync_chats_with_unviewed_messages_count(self, chat_id, new_item=None, old_item=None):
        "Sync User.chatsWithUnviewedMessagesCount to changes to chat member items"
        # digging kinda deep into the chat member object from here... should probably make a ChatMember class
        user_id = (new_item or old_item)['sortKey'].split('/')[1]
        new_count = (new_item or {}).get('messagesUnviewedCount', 0)
        old_count = (old_item or {}).get('messagesUnviewedCount', 0)
        if old_count == 0 and new_count > 0:
            self.dynamo.increment_chats_with_unviewed_messages_count(user_id)
        if old_count > 0 and new_count == 0:
            self.dynamo.decrement_chats_with_unviewed_messages_count(user_id)

    def sync_follow_counts_due_to_follow_status(self, followed_user_id, new_item=None, old_item=None):
        follower_user_id = (new_item or old_item)['sortKey'].split('/')[1]
        old_status = (old_item or {}).get('followStatus', FollowStatus.NOT_FOLLOWING)
        new_status = (new_item or {}).get('followStatus', FollowStatus.NOT_FOLLOWING)

        # incr/decr followedCount and followerCount if follow status changed to/from FOLLOWING
        if old_status != FollowStatus.FOLLOWING and new_status == FollowStatus.FOLLOWING:
            self.dynamo.increment_followed_count(follower_user_id)
            self.dynamo.increment_follower_count(followed_user_id)
        if old_status == FollowStatus.FOLLOWING and new_status != FollowStatus.FOLLOWING:
            self.dynamo.decrement_followed_count(follower_user_id)
            self.dynamo.decrement_follower_count(followed_user_id)

        # incr/decr followersRequestedCount if follow status changed to/from REQUESTED
        if old_status != FollowStatus.REQUESTED and new_status == FollowStatus.REQUESTED:
            self.dynamo.increment_followers_requested_count(followed_user_id)
        if old_status == FollowStatus.REQUESTED and new_status != FollowStatus.REQUESTED:
            self.dynamo.decrement_followers_requested_count(followed_user_id)

    def sync_chat_message_creation_count(self, message_id, new_item):
        if user_id := new_item.get('userId'):
            self.dynamo.increment_chat_messages_creation_count(user_id)

    def sync_chat_message_deletion_count(self, message_id, old_item):
        if user_id := old_item.get('userId'):
            self.dynamo.increment_chat_messages_deletion_count(user_id)

    def on_chat_member_add_update_chat_count(self, chat_id, new_item):
        user_id = new_item['sortKey'].split('/')[1]
        self.dynamo.increment_chat_count(user_id)

    def on_chat_member_delete_update_chat_count(self, chat_id, old_item):
        user_id = old_item['sortKey'].split('/')[1]
        self.dynamo.decrement_chat_count(user_id)

    def on_album_add_update_album_count(self, album_id, new_item):
        user_id = new_item['ownedByUserId']
        self.dynamo.increment_album_count(user_id)

    def on_album_delete_update_album_count(self, album_id, old_item):
        user_id = old_item['ownedByUserId']
        self.dynamo.decrement_album_count(user_id)

    def on_post_status_change_sync_counts(self, post_id, new_item, old_item):
        user_id = new_item['postedByUserId']

        new_status = new_item['postStatus']
        if new_status == PostStatus.ARCHIVED:
            self.dynamo.increment_post_archived_count(user_id)
        if new_status == PostStatus.COMPLETED:
            self.dynamo.increment_post_count(user_id)
        if new_status == PostStatus.DELETING:
            self.dynamo.increment_post_deleted_count(user_id)

        old_status = old_item['postStatus']
        if old_status == PostStatus.ARCHIVED:
            self.dynamo.decrement_post_archived_count(user_id)
        if old_status == PostStatus.COMPLETED:
            self.dynamo.decrement_post_count(user_id)

    def on_user_contact_attribute_change_update_subitem(
        self, attr_name, dynamo_lib_name, user_id, new_item=None, old_item=None
    ):
        dynamo_lib = getattr(self, dynamo_lib_name)
        if new_value := (new_item or {}).get(attr_name):
            dynamo_lib.add(new_value, user_id)
        if old_value := (old_item or {}).get(attr_name):
            dynamo_lib.delete(old_value, user_id)

    on_user_email_change_update_subitem = partialmethod(
        on_user_contact_attribute_change_update_subitem, 'email', 'email_dynamo'
    )
    on_user_phone_number_change_update_subitem = partialmethod(
        on_user_contact_attribute_change_update_subitem, 'phoneNumber', 'phone_number_dynamo'
    )

    def on_user_date_of_birth_change_update_age(self, user_id, new_item, old_item=None):
        self.init_user(new_item).update_age()

    def on_user_change_update_dating(self, user_id, new_item, old_item=None):
        old_status = (old_item or {}).get('datingStatus', UserDatingStatus.DISABLED)
        new_status = new_item.get('datingStatus', UserDatingStatus.DISABLED)

        if new_status == UserDatingStatus.DISABLED and old_status == UserDatingStatus.ENABLED:
            self.real_dating_client.remove_user(user_id)

        if new_status == UserDatingStatus.ENABLED:
            user = self.init_user(new_item)

            # if the user profile no longer has all the attributes required for dating, auto-disable dating
            try:
                user.validate_can_enable_dating()
            except UserException:
                self.dynamo.set_user_dating_status(user_id, UserDatingStatus.DISABLED, fail_softly=True)
                return

            new_profile = user.generate_dating_profile()
            old_profile = self.init_user(old_item).generate_dating_profile()
            if old_status == UserDatingStatus.DISABLED or new_profile != old_profile:
                self.real_dating_client.put_user(user_id, new_profile)

    def update_ages(self, now=None):
        now = now or pendulum.now('utc')
        birthday = now.format('MM-DD')
        total, updated = 0, 0
        for user_id in self.dynamo.generate_user_ids_by_birthday(birthday):
            user_updated = self.get_user(user_id).update_age(now=now)
            updated += 1 if user_updated else 0
            total += 1
        return total, updated

    def on_user_delete_delete_cognito(self, user_id, old_item):
        old_status = old_item.get('userStatus', UserStatus.ACTIVE)
        # for resets (used by the integration test suite) we leave the user in cognito
        # as a performance enhancement.
        if old_status != UserStatus.RESETTING:
            try:
                self.cognito_client.delete_user_pool_entry(user_id)
            except self.cognito_client.user_pool_client.exceptions.UserNotFoundException:
                logger.warning(f'No cognito user pool entry found when deleting user `{user_id}`')
            # TODO: catch 404 error & log warning
            self.cognito_client.delete_identity_pool_entry(user_id)

    def find_users(self, caller_user, emails=None, phones=None):
        """
        Given a list of emails and a list of phones, return a list of user_ids of users
        in our system with those emails and phones.
        For each returned user_id that is not already following the user that called this
        method, create a card inviting them to follow.
        """
        emails = emails or []
        phones = phones or []

        user_ids_from_emails = self.email_dynamo.batch_get_user_ids(emails)
        user_ids_from_phones = self.phone_number_dynamo.batch_get_user_ids(phones)
        user_ids = list(set(user_ids_from_emails + user_ids_from_phones))  # uniquify

        for user_id in user_ids:
            follow_status = self.follower_manager.get_follow_status(user_id, caller_user.id)
            if follow_status == FollowStatus.NOT_FOLLOWING:
                card_template = ContactJoinedCardTemplate(user_id, caller_user.id, caller_user.username)
                self.card_manager.add_or_update_card(card_template)

        return user_ids

    def on_appstore_sub_status_change_update_subscription(self, original_transaction_id, new_item, old_item=None):
        if new_item['status'] == AppStoreSubscriptionStatus.ACTIVE:
            self.dynamo.update_subscription(new_item['userId'], UserSubscriptionLevel.DIAMOND)
        else:
            self.dynamo.clear_subscription(new_item['userId'])
