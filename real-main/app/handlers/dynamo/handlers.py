import logging
import os

from boto3.dynamodb.types import TypeDeserializer

from app import clients, models
from app.handlers import xray
from app.logging import LogLevelContext, handler_logging
from app.models.follower.enums import FollowStatus
from app.models.user.enums import UserStatus, UserSubscriptionLevel

from .dispatch import DynamoDispatch

DYNAMO_FEED_TABLE = os.environ.get('DYNAMO_FEED_TABLE')
S3_UPLOADS_BUCKET = os.environ.get('S3_UPLOADS_BUCKET')

logger = logging.getLogger()
xray.patch_all()

secrets_manager_client = clients.SecretsManagerClient()
clients = {
    'appstore': clients.AppStoreClient(secrets_manager_client.get_apple_appstore_params),
    'appsync': clients.AppSyncClient(),
    'cognito': clients.CognitoClient(),
    'dynamo': clients.DynamoClient(),
    'dynamo_feed': clients.DynamoClient(table_name=DYNAMO_FEED_TABLE),
    'elasticsearch': clients.ElasticSearchClient(),
    'pinpoint': clients.PinpointClient(),
    'real_dating': clients.RealDatingClient(),
    's3_uploads': clients.S3Client(S3_UPLOADS_BUCKET),
}

managers = {}
album_manager = managers.get('album') or models.AlbumManager(clients, managers=managers)
appstore_manager = managers.get('appstore') or models.AppStoreManager(clients, managers=managers)
block_manager = managers.get('block') or models.BlockManager(clients, managers=managers)
card_manager = managers.get('card') or models.CardManager(clients, managers=managers)
chat_manager = managers.get('chat') or models.ChatManager(clients, managers=managers)
chat_message_manager = managers.get('chat_message') or models.ChatMessageManager(clients, managers=managers)
comment_manager = managers.get('comment') or models.CommentManager(clients, managers=managers)
feed_manager = managers.get('feed') or models.FeedManager(clients, managers=managers)
follower_manager = managers.get('follower') or models.FollowerManager(clients, managers=managers)
like_manager = managers.get('like') or models.LikeManager(clients, managers=managers)
post_manager = managers.get('post') or models.PostManager(clients, managers=managers)
screen_manager = managers.get('screen') or models.ScreenManager(clients, managers=managers)
user_manager = managers.get('user') or models.UserManager(clients, managers=managers)

# https://stackoverflow.com/a/46738251
deserialize = TypeDeserializer().deserialize

dispatch = DynamoDispatch()
register = dispatch.register

