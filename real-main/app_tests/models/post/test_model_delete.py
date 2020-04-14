from unittest.mock import call, Mock

import pendulum
import pytest

from app.models.comment import CommentManager
from app.models.feed import FeedManager
from app.models.flag import FlagManager
from app.models.followed_first_story import FollowedFirstStoryManager
from app.models.like import LikeManager
from app.models.media.enums import MediaStatus
from app.models.post.enums import PostStatus, PostType
from app.models.trending import TrendingManager
from app.models.view import ViewManager
from app.utils import image_size


@pytest.fixture
def user(user_manager, cognito_client):
    cognito_client.boto_client.admin_create_user(UserPoolId=cognito_client.user_pool_id, Username='pbuid2')
    yield user_manager.create_cognito_only_user('pbuid2', 'pbUname2')


@pytest.fixture
def post_with_expiration(post_manager, user):
    yield post_manager.add_post(
        user.id, 'pid2', PostType.TEXT_ONLY, text='t', lifetime_duration=pendulum.duration(hours=1),
    )


@pytest.fixture
def post_with_album(album_manager, post_manager, user, image_data_b64):
    album = album_manager.add_album(user.id, 'aid', 'album name')
    yield post_manager.add_post(
        user.id, 'pid2', PostType.IMAGE, image_input={'imageData': image_data_b64}, album_id=album.id,
    )


@pytest.fixture
def completed_post_with_media(post_manager, user, image_data_b64):
    yield post_manager.add_post(user.id, 'pid3', PostType.IMAGE, image_input={'imageData': image_data_b64})


@pytest.fixture
def post_with_media(post_manager, user):
    yield post_manager.add_post(user.id, 'pid4', PostType.IMAGE, text='t', image_input={'originalMetadata': '{}'})


def test_delete_completed_text_only_post_with_expiration(post_manager, post_with_expiration, user_manager):
    post = post_with_expiration
    posted_by_user_id = post.item['postedByUserId']
    posted_by_user = user_manager.get_user(posted_by_user_id)

    # check our starting post count
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 1

    # mock out some calls to far-flung other managers
    post.comment_manager = Mock(CommentManager({}))
    post.feed_manager = Mock(FeedManager({}))
    post.flag_manager = Mock(FlagManager({}))
    post.followed_first_story_manager = Mock(FollowedFirstStoryManager({}))
    post.like_manager = Mock(LikeManager({}))
    post.trending_manager = Mock(TrendingManager({'dynamo': {}}))
    post.view_manager = Mock(ViewManager({}))

    # delete the post
    post.delete()
    assert post.item['postStatus'] == PostStatus.DELETING
    assert post.item['mediaObjects'] == []
    post_item = post.item

    # check the post is no longer in the DB
    post.refresh_item()
    assert post.item is None

    # check our post count - should have decremented
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 0

    # check calls to mocked out managers
    assert post.comment_manager.mock_calls == [
        call.delete_all_on_post(post.id),
    ]
    assert post.flag_manager.mock_calls == [
        call.unflag_all_on_post(post.id),
    ]
    assert post.feed_manager.mock_calls == [
        call.delete_post_from_followers_feeds(posted_by_user_id, post.id),
    ]
    assert post.followed_first_story_manager.mock_calls == [
        call.refresh_after_story_change(story_prev=post_item),
    ]
    assert post.like_manager.mock_calls == [
        call.dislike_all_of_post(post.id),
    ]
    assert post.view_manager.mock_calls == [
        call.delete_views(post_item['partitionKey']),
    ]
    assert post.trending_manager.mock_calls == [
        call.dynamo.delete_trending(post.id),
    ]


def test_delete_pending_media_post(post_manager, post_with_media, user_manager):
    post = post_with_media
    media = post_manager.media_manager.init_media(post_with_media.item['mediaObjects'][0])
    posted_by_user_id = post.item['postedByUserId']
    posted_by_user = user_manager.get_user(posted_by_user_id)
    assert post_manager.dynamo.get_post(post_with_media.id)
    assert post_manager.dynamo.get_original_metadata(post_with_media.id)

    # check our starting post count
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 0

    # mock out some calls to far-flung other managers
    post.comment_manager = Mock(CommentManager({}))
    post.like_manager = Mock(LikeManager({}))
    post.followed_first_story_manager = Mock(FollowedFirstStoryManager({}))
    post.feed_manager = Mock(FeedManager({}))
    post.view_manager = Mock(ViewManager({}))
    post.trending_manager = Mock(TrendingManager({'dynamo': {}}))

    # delete the post
    post.delete()
    assert post.item['postStatus'] == PostStatus.DELETING
    assert len(post.item['mediaObjects']) == 1
    assert post.item['mediaObjects'][0]['mediaStatus'] == MediaStatus.DELETING

    # check the db again
    post_item = post.item
    post.refresh_item()
    assert post.item is None
    media.refresh_item()
    assert media.item is None
    assert post_manager.dynamo.get_original_metadata(post_with_media.id) is None

    # check our post count - should not have changed
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 0

    # check calls to mocked out managers
    assert post.comment_manager.mock_calls == [
        call.delete_all_on_post(post.id),
    ]
    assert post.like_manager.mock_calls == [
        call.dislike_all_of_post(post.id),
    ]
    assert post.followed_first_story_manager.mock_calls == []
    assert post.feed_manager.mock_calls == []
    assert post.view_manager.mock_calls == [
        call.delete_views(post_item['partitionKey']),
    ]
    assert post.trending_manager.mock_calls == [
        call.dynamo.delete_trending(post.id),
    ]


