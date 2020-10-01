import collections
import logging
from decimal import BasicContext

import pendulum
from boto3.dynamodb.conditions import Key

from ..enums import UserDatingStatus, UserPrivacyStatus, UserStatus, UserSubscriptionLevel
from ..exceptions import UserAlreadyExists, UserAlreadyGrantedSubscription

logger = logging.getLogger()


class UserDynamo:
    def __init__(self, dynamo_client):
        self.client = dynamo_client

    def pk(self, user_id):
        return {
            'partitionKey': f'user/{user_id}',
            'sortKey': 'profile',
        }

    def parse_pk(self, pk):
        return pk['partitionKey'].split('/')[1]

    def get_user(self, user_id, strongly_consistent=False):
        return self.client.get_item(self.pk(user_id), ConsistentRead=strongly_consistent)

    def get_user_by_username(self, username):
        query_kwargs = {
            'KeyConditionExpression': Key('gsiA1PartitionKey').eq(f'username/{username}'),
            'IndexName': 'GSI-A1',
        }
        return self.client.query_head(query_kwargs)

    def delete_user(self, user_id):
        return self.client.delete_item(self.pk(user_id))

    def add_user(
        self,
        user_id,
        username,
        full_name=None,
        email=None,
        phone=None,
        placeholder_photo_code=None,
        status=None,
        now=None,
    ):
        now = now or pendulum.now('utc')
        assert status is None or status in UserStatus._ALL, f'Invalid user status: `{status}`'
        query_kwargs = {
            'Item': {
                'schemaVersion': 11,
                'partitionKey': f'user/{user_id}',
                'sortKey': 'profile',
                'gsiA1PartitionKey': f'username/{username}',
                'gsiA1SortKey': '-',
                'userId': user_id,
                'username': username,
                'privacyStatus': UserPrivacyStatus.PUBLIC,
                'signedUpAt': now.to_iso8601_string(),
            },
        }
        if full_name:
            query_kwargs['Item']['fullName'] = full_name
        if placeholder_photo_code:
            query_kwargs['Item']['placeholderPhotoCode'] = placeholder_photo_code
        if email:
            query_kwargs['Item']['email'] = email
        if phone:
            query_kwargs['Item']['phoneNumber'] = phone
        if status:
            query_kwargs['Item']['userStatus'] = status
        try:
            return self.client.add_item(query_kwargs)
        except self.client.exceptions.ConditionalCheckFailedException as err:
            raise UserAlreadyExists(user_id) from err

    def update_user_username(self, user_id, username, old_username, now=None):
        now = now or pendulum.now('utc')
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'SET '
            + ', '.join(
                [
                    'username = :un',
                    'usernameLastValue = :oldun',
                    'usernameLastChangedAt = :ulca',
                    'gsiA1PartitionKey = :gsia1pk',
                ]
            ),
            'ExpressionAttributeValues': {
                ':un': username,
                ':oldun': old_username,
                ':ulca': now.to_iso8601_string(),
                ':gsia1pk': f'username/{username}',
            },
            'ConditionExpression': 'username = :oldun',
        }
        return self.client.update_item(query_kwargs)

    def set_user_photo_post_id(self, user_id, photo_id):
        query_kwargs = {
            'Key': self.pk(user_id),
        }

        if photo_id:
            query_kwargs['UpdateExpression'] = 'SET photoPostId = :ppid'
            query_kwargs['ExpressionAttributeValues'] = {':ppid': photo_id}
        else:
            query_kwargs['UpdateExpression'] = 'REMOVE photoPostId'

        return self.client.update_item(query_kwargs)

    def set_user_status(self, user_id, status, now=None):
        assert status in UserStatus._ALL, f'Invalid UserStatus `{status}`'
        now = now or pendulum.now('utc')
        query_kwargs = {
            'Key': self.pk(user_id),
        }
        if status == UserStatus.ACTIVE:  # default value
            query_kwargs['UpdateExpression'] = 'REMOVE userStatus'
        else:
            query_kwargs['UpdateExpression'] = 'SET userStatus = :s'
            query_kwargs['ExpressionAttributeValues'] = {':s': status}
        if status == UserStatus.DISABLED:
            query_kwargs['UpdateExpression'] += ', lastDisabledAt = :lda'
            query_kwargs['ExpressionAttributeValues'][':lda'] = now.to_iso8601_string()
        return self.client.update_item(query_kwargs)

    def set_user_privacy_status(self, user_id, privacy_status):
        assert privacy_status in UserPrivacyStatus._ALL, f'Invalid privacy_status `{privacy_status}`'
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'SET privacyStatus = :ps',
            'ExpressionAttributeValues': {':ps': privacy_status},
        }
        return self.client.update_item(query_kwargs)

    def set_user_age(self, user_id, age):
        assert age is None or int(age) == age, f'Age is not an integer value: `{age}`'
        query_kwargs = {'Key': self.pk(user_id)}
        if age is None:
            query_kwargs['UpdateExpression'] = 'REMOVE age'
        else:
            query_kwargs['UpdateExpression'] = 'SET age = :a'
            query_kwargs['ExpressionAttributeValues'] = {':a': int(age)}
        return self.client.update_item(query_kwargs)

    def set_user_last_found_users_at(self, user_id, now=None):
        now = now or pendulum.now('utc')
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'SET lastFoundUsersAt = :ps',
            'ExpressionAttributeValues': {':ps': now.to_iso8601_string()},
        }
        return self.client.update_item(query_kwargs)

    def set_user_details(
        self,
        user_id,
        full_name=None,
        bio=None,
        language_code=None,
        theme_code=None,
        follow_counts_hidden=None,
        view_counts_hidden=None,
        email=None,
        phone=None,
        comments_disabled=None,
        likes_disabled=None,
        sharing_disabled=None,
        verification_hidden=None,
        date_of_birth=None,
        gender=None,
        location=None,
        match_age_range=None,
        match_genders=None,
        match_location_radius=None,
    ):
        "To ignore an attribute, leave it set to None. To delete an attribute, set it to the empty string."
        expression_actions = collections.defaultdict(list)
        expression_attribute_names = {}
        expression_attribute_values = {}

        def process_attr(name, value):
            if value is not None:
                expression_attribute_names[f'#{name}'] = name
                if value != '':
                    expression_actions['SET'].append(f'#{name} = :{name}')
                    expression_attribute_values[f':{name}'] = value
                else:
                    expression_actions['REMOVE'].append(f'#{name}')

        if location is not None:
            for key in ('latitude', 'longitude'):
                location[key] = BasicContext.create_decimal(location[key]).normalize()

        process_attr('fullName', full_name)
        process_attr('bio', bio)
        process_attr('languageCode', language_code)
        process_attr('themeCode', theme_code)
        process_attr('followCountsHidden', follow_counts_hidden)
        process_attr('viewCountsHidden', view_counts_hidden)
        process_attr('email', email)
        process_attr('phoneNumber', phone)
        process_attr('commentsDisabled', comments_disabled)
        process_attr('likesDisabled', likes_disabled)
        process_attr('sharingDisabled', sharing_disabled)
        process_attr('verificationHidden', verification_hidden)
        process_attr('gender', gender)
        process_attr('location', location)
        process_attr('matchAgeRange', match_age_range)
        process_attr('matchGenders', match_genders)
        process_attr('matchLocationRadius', match_location_radius)

        process_attr('dateOfBirth', date_of_birth)
        if date_of_birth is not None:
            if date_of_birth != '':
                expression_actions['SET'].append('gsiK2PartitionKey = :gsik2pk')
                expression_actions['SET'].append('gsiK2SortKey = :gsik2sk')
                expression_attribute_values[':gsik2pk'] = 'userBirthday/' + date_of_birth[5:]
                expression_attribute_values[':gsik2sk'] = '-'
            else:
                expression_actions['REMOVE'].append('gsiK2PartitionKey')
                expression_actions['REMOVE'].append('gsiK2SortKey')

        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': ' '.join([f'{k} {", ".join(v)}' for k, v in expression_actions.items()]),
        }
        if expression_attribute_names:
            query_kwargs['ExpressionAttributeNames'] = expression_attribute_names
        if expression_attribute_values:
            query_kwargs['ExpressionAttributeValues'] = expression_attribute_values

        return self.client.update_item(query_kwargs)

    def set_user_accepted_eula_version(self, user_id, version):
        query_kwargs = {
            'Key': self.pk(user_id),
        }
        if version is None:
            query_kwargs['UpdateExpression'] = 'REMOVE acceptedEULAVersion'
        else:
            query_kwargs['UpdateExpression'] = 'SET acceptedEULAVersion = :aev'
            query_kwargs['ExpressionAttributeValues'] = {':aev': version}
        return self.client.update_item(query_kwargs)

    def set_last_client(self, user_id, client):
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'SET lastClient = :lc',
            'ExpressionAttributeValues': {':lc': client},
        }
        return self.client.update_item(query_kwargs)

    def set_user_dating_status(self, user_id, status, fail_softly=False):
        query_kwargs = {'Key': self.pk(user_id)}
        if status == UserDatingStatus.DISABLED:
            query_kwargs['UpdateExpression'] = 'REMOVE datingStatus'
        else:
            query_kwargs['UpdateExpression'] = 'SET datingStatus = :ds'
            query_kwargs['ExpressionAttributeValues'] = {':ds': status}
        failure_warning = 'User does not exist' if fail_softly else None
        return self.client.update_item(query_kwargs, failure_warning=failure_warning)

    def update_subscription(self, user_id, level, granted_at=None, expires_at=None):
        assert level != UserSubscriptionLevel.BASIC, "Cannot grant BASIC subscriptions"
        assert (granted_at is None) == (expires_at is None), "Subscriptions expire iff they are granted"
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'SET #sl = :sl',
            'ExpressionAttributeNames': {'#sl': 'subscriptionLevel'},
            'ExpressionAttributeValues': {':sl': level},
        }
        if granted_at is not None:
            query_kwargs['UpdateExpression'] += ', #sga = :sga'
            # each user gets max one subscription grant
            query_kwargs['ConditionExpression'] = 'attribute_not_exists(#sga)'
            query_kwargs['ExpressionAttributeNames'].update({'#sga': 'subscriptionGrantedAt'})
            query_kwargs['ExpressionAttributeValues'].update({':sga': granted_at.to_iso8601_string()})
        if expires_at is not None:
            query_kwargs['UpdateExpression'] += ', #sea = :sea, #gsipk = :gsipk, #gsisk = :sea'
            query_kwargs['ExpressionAttributeNames'].update(
                {
                    '#sea': 'subscriptionExpiresAt',
                    '#gsipk': 'gsiK1PartitionKey',
                    '#gsisk': 'gsiK1SortKey',
                }
            )
            query_kwargs['ExpressionAttributeValues'].update(
                {
                    ':sl': level,
                    ':sea': expires_at.to_iso8601_string(),
                    ':gsipk': f'user/{level}',
                }
            )
        try:
            return self.client.update_item(query_kwargs)
        except self.client.exceptions.ConditionalCheckFailedException as err:
            # this improperly also catches the condition where the user item doesn't exist because
            # there is no way for us to know which conditional check clause failed
            raise UserAlreadyGrantedSubscription(user_id) from err

    def clear_subscription(self, user_id):
        # delete any active subscription, but leave the subscriptionGrantedAt if it exists
        # to record that this user has used up their free subscription bonus
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'REMOVE #sl, #sea, #gsipk, #gsisk',
            'ExpressionAttributeNames': {
                '#sl': 'subscriptionLevel',
                '#sea': 'subscriptionExpiresAt',
                '#gsipk': 'gsiK1PartitionKey',
                '#gsisk': 'gsiK1SortKey',
            },
        }
        return self.client.update_item(query_kwargs)

    def generate_user_ids_by_birthday(self, birthday):
        "`birthday` should be a string in format MM-DD"
        query_kwargs = {
            'KeyConditionExpression': 'gsiK2PartitionKey = :gsipk',
            'ProjectionExpression': 'partitionKey',
            'ExpressionAttributeValues': {':gsipk': f'userBirthday/{birthday}'},
            'IndexName': 'GSI-K2',
        }
        return (key['partitionKey'].split('/')[1] for key in self.client.generate_all_query(query_kwargs))

    def generate_user_ids_by_subscription_level(self, sub_level, max_expires_at=None):
        assert sub_level != UserSubscriptionLevel.BASIC, "Cannot generate for BASIC subscriptions"
        query_kwargs = {
            'KeyConditionExpression': 'gsiK1PartitionKey = :gsipk',
            'ProjectionExpression': 'partitionKey',
            'ExpressionAttributeValues': {':gsipk': f'user/{sub_level}'},
            'IndexName': 'GSI-K1',
        }
        if max_expires_at:
            query_kwargs['KeyConditionExpression'] += ' AND gsiK1SortKey <= :mea'
            query_kwargs['ExpressionAttributeValues'][':mea'] = max_expires_at.to_iso8601_string()
        return (key['partitionKey'].split('/')[1] for key in self.client.generate_all_query(query_kwargs))

    def update_last_post_view_at(self, user_id, now=None, view_type=None):
        now = now or pendulum.now('utc')
        query_kwargs = {
            'Key': self.pk(user_id),
            'UpdateExpression': 'SET lastPostViewAt = :lpva',
            'ConditionExpression': 'NOT lastPostViewAt > :lpva',
            'ExpressionAttributeValues': {':lpva': now.to_iso8601_string()},
        }

        if view_type == 'FOCUS':
            query_kwargs['UpdateExpression'] = 'SET lastPostViewAt = :lpva, lastPostFocusViewAt = :lpva'

        failure_warning = f'Failed to update lastPostViewAt for user `{user_id}`'
        return self.client.update_item(query_kwargs, failure_warning=failure_warning)

    def increment_album_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'albumCount')

    def decrement_album_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'albumCount')

    def increment_card_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'cardCount')

    def decrement_card_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'cardCount')

    def increment_chat_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'chatCount')

    def decrement_chat_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'chatCount')

    def increment_chat_messages_creation_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'chatMessagesCreationCount')

    def increment_chat_messages_deletion_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'chatMessagesDeletionCount')

    def increment_chat_messages_forced_deletion_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'chatMessagesForcedDeletionCount')

    def increment_chats_with_unviewed_messages_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'chatsWithUnviewedMessagesCount')

    def decrement_chats_with_unviewed_messages_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'chatsWithUnviewedMessagesCount')

    def increment_comment_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'commentCount')

    def decrement_comment_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'commentCount')

    def increment_comment_deleted_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'commentDeletedCount')

    def increment_comment_forced_deletion_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'commentForcedDeletionCount')

    def increment_followed_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'followedCount')

    def decrement_followed_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'followedCount')

    def increment_follower_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'followerCount')

    def decrement_follower_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'followerCount')

    def increment_followers_requested_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'followersRequestedCount')

    def decrement_followers_requested_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'followersRequestedCount')

    def increment_post_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'postCount')

    def decrement_post_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'postCount')

    def increment_post_archived_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'postArchivedCount')

    def decrement_post_archived_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'postArchivedCount')

    def increment_post_deleted_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'postDeletedCount')

    def increment_post_forced_archiving_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'postForcedArchivingCount')

    def increment_post_viewed_by_count(self, user_id):
        return self.client.increment_count(self.pk(user_id), 'postViewedByCount')

    def decrement_post_viewed_by_count(self, user_id):
        return self.client.decrement_count(self.pk(user_id), 'postViewedByCount')

    def add_user_deleted(self, user_id, now=None):
        now = now or pendulum.now('utc')
        deleted_at_str = now.to_iso8601_string()
        item = {
            'partitionKey': f'user/{user_id}',
            'sortKey': 'deleted',
            'schemaVersion': 0,
            'userId': user_id,
            'deletedAt': deleted_at_str,
            'gsiA1PartitionKey': 'userDeleted',
            'gsiA1SortKey': deleted_at_str,
        }
        try:
            return self.client.add_item({'Item': item})
        except self.client.exceptions.ConditionalCheckFailedException:
            logger.warning(f'Failed to add UserDeleted subitem for user `{user_id}`: already exists')

    def delete_user_deleted(self, user_id):
        key = {'partitionKey': f'user/{user_id}', 'sortKey': 'deleted'}
        return self.client.delete_item(key)
