import logging
from unittest.mock import call, patch
from uuid import uuid4

import pytest

from app.models.appstore.enums import AppStoreSubscriptionStatus
from app.models.post.enums import PostStatus, PostType
from app.models.user.enums import UserStatus, UserSubscriptionLevel
from app.utils import image_size


@pytest.fixture
def user(user_manager, cognito_client):
    user_id, username = str(uuid4()), str(uuid4())[:8]
    cognito_client.create_user_pool_entry(user_id, username, verified_email=f'{username}@real.app')
    yield user_manager.create_cognito_only_user(user_id, username)


@pytest.fixture
def comment(user, post_manager, comment_manager):
    post = post_manager.add_post(user, str(uuid4()), PostType.TEXT_ONLY, text='go go')
    yield comment_manager.add_comment(str(uuid4()), post.id, user.id, 'run far')


@pytest.fixture
def card(user, card_manager, TestCardTemplate):
    yield card_manager.add_or_update_card(TestCardTemplate(user.id, title='card title', action='https://action/'))


@pytest.fixture
def chat(user, chat_manager):
    yield chat_manager.add_group_chat(str(uuid4()), user)


@pytest.fixture
def album(album_manager, user):
    yield album_manager.add_album(user.id, str(uuid4()), 'album name')


def test_on_comment_add_adjusts_counts(user_manager, user, comment):
    # check & save starting state
    org_item = user.refresh_item().item
    assert 'commentCount' not in org_item

    # process, check state
    user_manager.on_comment_add(comment.id, comment.item)
    assert user.refresh_item().item['commentCount'] == 1

    # process, check state
    user_manager.on_comment_add(comment.id, comment.item)
    assert user.refresh_item().item['commentCount'] == 2

    # check for unexpected state changes
    new_item = user.item
    new_item.pop('commentCount')
    assert new_item == org_item


def test_on_comment_delete_adjusts_counts(user_manager, user, comment, caplog):
    # configure, check & save starting state
    user_manager.on_comment_add(comment.id, comment.item)
    org_item = user.refresh_item().item
    assert org_item['commentCount'] == 1
    assert 'commentDeletedCount' not in org_item

    # process, check state
    user_manager.on_comment_delete(comment.id, comment.item)
    new_item = user.refresh_item().item
    assert new_item['commentCount'] == 0
    assert new_item['commentDeletedCount'] == 1

    # process again, verify fails softly
    with caplog.at_level(logging.WARNING):
        user_manager.on_comment_delete(comment.id, comment.item)
    assert len(caplog.records) == 1
    assert 'Failed to decrement' in caplog.records[0].msg
    assert 'commentCount' in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    new_item = user.refresh_item().item
    assert new_item['commentCount'] == 0
    assert new_item['commentDeletedCount'] == 2

    # check for unexpected state changes
    del new_item['commentCount'], org_item['commentCount'], new_item['commentDeletedCount']
    assert new_item == org_item


def test_on_user_add_delete_user_deleted_subitem(user_manager, user):
    key = {'partitionKey': f'user/{user.id}', 'sortKey': 'deleted'}
    # add a deleted subitem, verify
    user_manager.dynamo.add_user_deleted(user.id)
    assert user_manager.dynamo.client.get_item(key)

    # run handler, verify
    user_manager.on_user_add_delete_user_deleted_subitem(user.id, new_item=user.item)
    assert user_manager.dynamo.client.get_item(key) is None

    # run handler again, verify doesn't crash & idempotent
    user_manager.on_user_add_delete_user_deleted_subitem(user.id, new_item=user.item)
    assert user_manager.dynamo.client.get_item(key) is None


def test_on_user_delete_calls_elasticsearch(user_manager, user):
    with patch.object(user_manager, 'elasticsearch_client') as elasticsearch_client_mock:
        user_manager.on_user_delete(user.id, old_item=user.item)
    assert elasticsearch_client_mock.mock_calls == [call.delete_user(user.id)]