def test_delete_completed_media_post(post_manager, completed_post_with_media, user_manager):
    post = completed_post_with_media
    media = post_manager.media_manager.init_media(post.item['mediaObjects'][0])
    posted_by_user_id = post.item['postedByUserId']
    posted_by_user = user_manager.get_user(posted_by_user_id)

    # check our starting post count
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 1

    # mock out some calls to far-flung other managers
    post.comment_manager = Mock(CommentManager({}))
    post.like_manager = Mock(LikeManager({}))
    post.followed_first_story_manager = Mock(FollowedFirstStoryManager({}))
    post.feed_manager = Mock(FeedManager({}))
    post.view_manager = Mock(ViewManager({}))
    post.trending_manager = Mock(TrendingManager({'dynamo': {}}))

    # delete the post
    post.delete()
    assert post.item['postStatus'] == PostStatus.DELETING
    assert len(post.item['mediaObjects']) == 1
    assert post.item['mediaObjects'][0]['mediaStatus'] == MediaStatus.DELETING

    # check the all the media got deleted
    for size in image_size.JPEGS:
        path = media.get_s3_path(size)
        assert post_manager.clients['s3_uploads'].exists(path) is False

    # check the DB again
    post_item = post.item
    post.refresh_item()
    assert post.item is None
    media.refresh_item()
    assert media.item is None

    # check our post count - should have decremented
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 0

    # check calls to mocked out managers
    assert post.comment_manager.mock_calls == [
        call.delete_all_on_post(post.id),
    ]
    assert post.like_manager.mock_calls == [
        call.dislike_all_of_post(post.id),
    ]
    assert post.followed_first_story_manager.mock_calls == []
    assert post.feed_manager.mock_calls == [
        call.delete_post_from_followers_feeds(posted_by_user_id, post.id),
    ]
    assert post.view_manager.mock_calls == [
        call.delete_views(post_item['partitionKey']),
    ]
    assert post.trending_manager.mock_calls == [
        call.dynamo.delete_trending(post.id),
    ]


def test_delete_completed_post_in_album(album_manager, post_manager, post_with_album, user_manager):
    post = post_with_album
    posted_by_user_id = post.item['postedByUserId']
    album = album_manager.get_album(post.item['albumId'])
    posted_by_user = user_manager.get_user(posted_by_user_id)
    assert post.item['gsiK3PartitionKey'] == f'post/{album.id}'
    assert post.item['gsiK3SortKey'] == 0

    # check our starting point
    assert post.item['postStatus'] == PostStatus.COMPLETED
    album.refresh_item()
    assert album.item.get('postCount', 0) == 1
    assert album.item.get('rankCount', 0) == 1
    assert album.item['artHash']
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 1

    # mock out some calls to far-flung other managers
    post.comment_manager = Mock(CommentManager({}))
    post.like_manager = Mock(LikeManager({}))
    post.followed_first_story_manager = Mock(FollowedFirstStoryManager({}))
    post.feed_manager = Mock(FeedManager({}))
    post.view_manager = Mock(ViewManager({}))
    post.trending_manager = Mock(TrendingManager({'dynamo': {}}))

    # delete the post
    post.delete()
    assert post.item['postStatus'] == PostStatus.DELETING
    assert len(post.item['mediaObjects']) == 1
    assert post.item['mediaObjects'][0]['mediaStatus'] == MediaStatus.DELETING
    assert post.item['gsiK3PartitionKey'] == f'post/{album.id}'
    assert post.item['gsiK3SortKey'] == -1

    # check the DB again
    post_item = post.item
    post.refresh_item()
    assert post.item is None

    # check our post count - should have decremented
    album.refresh_item()
    assert album.item.get('postCount', 0) == 0
    assert album.item.get('rankCount', 0) == 1
    assert 'artHash' not in album.item
    posted_by_user.refresh_item()
    assert posted_by_user.item.get('postCount', 0) == 0

    # check calls to mocked out managers
    assert post.comment_manager.mock_calls == [
        call.delete_all_on_post(post.id),
    ]
    assert post.like_manager.mock_calls == [
        call.dislike_all_of_post(post.id),
    ]
    assert post.followed_first_story_manager.mock_calls == []
    assert post.feed_manager.mock_calls == [
        call.delete_post_from_followers_feeds(posted_by_user_id, post.id),
    ]
    assert post.view_manager.mock_calls == [
        call.delete_views(post_item['partitionKey']),
    ]
    assert post.trending_manager.mock_calls == [
        call.dynamo.delete_trending(post.id),
    ]