register('album', '-', ['INSERT'], user_manager.on_album_add_update_album_count)
register('album', '-', ['INSERT', 'MODIFY'], album_manager.on_album_add_edit_sync_delete_at)
register(
    'album',
    '-',
    ['INSERT', 'MODIFY'],
    album_manager.on_album_posts_last_updated_at_change_update_art_if_needed,
    {'postsLastUpdatedAt': None},
)
register('album', '-', ['REMOVE'], album_manager.on_album_delete_delete_album_art)
register('album', '-', ['REMOVE'], post_manager.on_album_delete_remove_posts)
register('album', '-', ['REMOVE'], user_manager.on_album_delete_update_album_count)
register(
    'appStoreSub',
    '-',
    ['INSERT', 'MODIFY'],
    user_manager.on_appstore_sub_status_change_update_subscription,
    {'status': None},
)
register('card', '-', ['INSERT'], card_manager.on_card_add)
register('card', '-', ['INSERT'], user_manager.on_card_add_increment_count)
register('card', '-', ['MODIFY'], card_manager.on_card_edit)
register('card', '-', ['REMOVE'], card_manager.on_card_delete)
register('card', '-', ['REMOVE'], user_manager.on_card_delete_decrement_count)
register('chat', '-', ['REMOVE'], chat_manager.on_chat_delete_delete_memberships)
register('chat', '-', ['REMOVE'], chat_manager.on_item_delete_delete_flags)
register('chat', '-', ['REMOVE'], chat_manager.on_item_delete_delete_views)
register('chat', '-', ['REMOVE'], chat_message_manager.on_chat_delete_delete_messages)
register('chat', 'flag', ['INSERT'], chat_manager.on_flag_add)
register('chat', 'flag', ['REMOVE'], chat_manager.on_flag_delete)
register('chat', 'member', ['INSERT'], user_manager.on_chat_member_add_update_chat_count)
register(
    'chat',
    'member',
    ['INSERT', 'MODIFY', 'REMOVE'],
    user_manager.sync_chats_with_unviewed_messages_count,
    {'messagesUnviewedCount': 0},
)
register('chat', 'member', ['REMOVE'], user_manager.on_chat_member_delete_update_chat_count)
register('chat', 'view', ['INSERT', 'MODIFY'], chat_manager.sync_member_messages_unviewed_count, {'viewCount': 0})
register('chatMessage', '-', ['INSERT'], chat_manager.on_chat_message_add)
register('chatMessage', '-', ['INSERT'], user_manager.sync_chat_message_creation_count)
register('chatMessage', '-', ['REMOVE'], chat_manager.on_chat_message_delete)
register('chatMessage', '-', ['REMOVE'], chat_message_manager.on_item_delete_delete_flags)
register('chatMessage', '-', ['REMOVE'], user_manager.sync_chat_message_deletion_count)
register('chatMessage', 'flag', ['INSERT'], chat_message_manager.on_flag_add)
register('chatMessage', 'flag', ['REMOVE'], chat_message_manager.on_flag_delete)
register('comment', '-', ['INSERT'], post_manager.on_comment_add)
register('comment', '-', ['INSERT'], user_manager.on_comment_add)
register(
    'comment',
    '-',
    ['INSERT', 'MODIFY'],
    card_manager.on_comment_text_tags_change_update_card,
    {'textTags': []},
)
register('comment', '-', ['REMOVE'], card_manager.on_comment_delete_delete_cards)
register('comment', '-', ['REMOVE'], comment_manager.on_item_delete_delete_flags)
register('comment', '-', ['REMOVE'], post_manager.on_comment_delete)
register('comment', '-', ['REMOVE'], user_manager.on_comment_delete)
register('comment', 'flag', ['INSERT'], comment_manager.on_flag_add)
register('comment', 'flag', ['REMOVE'], comment_manager.on_flag_delete)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY'],
    card_manager.on_post_comments_unviewed_count_change_update_card,
    {'commentsUnviewedCount': 0},
)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY'],
    card_manager.on_post_likes_count_change_update_card,
    {'anonymousLikeCount': 0, 'onymousLikeCount': 0},
)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY'],
    card_manager.on_post_original_post_id_change_update_card,
    {'originalPostId': None},
)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY'],
    card_manager.on_post_text_tags_change_update_card,
    {'textTags': []},
)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY'],
    card_manager.on_post_viewed_by_count_change_update_card,
    {'viewedByCount': 0},
)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY', 'REMOVE'],
    feed_manager.on_post_status_change_sync_feed,
    {'postStatus': None},
)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY'],
    post_manager.on_post_verification_hidden_change_update_is_verified,
    {'verificationHidden': False},
)
register('post', '-', ['MODIFY'], post_manager.on_post_status_change_fire_gql_notifications, {'postStatus': None})
register('post', '-', ['MODIFY'], user_manager.on_post_status_change_sync_counts, {'postStatus': None})
register('post', '-', ['REMOVE'], card_manager.on_post_delete_delete_cards)
register('post', '-', ['REMOVE'], post_manager.on_item_delete_delete_flags)
register('post', '-', ['REMOVE'], post_manager.on_item_delete_delete_views)
register(
    'post',
    '-',
    ['INSERT', 'MODIFY', 'REMOVE'],
    album_manager.on_post_album_change_update_counts_and_timestamps,
    {'albumId': None, 'gsiK3SortKey': -1},  # all non-completed posts are given rank of -1
)
register('post', 'flag', ['INSERT'], post_manager.on_flag_add)
register('post', 'flag', ['REMOVE'], post_manager.on_flag_delete)
register('post', 'like', ['INSERT'], post_manager.on_like_add)
register('post', 'like', ['REMOVE'], post_manager.on_like_delete)
register(
    'post',
    'view',
    ['INSERT', 'MODIFY'],
    card_manager.on_post_view_count_change_update_cards,
    {'viewCount': 0},
)
register(
    'post',
    'view',
    ['INSERT', 'MODIFY'],
    post_manager.on_post_view_count_change_update_counts,
    {'viewCount': 0},
)
register('post', 'view', ['INSERT', 'REMOVE'], post_manager.on_post_view_add_delete_sync_viewed_by_counts)
register('post', 'view', ['INSERT', 'MODIFY'], post_manager.on_post_view_change_update_trending)
register('user', 'blocker', ['INSERT'], block_manager.on_user_blocked_sync_user_status)
register(
    'user',
    'follower',
    ['INSERT', 'MODIFY', 'REMOVE'],
    feed_manager.on_user_follow_status_change_sync_feed,
    {'followStatus': FollowStatus.NOT_FOLLOWING},
)
register(
    'user',
    'follower',
    ['INSERT', 'MODIFY', 'REMOVE'],
    follower_manager.on_first_story_post_id_change_fire_gql_notifications,
    {'postId': None},
)
register(
    'user',
    'follower',
    ['INSERT', 'MODIFY', 'REMOVE'],
    follower_manager.on_user_follow_status_change_sync_first_story,
    {'followStatus': FollowStatus.NOT_FOLLOWING},
)
register(
    'user',
    'follower',
    ['INSERT', 'MODIFY', 'REMOVE'],
    like_manager.on_user_follow_status_change_sync_likes,
    {'followStatus': FollowStatus.NOT_FOLLOWING},
)
register(
    'user',
    'follower',
    ['INSERT', 'MODIFY', 'REMOVE'],
    user_manager.sync_follow_counts_due_to_follow_status,
    {'followStatus': FollowStatus.NOT_FOLLOWING},
)
register('user', 'profile', ['INSERT'], user_manager.on_user_add_delete_user_deleted_subitem)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    card_manager.on_user_chats_with_unviewed_messages_count_change_sync_card,
    {'chatsWithUnviewedMessagesCount': 0},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    card_manager.on_user_followers_requested_count_change_sync_card,
    {'followersRequestedCount': 0},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.on_user_chat_message_forced_deletion_sync_user_status,
    {'chatMessagesForcedDeletionCount': 0},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.on_user_comment_forced_deletion_sync_user_status,
    {'commentForcedDeletionCount': 0},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.on_user_date_of_birth_change_update_age,
    {'dateOfBirth': None},
)
register('user', 'profile', ['INSERT', 'MODIFY'], user_manager.on_user_change_update_dating)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.on_user_post_forced_archiving_sync_user_status,
    {'postForcedArchivingCount': 0},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.fire_gql_subscription_chats_with_unviewed_messages_count,
    {'chatsWithUnviewedMessagesCount': 0},
)
register('user', 'profile', ['INSERT', 'MODIFY'], user_manager.sync_pinpoint_email, {'email': None})
register('user', 'profile', ['INSERT', 'MODIFY'], user_manager.sync_pinpoint_phone, {'phoneNumber': None})
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.sync_pinpoint_user_status,
    {'userStatus': UserStatus.ACTIVE},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    user_manager.sync_elasticsearch,
    {'username': None, 'fullName': None, 'lastManuallyReindexedAt': None},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY', 'REMOVE'],
    user_manager.on_user_email_change_update_subitem,
    {'email': None},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY', 'REMOVE'],
    user_manager.on_user_phone_number_change_update_subitem,
    {'phoneNumber': None},
)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    card_manager.on_user_subscription_level_change_update_card,
    {'subscriptionLevel': UserSubscriptionLevel.BASIC},
)
register('user', 'profile', ['INSERT', 'MODIFY'], card_manager.on_user_change_update_photo_card)
register(
    'user',
    'profile',
    ['INSERT', 'MODIFY'],
    card_manager.on_user_change_update_anonymous_upsell_card,
    {'userStatus': UserStatus.ACTIVE},
)
register('user', 'profile', ['REMOVE'], album_manager.on_user_delete_delete_all_by_user)
register('user', 'profile', ['REMOVE'], appstore_manager.on_user_delete_delete_all_by_user)
register('user', 'profile', ['REMOVE'], block_manager.on_user_delete_unblock_all_blocks)
register('user', 'profile', ['REMOVE'], card_manager.on_user_delete_delete_cards)
register('user', 'profile', ['REMOVE'], chat_manager.on_user_delete_delete_flags)
register('user', 'profile', ['REMOVE'], chat_manager.on_user_delete_delete_views)
register('user', 'profile', ['REMOVE'], chat_manager.on_user_delete_leave_all_chats)
register('user', 'profile', ['REMOVE'], chat_message_manager.on_user_delete_delete_flags)
register('user', 'profile', ['REMOVE'], comment_manager.on_user_delete_delete_all_by_user)
register('user', 'profile', ['REMOVE'], comment_manager.on_user_delete_delete_flags)
register('user', 'profile', ['REMOVE'], follower_manager.on_user_delete_delete_follower_items)
register('user', 'profile', ['REMOVE'], like_manager.on_user_delete_dislike_all_by_user)
register('user', 'profile', ['REMOVE'], post_manager.on_user_delete_delete_all_by_user)
register('user', 'profile', ['REMOVE'], post_manager.on_user_delete_delete_flags)
register('user', 'profile', ['REMOVE'], post_manager.on_user_delete_delete_views)
register('user', 'profile', ['REMOVE'], screen_manager.on_user_delete_delete_views)
register('user', 'profile', ['REMOVE'], user_manager.on_user_delete)
register('user', 'profile', ['REMOVE'], user_manager.on_user_delete_delete_cognito)


@handler_logging
def process_records(event, context):
    for record in event['Records']:

        name = record['eventName']
        pk = deserialize(record['dynamodb']['Keys']['partitionKey'])
        sk = deserialize(record['dynamodb']['Keys']['sortKey'])
        old_item = {k: deserialize(v) for k, v in record['dynamodb'].get('OldImage', {}).items()}
        new_item = {k: deserialize(v) for k, v in record['dynamodb'].get('NewImage', {}).items()}

        with LogLevelContext(logger, logging.INFO):
            logger.info(f'{name}: `{pk}` / `{sk}` starting processing')

        pk_prefix, item_id = pk.split('/')
        sk_prefix = sk.split('/')[0]

        item_kwargs = {k: v for k, v in {'new_item': new_item, 'old_item': old_item}.items() if v}
        for func in dispatch.search(pk_prefix, sk_prefix, name, old_item, new_item):
            with LogLevelContext(logger, logging.INFO):
                logger.info(f'{name}: `{pk}` / `{sk}` running: {func}')
            try:
                func(item_id, **item_kwargs)
            except Exception as err:
                logger.exception(str(err))