def test_on_user_delete_calls_pinpoint(user_manager, user):
    with patch.object(user_manager, 'pinpoint_client') as pinpoint_client_mock:
        user_manager.on_user_delete(user.id, old_item=user.item)
    assert pinpoint_client_mock.mock_calls == [call.delete_user_endpoints(user.id)]


def test_on_user_delete_calls_dating_project(user_manager, user):
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_delete(user.id, old_item=user.item)
    assert rdc_mock.mock_calls == [call.remove_user(user.id, fail_soft=True)]


def test_on_user_delete_adds_user_deleted_subitem(user_manager, user):
    key = {'partitionKey': f'user/{user.id}', 'sortKey': 'deleted'}
    assert user_manager.dynamo.client.get_item(key) is None
    user_manager.on_user_delete(user.id, old_item=user.item)
    assert user_manager.dynamo.client.get_item(key) is not None


def test_on_user_delete_deletes_trending(user_manager, user):
    # give the user some trending, verify
    user.trending_increment_score()
    assert user.refresh_trending_item().trending_item

    # run the handler, verify the trending was deleted
    user_manager.on_user_delete(user.id, old_item=user.item)
    assert user.refresh_trending_item().trending_item is None


def test_on_user_delete_deletes_photo_s3_objects(user_manager, user):
    # add a profile pic of all sizes for that user, verify they are all in s3
    post_id = str(uuid4())
    paths = [user.get_photo_path(size, photo_post_id=post_id) for size in image_size.JPEGS]
    for path in paths:
        user.s3_uploads_client.put_object(path, b'somedata', 'image/jpeg')
    for path in paths:
        assert user_manager.s3_uploads_client.exists(path)

    # run the handler, verify those images were all deleted
    user_manager.on_user_delete(user.id, old_item=user.item)
    for path in paths:
        assert not user.s3_uploads_client.exists(path)


def test_on_card_add_increment_count(user_manager, user, card):
    assert user.refresh_item().item.get('cardCount', 0) == 0

    # handle add, verify state
    user_manager.on_card_add_increment_count(card.id, card.item)
    assert user.refresh_item().item.get('cardCount', 0) == 1

    # handle add, verify state
    user_manager.on_card_add_increment_count(card.id, card.item)
    assert user.refresh_item().item.get('cardCount', 0) == 2


def test_on_card_delete_decrement_count(user_manager, user, card, caplog):
    user_manager.dynamo.increment_card_count(user.id)
    assert user.refresh_item().item.get('cardCount', 0) == 1

    # handle delete, verify state
    user_manager.on_card_delete_decrement_count(card.id, card.item)
    assert user.refresh_item().item.get('cardCount', 0) == 0

    # handle delete, verify fails softly and state unchanged
    with caplog.at_level(logging.WARNING):
        user_manager.on_card_delete_decrement_count(card.id, card.item)
    assert len(caplog.records) == 1
    assert 'Failed to decrement' in caplog.records[0].msg
    assert 'cardCount' in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    assert user.refresh_item().item.get('cardCount', 0) == 0


def test_on_chat_member_add_update_chat_count(user_manager, chat, user):
    # check starting state
    member_item = chat.member_dynamo.get(chat.id, user.id)
    assert member_item
    assert user.refresh_item().item.get('chatCount', 0) == 0

    # react to an add, check state
    user_manager.on_chat_member_add_update_chat_count(chat.id, new_item=member_item)
    assert user.refresh_item().item.get('chatCount', 0) == 1

    # react to another add, check state
    user_manager.on_chat_member_add_update_chat_count(chat.id, new_item=member_item)
    assert user.refresh_item().item.get('chatCount', 0) == 2


def test_on_chat_member_delete_update_chat_count(user_manager, chat, user, caplog):
    # configure and check starting state
    member_item = chat.member_dynamo.get(chat.id, user.id)
    assert member_item
    user_manager.dynamo.increment_chat_count(user.id)
    assert user.refresh_item().item.get('chatCount', 0) == 1

    # react to an delete, check state
    user_manager.on_chat_member_delete_update_chat_count(chat.id, old_item=member_item)
    assert user.refresh_item().item.get('chatCount', 0) == 0

    # react to another delete, verify fails softly
    with caplog.at_level(logging.WARNING):
        user_manager.on_chat_member_delete_update_chat_count(chat.id, old_item=member_item)
    assert len(caplog.records) == 1
    assert 'Failed to decrement' in caplog.records[0].msg
    assert 'chatCount' in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    assert user.refresh_item().item.get('chatCount', 0) == 0


def test_on_album_add_update_album_count(user_manager, album, user):
    # check starting state
    assert user.refresh_item().item.get('albumCount', 0) == 0

    # react to an add, check state
    user_manager.on_album_add_update_album_count(album.id, new_item=album.item)
    assert user.refresh_item().item.get('albumCount', 0) == 1

    # react to another add, check state
    user_manager.on_album_add_update_album_count(album.id, new_item=album.item)
    assert user.refresh_item().item.get('albumCount', 0) == 2


def test_on_album_delete_update_album_count(user_manager, album, user, caplog):
    # configure and check starting state
    user_manager.dynamo.increment_album_count(user.id)
    assert user.refresh_item().item.get('albumCount', 0) == 1

    # react to an delete, check state
    user_manager.on_album_delete_update_album_count(album.id, old_item=album.item)
    assert user.refresh_item().item.get('albumCount', 0) == 0

    # react to another delete, verify fails softly
    with caplog.at_level(logging.WARNING):
        user_manager.on_album_delete_update_album_count(album.id, old_item=album.item)
    assert len(caplog.records) == 1
    assert 'Failed to decrement' in caplog.records[0].msg
    assert 'albumCount' in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    assert user.refresh_item().item.get('albumCount', 0) == 0


@pytest.mark.parametrize(
    'new_status, count_col_incremented',
    [
        [PostStatus.COMPLETED, 'postCount'],
        [PostStatus.ARCHIVED, 'postArchivedCount'],
        [PostStatus.DELETING, 'postDeletedCount'],
    ],
)
def test_on_post_status_change_sync_counts_new_status(
    user_manager,
    user,
    new_status,
    count_col_incremented,
):
    post_id = str(uuid4())
    new_item = {'postId': post_id, 'postedByUserId': user.id, 'postStatus': new_status}
    old_item = {'postId': post_id, 'postedByUserId': user.id, 'postStatus': 'whateves'}
    count_cols = ['postCount', 'postArchivedCount', 'postDeletedCount']

    # check starting state
    user.refresh_item()
    for col in count_cols:
        assert user.item.get(col, 0) == 0

    # react to the change, check counts
    user_manager.on_post_status_change_sync_counts(post_id, new_item=new_item, old_item=old_item)
    user.refresh_item()
    for col in count_cols:
        assert user.item.get(col, 0) == (1 if col == count_col_incremented else 0)

    # react to the change again, check counts
    user_manager.on_post_status_change_sync_counts(post_id, new_item=new_item, old_item=old_item)
    user.refresh_item()
    for col in count_cols:
        assert user.item.get(col, 0) == (2 if col == count_col_incremented else 0)


@pytest.mark.parametrize(
    'old_status, count_col_decremented',
    [[PostStatus.COMPLETED, 'postCount'], [PostStatus.ARCHIVED, 'postArchivedCount']],
)
def test_on_post_status_change_sync_counts_old_status(
    user_manager,
    user,
    old_status,
    count_col_decremented,
    caplog,
):
    post_id = str(uuid4())
    new_item = {'postId': post_id, 'postedByUserId': user.id, 'postStatus': 'whateves'}
    old_item = {'postId': post_id, 'postedByUserId': user.id, 'postStatus': old_status}
    count_cols = ['postCount', 'postArchivedCount', 'postDeletedCount']

    # configure and check starting state
    user.dynamo.increment_post_count(user.id)
    user.dynamo.increment_post_archived_count(user.id)
    user.dynamo.increment_post_deleted_count(user.id)
    user.refresh_item()
    for col in count_cols:
        assert user.item.get(col, 0) == 1

    # react to the change, check counts
    user_manager.on_post_status_change_sync_counts(post_id, new_item=new_item, old_item=old_item)
    user.refresh_item()
    for col in count_cols:
        assert user.item.get(col, 0) == (0 if col == count_col_decremented else 1)

    # react to the change again, verify fails softly
    with caplog.at_level(logging.WARNING):
        user_manager.on_post_status_change_sync_counts(post_id, new_item=new_item, old_item=old_item)
    assert len(caplog.records) == 1
    assert 'Failed to decrement' in caplog.records[0].msg
    assert count_col_decremented in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    user.refresh_item()
    for col in count_cols:
        assert user.item.get(col, 0) == (0 if col == count_col_decremented else 1)


@pytest.mark.parametrize(
    'method_name, attr_name, dynamo_lib_name',
    [
        ['on_user_email_change_update_subitem', 'email', 'email_dynamo'],
        ['on_user_phone_number_change_update_subitem', 'phoneNumber', 'phone_number_dynamo'],
    ],
)
def test_on_user_contact_attribute_change_update_subitem(
    user_manager, user, method_name, attr_name, dynamo_lib_name
):
    # test adding for the first time
    new_item = {**user.item, attr_name: 'the-value'}
    with patch.object(user_manager, dynamo_lib_name) as dynamo_lib_mock:
        getattr(user_manager, method_name)(user.id, new_item=new_item)
    assert dynamo_lib_mock.mock_calls == [call.add('the-value', user.id)]

    # test changing to a different value
    old_item = new_item.copy()
    new_item = {**old_item, attr_name: 'new-value'}
    with patch.object(user_manager, dynamo_lib_name) as dynamo_lib_mock:
        getattr(user_manager, method_name)(user.id, new_item=new_item, old_item=old_item)
    assert dynamo_lib_mock.mock_calls == [call.add('new-value', user.id), call.delete('the-value', user.id)]

    # test deleting the value
    old_item = new_item.copy()
    with patch.object(user_manager, dynamo_lib_name) as dynamo_lib_mock:
        getattr(user_manager, method_name)(user.id, old_item=old_item)
    assert dynamo_lib_mock.mock_calls == [call.delete('new-value', user.id)]


def test_delete_user_clears_cognito(user_manager, user, cognito_client):
    # moto has not yet implemented identity pool describeIdentity, so skipping that for now
    assert cognito_client.get_user_attributes(user.id)

    # user status with RESETTING, verify leaves cognito alone
    old_item = {**user.item, 'userStatus': UserStatus.RESETTING}
    user_manager.on_user_delete_delete_cognito(user.id, old_item=old_item)
    cognito_client.get_user_attributes(user.id)

    # user status with anything other than RESETTING
    user_manager.on_user_delete_delete_cognito(user.id, old_item=user.item)
    with pytest.raises(cognito_client.user_pool_client.exceptions.UserNotFoundException):
        cognito_client.get_user_attributes(user.id)

    # fire again, make sure handler doesn't error out on missing cognito profile
    user_manager.on_user_delete_delete_cognito(user.id, old_item=user.item)
    with pytest.raises(cognito_client.user_pool_client.exceptions.UserNotFoundException):
        cognito_client.get_user_attributes(user.id)


@pytest.mark.parametrize(
    'method_name, check_method_name, log_pattern',
    [
        [
            'on_user_chat_message_forced_deletion_sync_user_status',
            'is_forced_disabling_criteria_met_by_chat_messages',
            'due to chatMessages',
        ],
        [
            'on_user_comment_forced_deletion_sync_user_status',
            'is_forced_disabling_criteria_met_by_comments',
            'due to comments',
        ],
        [
            'on_user_post_forced_archiving_sync_user_status',
            'is_forced_disabling_criteria_met_by_posts',
            'due to posts',
        ],
    ],
)
def test_on_criteria_sync_user_status(user_manager, user, method_name, check_method_name, log_pattern, caplog):
    # test does not call
    with patch.object(user, check_method_name, return_value=False):
        with patch.object(user_manager, 'init_user', return_value=user):
            with caplog.at_level(logging.WARNING):
                getattr(user_manager, method_name)(user.id, user.item, user.item)
    assert len(caplog.records) == 0
    assert user.refresh_item().status == UserStatus.ACTIVE

    # test does call
    with patch.object(user, check_method_name, return_value=True):
        with patch.object(user_manager, 'init_user', return_value=user):
            with caplog.at_level(logging.WARNING):
                getattr(user_manager, method_name)(user.id, user.item, user.item)
    assert len(caplog.records) == 1
    assert 'USER_FORCE_DISABLED' in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    assert user.username in caplog.records[0].msg
    assert log_pattern in caplog.records[0].msg
    assert user.refresh_item().status == UserStatus.DISABLED


def test_on_appstore_sub_status_change_update_subscription(user_manager, user):
    assert user.refresh_item().subscription_level == UserSubscriptionLevel.BASIC

    # simulate adding a new appstore subscription
    new_item = {'userId': user.id, 'status': AppStoreSubscriptionStatus.ACTIVE}
    user_manager.on_appstore_sub_status_change_update_subscription(str(uuid4()), new_item=new_item)
    assert user.refresh_item().subscription_level == UserSubscriptionLevel.DIAMOND

    # simulate that subscription expiring
    old_item = new_item
    new_item = {'userId': user.id, 'status': AppStoreSubscriptionStatus.EXPIRED}
    user_manager.on_appstore_sub_status_change_update_subscription(
        str(uuid4()), new_item=new_item, old_item=old_item
    )
    assert user.refresh_item().subscription_level == UserSubscriptionLevel.BASIC

    # simulate them re-starting the subscription
    old_item = new_item
    new_item = {'userId': user.id, 'status': AppStoreSubscriptionStatus.ACTIVE}
    user_manager.on_appstore_sub_status_change_update_subscription(
        str(uuid4()), new_item=new_item, old_item=old_item
    )
    assert user.refresh_item().subscription_level == UserSubscriptionLevel.DIAMOND

    # simulate them cancelling the subscription
    old_item = new_item
    new_item = {'userId': user.id, 'status': AppStoreSubscriptionStatus.CANCELLED}
    user_manager.on_appstore_sub_status_change_update_subscription(
        str(uuid4()), new_item=new_item, old_item=old_item
    )
    assert user.refresh_item().subscription_level == UserSubscriptionLevel.BASIC


def test_on_user_date_of_birth_change_update_age(user_manager, user):
    assert 'age' not in user.refresh_item().item

    # fire simulating the creation of a user with a date of birth
    user.update_details(date_of_birth='1992-04-26')
    user_manager.on_user_date_of_birth_change_update_age(user.id, new_item=user.item)
    assert 'age' in user.refresh_item().item

    # fire simulating the editing of a user to remove date of birth
    old_item = user.item.copy()
    user.update_details(date_of_birth='')
    user_manager.on_user_date_of_birth_change_update_age(user.id, new_item=user.item, old_item=old_item)
    assert 'age' not in user.refresh_item().item

    # fire simulating the editing of a user to change date of birth
    old_item = user.item.copy()
    user.update_details(date_of_birth='2020-01-01')
    user_manager.on_user_date_of_birth_change_update_age(user.id, new_item=user.item, old_item=old_item)
    assert 'age' in user.refresh_item().item
