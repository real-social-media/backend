import logging
from unittest.mock import Mock, call, patch
from uuid import uuid4

import botocore
import pendulum
import pytest

from app.clients.cognito import InvalidEncryption
from app.models.follower.enums import FollowStatus
from app.models.user.enums import (
    UserDatingStatus,
    UserGender,
    UserPrivacyStatus,
    UserStatus,
    UserSubscriptionLevel,
)
from app.models.user.exceptions import (
    UserAlreadyGrantedSubscription,
    UserException,
    UserValidationException,
    UserVerificationException,
)


@pytest.fixture
def user(user_manager, cognito_client):
    user_id, username = str(uuid4()), str(uuid4())[:8]
    cognito_client.create_user_pool_entry(user_id, username, verified_email=f'{username}@real.app')
    yield user_manager.create_cognito_only_user(user_id, username)


@pytest.fixture
def user2(user_manager, cognito_client):
    user_id, username = str(uuid4()), str(uuid4())[:8]
    cognito_client.create_user_pool_entry(user_id, username, verified_email=f'{username}@real.app')
    yield user_manager.create_cognito_only_user(user_id, username)


@pytest.fixture
def user3(user_manager, cognito_client):
    user_id, username = str(uuid4()), str(uuid4())[:8]
    cognito_client.create_user_pool_entry(user_id, username, verified_email=f'{username}@real.app')
    yield user_manager.create_cognito_only_user(user_id, username)


@pytest.fixture
def anonymous_user(user_manager):
    with patch.object(user_manager.cognito_client, 'get_user_pool_tokens', return_value={'IdToken': 'id-token'}):
        user, _ = user_manager.create_anonymous_user(str(uuid4()))
        yield user


@pytest.fixture
def user_verified_phone(user_manager, cognito_client):
    user_id, username = str(uuid4()), str(uuid4())[:8]
    cognito_client.create_user_pool_entry(user_id, username, verified_phone='+12125551212')
    yield user_manager.create_cognito_only_user(user_id, username)


def test_refresh(user):
    new_username = 'really good'
    assert user.item['username'] != new_username

    # go behind their back and change the DB item on them
    user.dynamo.update_user_username(user.id, new_username, user.item['username'])
    user.refresh_item()
    assert user.item['username'] == new_username


def test_invalid_username(user):
    user.cognito_client = Mock()

    invalid_username = '-'
    with pytest.raises(UserValidationException):
        user.update_username(invalid_username)

    assert user.item['username'] != invalid_username
    assert user.cognito_client.mock_calls == []


def test_update_username_no_change(user):
    user.cognito_client = Mock()

    org_user_item = user.item
    user.update_username(user.username)
    assert user.item == org_user_item
    assert user.cognito_client.mock_calls == []


def test_success_update_username(user):
    assert user.cognito_client.get_user_attributes(user.id)['preferred_username'] == user.username.lower()

    # change the username, verify it changed
    new_username = user.username + 'newusername'
    user.update_username(new_username)
    assert user.username == new_username
    assert user.cognito_client.get_user_attributes(user.id)['preferred_username'] == new_username.lower()


def test_cant_update_username_to_one_already_taken(user, user2):
    username = 'nothingButClearSkies'

    # another user takes the username (case insensitive)
    user2.update_username(username.lower())
    assert user2.item['username'] == username.lower()

    # mock out the cognito backend so it behaves like the real thing
    exception = user.cognito_client.user_pool_client.exceptions.AliasExistsException({}, None)
    user.cognito_client.set_user_attributes = Mock(side_effect=exception)

    # verify we can't update to that username
    with pytest.raises(UserValidationException):
        user.update_username(username.upper())


def test_update_no_details(user):
    org_user_item = user.item
    user.update_details()
    # check the user_item has not been replaced
    assert user.item is org_user_item


def test_update_with_existing_values_causes_no_update(user):
    user.update_details(language_code='en', likes_disabled=False)
    assert user.item['languageCode'] == 'en'
    assert user.item['likesDisabled'] is False
    assert 'fullName' not in user.item
    org_user_item = user.item
    user.update_details(language_code='en', likes_disabled=False, full_name='')
    # check the user_item has not been replaced
    assert user.item is org_user_item


def test_update_all_details(user):
    # check only privacy status is already set
    assert 'fullName' not in user.item
    assert 'bio' not in user.item
    assert 'languageCode' not in user.item
    assert 'themeCode' not in user.item
    assert 'followCountsHidden' not in user.item
    assert 'viewCountsHidden' not in user.item

    user.update_details(
        full_name='f',
        bio='b',
        language_code='de',
        theme_code='orange',
        follow_counts_hidden=True,
        view_counts_hidden=True,
    )

    # check the user.item has not been replaced
    assert user.item['fullName'] == 'f'
    assert user.item['bio'] == 'b'
    assert user.item['languageCode'] == 'de'
    assert user.item['themeCode'] == 'orange'
    assert user.item['followCountsHidden'] is True
    assert user.item['viewCountsHidden'] is True


def test_delete_all_details(user):
    # set some details
    user.update_details(
        full_name='f',
        bio='b',
        language_code='de',
        theme_code='orange',
        follow_counts_hidden=True,
        view_counts_hidden=True,
    )

    # delete those details, all except for privacyStatus which can't be deleted
    user.update_details(
        full_name='', bio='', language_code='', theme_code='', follow_counts_hidden='', view_counts_hidden=''
    )

    # check the delete made it through
    assert 'fullName' not in user.item
    assert 'bio' not in user.item
    assert 'languageCode' not in user.item
    assert 'themeCode' not in user.item
    assert 'followCountsHidden' not in user.item
    assert 'viewCountsHidden' not in user.item


def test_update_age(user):
    assert 'dateOfBirth' not in user.item
    assert 'age' not in user.item
    assert user.update_age() is False
    assert 'age' not in user.item

    user.update_details(date_of_birth='1990-07-01')
    assert user.item['dateOfBirth'] == '1990-07-01'
    assert 'age' not in user.item

    # update age once
    now = pendulum.parse('2020-06-30T04:03:05.2343Z')
    assert user.update_age(now=now) is True
    assert user.item['age'] == 29

    # update age again
    now = pendulum.parse('2020-07-01T04:03:05.2343Z')
    assert user.update_age(now=now) is True
    assert user.item['age'] == 30

    # update age again, no update needed
    now = pendulum.parse('2020-08-01T04:03:05.2343Z')
    assert user.update_age(now=now) is False
    assert user.item['age'] == 30

    # delete the date of birth, then update age again
    user.update_details(date_of_birth='')
    assert 'dateOfBirth' not in user.item
    assert 'age' in user.item

    assert user.update_age(now=now) is True
    assert 'age' not in user.item


def test_disable_enable_user_status(user, caplog):
    assert user.status == UserStatus.ACTIVE
    assert 'userStatus' not in user.item

    # no op
    user.enable()
    assert user.status == UserStatus.ACTIVE

    # force disable user
    with caplog.at_level(logging.WARNING):
        user.disable(forced_by='kittens')
    assert len(caplog.records) == 1
    assert 'USER_FORCE_DISABLED' in caplog.records[0].msg
    assert 'kittens' in caplog.records[0].msg
    assert user.id in caplog.records[0].msg
    assert user.username in caplog.records[0].msg
    assert user.status == UserStatus.DISABLED
    assert user.refresh_item().status == UserStatus.DISABLED

    # disable user
    user.disable()
    assert user.status == UserStatus.DISABLED

    # enable user
    user.enable()
    assert user.status == UserStatus.ACTIVE
    assert user.refresh_item().status == UserStatus.ACTIVE

    # disable again, this time not forced
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        user.disable()
    assert len(caplog.records) == 0
    assert user.status == UserStatus.DISABLED
    assert user.refresh_item().status == UserStatus.DISABLED

    # directly in dynamo set user status to DELETING
    user.dynamo.set_user_status(user.id, UserStatus.DELETING)
    user.refresh_item()
    assert user.status == UserStatus.DELETING

    with pytest.raises(UserException, match='Cannot enable user .* in status'):
        user.enable()
    with pytest.raises(UserException, match='Cannot disable user .* in status'):
        user.disable()


def test_disable_enable_user_status_anonymous_user(anonymous_user, caplog):
    user = anonymous_user
    assert user.refresh_item().status == UserStatus.ANONYMOUS

    # no-op
    assert user.enable().status == UserStatus.ANONYMOUS
    assert user.refresh_item().status == UserStatus.ANONYMOUS

    # disable user
    assert user.disable().status == UserStatus.DISABLED
    assert user.refresh_item().status == UserStatus.DISABLED

    # no-op
    assert user.disable().status == UserStatus.DISABLED
    assert user.refresh_item().status == UserStatus.DISABLED

    # enable user
    assert user.enable().status == UserStatus.ANONYMOUS
    assert user.refresh_item().status == UserStatus.ANONYMOUS


def test_set_privacy_status_no_change(user):
    privacy_status = UserPrivacyStatus.PUBLIC
    user.set_privacy_status(privacy_status)

    org_user_item = user.item
    user.set_privacy_status(privacy_status)
    # verify there was no write to the DB by checking object identity
    assert org_user_item is user.item


def test_set_privacy_status_from_public_to_private(user):
    privacy_status = UserPrivacyStatus.PUBLIC
    user.set_privacy_status(privacy_status)
    assert user.item['privacyStatus'] == privacy_status

    privacy_status = UserPrivacyStatus.PRIVATE
    user.set_privacy_status(privacy_status)
    assert user.item['privacyStatus'] == privacy_status


def test_set_privacy_status_from_private_to_public(user_manager, user, user2, user3):
    follower_manager = user_manager.follower_manager
    privacy_status = UserPrivacyStatus.PRIVATE
    user.set_privacy_status(privacy_status)
    assert user.item['privacyStatus'] == privacy_status

    # set up a follow request in REQUESTED state
    follower_manager.request_to_follow(user2, user)

    # set up a follow request in DENIED state
    follower_manager.request_to_follow(user3, user).deny()

    # check we can see those two request
    resp = list(follower_manager.dynamo.generate_follower_items(user.id, follow_status=FollowStatus.REQUESTED))
    assert len(resp) == 1
    resp = list(follower_manager.dynamo.generate_follower_items(user.id, follow_status=FollowStatus.DENIED))
    assert len(resp) == 1

    # change to private
    privacy_status = UserPrivacyStatus.PUBLIC
    user.set_privacy_status(privacy_status)
    assert user.item['privacyStatus'] == privacy_status

    # check those two requests disappeared
    resp = list(follower_manager.dynamo.generate_follower_items(user.id, follow_status=FollowStatus.REQUESTED))
    assert len(resp) == 0
    resp = list(follower_manager.dynamo.generate_follower_items(user.id, follow_status=FollowStatus.DENIED))
    assert len(resp) == 0


def test_start_change_email(user):
    prev_email = 'stop@stop.com'
    user.item = user.dynamo.set_user_details(user.id, email=prev_email)
    user.cognito_client.set_user_attributes(user.id, {'email': prev_email, 'email_verified': 'true'})

    # check starting state
    assert user.item['email'] == prev_email
    attrs = user.cognito_client.get_user_attributes(user.id)
    assert attrs['email'] == prev_email
    assert attrs['email_verified'] == 'true'
    assert 'custom:unverified_email' not in attrs

    # start the email change
    new_email = 'go@go.com'
    user.start_change_contact_attribute('email', new_email)

    # check final state
    assert user.item['email'] == prev_email
    attrs = user.cognito_client.get_user_attributes(user.id)
    assert attrs['email'] == prev_email
    assert attrs['email_verified'] == 'true'
    assert attrs['custom:unverified_email'] == new_email


def test_finish_change_email(user):
    # set up cognito like we have already started an email change
    new_email = 'go@go.com'
    user.cognito_client.set_user_attributes(user.id, {'custom:unverified_email': new_email})

    # moto has not yet implemented verify_user_attribute, admin_delete_user_attributes, or admin_initiate_auth
    user.cognito_client.get_user_pool_tokens = Mock(return_value={'AccessToken': 'access_token'})
    user.cognito_client.verify_user_attribute = Mock()
    user.cognito_client.clear_user_attribute = Mock()

    user.finish_change_contact_attribute('email', 'verification_code')
    assert user.item['email'] == new_email

    attrs = user.cognito_client.get_user_attributes(user.id)
    assert attrs['email'] == new_email
    assert attrs['email_verified'] == 'true'

    assert user.cognito_client.verify_user_attribute.mock_calls == [
        call('access_token', 'email', 'verification_code'),
    ]
    assert user.cognito_client.clear_user_attribute.mock_calls == [call(user.id, 'custom:unverified_email')]


def test_finish_change_email_anonymous_user_becomes_active(anonymous_user):
    # set up cognito like we have already started an email change
    user = anonymous_user
    new_email = 'go@go.com'
    user.cognito_client.set_user_attributes(user.id, {'custom:unverified_email': new_email})
    assert user.refresh_item().status == UserStatus.ANONYMOUS

    # moto has not yet implemented verify_user_attribute, admin_delete_user_attributes, or admin_initiate_auth
    user.cognito_client.get_user_pool_tokens = Mock(return_value={'AccessToken': 'access_token'})
    user.cognito_client.verify_user_attribute = Mock()
    user.cognito_client.clear_user_attribute = Mock()

    user.finish_change_contact_attribute('email', 'verification_code')
    assert user.item == user.refresh_item().item
    assert user.item['email'] == new_email
    assert user.status == UserStatus.ACTIVE


def test_start_change_phone(user):
    prev_phone = '+123'
    user.item = user.dynamo.set_user_details(user.id, phone=prev_phone)
    user.cognito_client.set_user_attributes(user.id, {'phone': prev_phone, 'phone_verified': 'true'})

    # check starting state
    assert user.item['phoneNumber'] == prev_phone
    attrs = user.cognito_client.get_user_attributes(user.id)
    assert attrs['phone'] == prev_phone
    assert attrs['phone_verified'] == 'true'
    assert 'custom:unverified_phone' not in attrs

    # start the email change
    new_phone = '+567'
    user.start_change_contact_attribute('phone', new_phone)

    # check final state
    assert user.item['phoneNumber'] == prev_phone
    attrs = user.cognito_client.get_user_attributes(user.id)
    assert attrs['phone'] == prev_phone
    assert attrs['phone_verified'] == 'true'
    assert attrs['custom:unverified_phone'] == new_phone


def test_finish_change_phone(user):
    # set attributes in cognito that would have been set when email change process started
    new_phone = '+567'
    user.cognito_client.set_user_attributes(user.id, {'custom:unverified_phone': new_phone})

    # moto has not yet implemented verify_user_attribute, admin_delete_user_attributes, or admin_initiate_auth
    user.cognito_client.get_user_pool_tokens = Mock(return_value={'AccessToken': 'access_token'})
    user.cognito_client.verify_user_attribute = Mock()
    user.cognito_client.clear_user_attribute = Mock()

    user.finish_change_contact_attribute('phone', 'verification_code')
    assert user.item['phoneNumber'] == new_phone

    attrs = user.cognito_client.get_user_attributes(user.id)
    assert attrs['phone_number'] == new_phone
    assert attrs['phone_number_verified'] == 'true'

    assert user.cognito_client.verify_user_attribute.mock_calls == [
        call('access_token', 'phone_number', 'verification_code'),
    ]
    assert user.cognito_client.clear_user_attribute.mock_calls == [call(user.id, 'custom:unverified_phone')]


def test_start_change_email_same_as_existing(user):
    prev_email = 'stop@stop.com'
    user.item = user.dynamo.set_user_details(user.id, email=prev_email)

    new_email = prev_email
    with pytest.raises(UserVerificationException):
        user.start_change_contact_attribute('email', new_email)


def test_start_change_email_no_old_value(user_verified_phone):
    user = user_verified_phone

    # check starting state
    assert 'email' not in user.item
    user_attrs = user.cognito_client.get_user_attributes(user.id)
    assert 'email' not in user_attrs
    assert 'custom:unverified_email' not in user_attrs

    new_email = 'go@go.com'
    user.start_change_contact_attribute('email', new_email)
    assert 'email' not in user.item

    # check the cognito attributes set correctly
    user_attrs = user.cognito_client.get_user_attributes(user.id)
    assert user_attrs['email'] == new_email
    assert user_attrs['custom:unverified_email'] == new_email


def test_finish_change_email_no_unverified_email(user):
    org_email = user.item['email']
    verification_code = {}
    with pytest.raises(UserVerificationException):
        user.finish_change_contact_attribute('email', verification_code)
    assert user.cognito_client.get_user_attributes(user.id)['email'] == org_email
    assert user.item['email'] == org_email


def test_finish_change_email_wrong_verification_code(user):
    # set attributes in cognito that would have been set when email change process started
    new_email = 'go@go.com'
    org_email = user.item['email']
    user.cognito_client.set_user_attributes(user.id, {'custom:unverified_email': new_email})

    # moto has not yet implemented verify_user_attribute, admin_delete_user_attributes, or admin_initiate_auth
    user.cognito_client.get_user_pool_tokens = Mock(return_value={'AccessToken': 'access_token'})
    exception = user.cognito_client.user_pool_client.exceptions.CodeMismatchException({}, None)
    user.cognito_client.user_pool_client.verify_user_attribute = Mock(side_effect=exception)

    verification_code = {}
    with pytest.raises(UserVerificationException):
        user.finish_change_contact_attribute('email', verification_code)
    assert user.cognito_client.get_user_attributes(user.id)['email'] == org_email
    assert user.item['email'] == org_email


def test_serailize_self(user):
    resp = user.serialize(user.id)
    assert resp.pop('blockerStatus') == 'SELF'
    assert resp.pop('followedStatus') == 'SELF'
    assert resp == user.item


def test_serailize_unrelated(user, user2):
    resp = user.serialize(user2.id)
    assert resp.pop('blockerStatus') == 'NOT_BLOCKING'
    assert resp.pop('followedStatus') == 'NOT_FOLLOWING'
    assert resp == user.item


def test_serailize_blocker(user, user2, block_manager):
    # they block caller
    block_manager.block(user, user2)
    user.refresh_item()

    resp = user.serialize(user2.id)
    assert resp.pop('blockerStatus') == 'BLOCKING'
    assert resp.pop('followedStatus') == 'NOT_FOLLOWING'
    assert resp == user.item


def test_serailize_followed(user, user2, follower_manager):
    # caller follows them
    follower_manager.request_to_follow(user2, user)
    user.refresh_item()

    resp = user.serialize(user2.id)
    assert resp.pop('blockerStatus') == 'NOT_BLOCKING'
    assert resp.pop('followedStatus') == 'FOLLOWING'
    assert resp == user.item


def test_serialize_deleting(user, user2):
    user.delete()

    resp = user.serialize(user.id)
    assert resp['userId'] == user.id
    assert resp['userStatus'] == 'DELETING'
    assert resp['blockerStatus'] == 'SELF'
    assert resp['followedStatus'] == 'SELF'

    resp = user.serialize(user2.id)
    assert resp['userId'] == user.id
    assert resp['userStatus'] == 'DELETING'
    assert resp['blockerStatus'] == 'NOT_BLOCKING'
    assert resp['followedStatus'] == 'NOT_FOLLOWING'

    user.refresh_item()
    with pytest.raises(AssertionError):
        user.serialize(user.id)


def test_is_forced_disabling_criteria_met_by_posts(user):
    # check starting state
    assert user.item.get('postCount', 0) == 0
    assert user.item.get('postArchivedCount', 0) == 0
    assert user.item.get('postForcedArchivingCount', 0) == 0
    assert user.is_forced_disabling_criteria_met_by_posts() is False

    # first post was force-disabled, shouldn't disable the user
    user.item['postCount'] = 1
    user.item['postArchivedCount'] = 0
    user.item['postForcedArchivingCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_posts() is False

    # just below criteria cutoff
    user.item['postCount'] = 5
    user.item['postArchivedCount'] = 0
    user.item['postForcedArchivingCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_posts() is False
    user.item['postCount'] = 3
    user.item['postArchivedCount'] = 3
    user.item['postForcedArchivingCount'] = 0
    assert user.is_forced_disabling_criteria_met_by_posts() is False

    # just above criteria cutoff
    user.item['postCount'] = 6
    user.item['postArchivedCount'] = 0
    user.item['postForcedArchivingCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_posts() is True
    user.item['postCount'] = 0
    user.item['postArchivedCount'] = 6
    user.item['postForcedArchivingCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_posts() is True
    user.item['postCount'] = 2
    user.item['postArchivedCount'] = 4
    user.item['postForcedArchivingCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_posts() is True


def test_is_forced_disabling_criteria_met_by_comments(user):
    # check starting state
    assert user.item.get('commentCount', 0) == 0
    assert user.item.get('commentDeletedCount', 0) == 0
    assert user.item.get('commentForcedDeletionCount', 0) == 0
    assert user.is_forced_disabling_criteria_met_by_comments() is False

    # first comment was force-disabled, shouldn't disable the user
    user.item['commentCount'] = 1
    user.item['commentDeletedCount'] = 0
    user.item['commentForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_comments() is False

    # just below criteria cutoff
    user.item['commentCount'] = 5
    user.item['commentDeletedCount'] = 0
    user.item['commentForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_comments() is False
    user.item['commentCount'] = 3
    user.item['commentDeletedCount'] = 3
    user.item['commentForcedDeletionCount'] = 0
    assert user.is_forced_disabling_criteria_met_by_comments() is False

    # just above criteria cutoff
    user.item['commentCount'] = 6
    user.item['commentDeletedCount'] = 0
    user.item['commentForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_comments() is True
    user.item['commentCount'] = 0
    user.item['commentDeletedCount'] = 6
    user.item['commentForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_comments() is True
    user.item['commentCount'] = 2
    user.item['commentDeletedCount'] = 4
    user.item['commentForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_comments() is True


def test_is_forced_disabling_criteria_met_by_chat_messages(user):
    # check starting state
    assert user.item.get('chatMessagesCreationCount', 0) == 0
    assert user.item.get('chatMessagesForcedDeletionCount', 0) == 0
    assert user.is_forced_disabling_criteria_met_by_chat_messages() is False

    # first comment was force-disabled, shouldn't disable the user
    user.item['chatMessagesCreationCount'] = 1
    user.item['chatMessagesForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_chat_messages() is False

    # just below criteria cutoff
    user.item['chatMessagesCreationCount'] = 5
    user.item['chatMessagesForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_chat_messages() is False

    # just above criteria cutoff
    user.item['chatMessagesCreationCount'] = 6
    user.item['chatMessagesForcedDeletionCount'] = 1
    assert user.is_forced_disabling_criteria_met_by_chat_messages() is True


def test_set_user_accepted_eula_version(user):
    assert 'acceptedEULAVersion' not in user.item

    # set it
    user.set_accepted_eula_version('version-1')
    assert user.item['acceptedEULAVersion'] == 'version-1'
    assert user.refresh_item().item['acceptedEULAVersion'] == 'version-1'

    # no-op set it to same value
    org_item = user.item
    user.set_accepted_eula_version('version-1')
    assert user.item is org_item
    assert user.refresh_item().item['acceptedEULAVersion'] == 'version-1'

    # change value
    user.set_accepted_eula_version('version-2')
    assert user.item['acceptedEULAVersion'] == 'version-2'
    assert user.refresh_item().item['acceptedEULAVersion'] == 'version-2'

    # delete value
    user.set_accepted_eula_version(None)
    assert 'acceptedEULAVersion' not in user.item
    assert 'acceptedEULAVersion' not in user.refresh_item().item

    # no-op delete
    org_item = user.item
    user.set_accepted_eula_version(None)
    assert user.item is org_item
    assert 'acceptedEULAVersion' not in user.refresh_item().item


def test_set_apns_token(user):
    # set the token
    user.pinpoint_client.reset_mock()
    user.set_apns_token('token-1')
    assert user.pinpoint_client.mock_calls == [call.update_user_endpoint(user.id, 'APNS', 'token-1')]

    # delete the token
    user.pinpoint_client.reset_mock()
    user.set_apns_token(None)
    assert user.pinpoint_client.mock_calls == [call.delete_user_endpoint(user.id, 'APNS')]


def test_get_apns_token(user):
    # test not found response
    with patch.object(user, 'pinpoint_client', **{'get_user_endpoints.return_value': {}}) as pc_mock:
        assert user.get_apns_token() is None
    assert pc_mock.mock_calls == [call.get_user_endpoints(user.id, 'APNS')]

    # test found response. A few of these aren't actually uuid4's in reality, just random strings
    address = str(uuid4())
    sample_resp = {
        str(uuid4()): {
            'Address': address,
            'ApplicationId': str(uuid4()),
            'ChannelType': 'APNS',
            'CohortId': '83',
            'CreationDate': '2020-06-10T23:51:30.033Z',
            'EffectiveDate': '2020-06-10T23:51:30.033Z',
            'EndpointStatus': 'ACTIVE',
            'Id': str(uuid4()),
            'OptOut': 'NONE',
            'RequestId': str(uuid4()),
            'User': {'UserId': user.id},
        }
    }
    with patch.object(user, 'pinpoint_client', **{'get_user_endpoints.return_value': sample_resp}) as pc_mock:
        assert user.get_apns_token() == address
    assert pc_mock.mock_calls == [call.get_user_endpoints(user.id, 'APNS')]


def test_set_last_client(user):
    assert 'lastClient' not in user.refresh_item().item
    user.dynamo = Mock(wraps=user.dynamo)

    # set it, verify
    client_1 = {
        'device': 'original razr',
        'system': 'brew',
    }
    with patch.object(user, 'dynamo', Mock(wraps=user.dynamo)) as dynamo_mock:
        user.set_last_client(client_1)
    assert len(dynamo_mock.mock_calls) == 1
    assert user.item == user.refresh_item().item
    assert user.item['lastClient'] == client_1

    # update it, verify
    client_2 = {
        'device': 'original razr',
        'element': 'out of it',
    }
    with patch.object(user, 'dynamo', Mock(wraps=user.dynamo)) as dynamo_mock:
        user.set_last_client(client_2)
    assert len(dynamo_mock.mock_calls) == 1
    assert user.item == user.refresh_item().item
    assert user.item['lastClient'] == client_2

    # verify setting it to the same value does no writes to dynamo
    with patch.object(user, 'dynamo', Mock(wraps=user.dynamo)) as dynamo_mock:
        user.set_last_client(client_2)
    assert dynamo_mock.mock_calls == []
    assert user.item['lastClient'] == client_2


def test_grant_subscription_bonus(user):
    assert user.subscription_level == UserSubscriptionLevel.BASIC
    assert 'subscriptionGrantedAt' not in user.item
    assert 'subscriptionExpiresAt' not in user.item
    sub_duration = pendulum.duration(months=3)

    # grant a subscription
    before = pendulum.now('utc')
    user.grant_subscription_bonus()
    after = pendulum.now('utc')
    assert user.item == user.refresh_item().item
    assert user.subscription_level == UserSubscriptionLevel.DIAMOND
    assert before < pendulum.parse(user.item['subscriptionGrantedAt']) < after
    assert before + sub_duration < pendulum.parse(user.item['subscriptionExpiresAt']) < after + sub_duration

    # clear it (as if it expired)
    user.item = user.dynamo.clear_subscription(user.id)
    assert user.item == user.refresh_item().item
    assert user.subscription_level == UserSubscriptionLevel.BASIC
    assert before < pendulum.parse(user.item['subscriptionGrantedAt']) < after
    assert 'subscriptionExpiresAt' not in user.item

    # verify can't grant it again
    with pytest.raises(UserAlreadyGrantedSubscription):
        user.grant_subscription_bonus()


def test_reset(user):
    # verify starting state
    assert user.refresh_item().status == UserStatus.ACTIVE

    # do the reset, verify congito called to free the user's username
    # note that moto cognito has not yet implemented admin_delete_user_attributes
    with patch.object(user, 'cognito_client') as cognito_client_mock:
        user.reset()
    assert cognito_client_mock.mock_calls == [call.clear_user_attribute(user.id, 'preferred_username')]

    # verify final dynamo state
    assert user.status == UserStatus.RESETTING
    assert user.refresh_item().item is None


def test_delete(user):
    assert user.refresh_item().status == UserStatus.ACTIVE
    user.delete()
    assert user.status == UserStatus.DELETING
    assert user.refresh_item().item is None


def test_link_federated_login_bad_provider(user):
    with pytest.raises(AssertionError, match='not-a-provider'):
        user.link_federated_login('not-a-provider', 'token')


def test_link_federated_login_normal_user(user):
    # set up mocks, save state
    user.cognito_client.get_user_pool_tokens = Mock(return_value={'IdToken': 'cognito-id-token'})
    user.cognito_client.link_identity_pool_entries = Mock()
    org_email = user.item['email']
    assert user.status == UserStatus.ACTIVE

    # call, verify final state
    user.link_federated_login('google', 'google-id-token')
    assert user.item == user.refresh_item().item
    assert user.item['email'] == org_email
    assert user.status == UserStatus.ACTIVE

    # verify mock calls
    assert user.cognito_client.get_user_pool_tokens.mock_calls == [call(user.id)]
    assert user.cognito_client.link_identity_pool_entries.mock_calls == [
        call(user.id, cognito_token='cognito-id-token', google_token='google-id-token')
    ]


def test_link_federated_login_anonymous_user(anonymous_user):
    # set up mocks, save state
    user = anonymous_user
    user.cognito_client.get_user_pool_tokens = Mock(return_value={'IdToken': 'cognito-id-token'})
    user.cognito_client.link_identity_pool_entries = Mock()
    user.cognito_client.set_user_email = Mock()
    user.clients['apple'].get_verified_email = Mock(return_value='xyz@email.com')
    assert 'email' not in user.item
    assert user.status == UserStatus.ANONYMOUS

    # call, verify final state
    user.link_federated_login('apple', 'apple-id-token')
    assert user.item == user.refresh_item().item
    assert user.item['email'] == 'xyz@email.com'
    assert user.status == UserStatus.ACTIVE

    # verify mock calls
    assert user.cognito_client.get_user_pool_tokens.mock_calls == [call(user.id)]
    assert user.cognito_client.link_identity_pool_entries.mock_calls == [
        call(user.id, cognito_token='cognito-id-token', apple_token='apple-id-token')
    ]
    assert user.cognito_client.set_user_email.mock_calls == [call(user.id, 'xyz@email.com')]
    assert user.clients['apple'].get_verified_email.mock_calls == [call('apple-id-token')]


def test_update_last_found_users_at(user):
    # Check update_last_found_users_at without Specific Time
    before = pendulum.now('utc')
    user.update_last_found_users_at()
    after = pendulum.now('utc')
    assert before < pendulum.parse(user.refresh_item().item['lastFoundUsersAt']) < after

    # Check update_last_found_users_at with Specific Time
    now = pendulum.now('utc')
    user.update_last_found_users_at(now)
    assert user.refresh_item().item['lastFoundUsersAt'] == now.to_iso8601_string()


def test_set_user_password_failures(user):
    # it seems boto can raise multiple exceptions for invalid passwords
    err = botocore.exceptions.ParamValidationError(report='foo')
    with patch.object(user.cognito_client, 'set_user_password', side_effect=err):
        with pytest.raises(UserValidationException, match='Invalid password'):
            user.set_password('encryptedfoo')

    err = user.cognito_client.user_pool_client.exceptions.InvalidPasswordException({}, 'bar')
    with patch.object(user.cognito_client, 'set_user_password', side_effect=err):
        with pytest.raises(UserValidationException, match='Invalid password'):
            user.set_password('encryptedfoo')

    err = InvalidEncryption()
    with patch.object(user.cognito_client, 'set_user_password', side_effect=err):
        with pytest.raises(UserException, match='Unable to decrypt'):
            user.set_password('encryptedfoo')


@pytest.mark.parametrize('attr', ['fullName', 'photoPostId', 'gender', 'location', 'matchAgeRange'])
def test_validate_can_enable_dating_missing_attribute(user, attr):
    # set all the required properties, verify succeeds
    user.item.update(
        {
            'fullName': 'HUNTER S',
            'photoPostId': str(uuid4()),
            'age': 42,
            'gender': 'MALE',
            'location': {'latitude': 50, 'longitude': 50, 'accuracy': 10},
            'matchGenders': ['FEMALE'],
            'matchAgeRange': {'min': 20, 'max': 50},
            'matchLocationRadius': 50,
        }
    )
    user.validate_can_enable_dating()

    # remove the attr, verify fails
    user.item.pop(attr)
    with pytest.raises(UserException, match=attr):
        user.validate_can_enable_dating()


def test_validate_can_enable_dating_match_genders(user):
    # set all the required properties except match genders , verify fails
    user.item.update(
        {
            'fullName': 'HUNTER S',
            'photoPostId': str(uuid4()),
            'age': 42,
            'gender': 'MALE',
            'location': {'latitude': 50, 'longitude': 50, 'accuracy': 10},
            'matchAgeRange': {'min': 20, 'max': 50},
            'matchLocationRadius': 50,
        }
    )
    assert 'matchGenders' not in user.item
    with pytest.raises(UserException, match='matchGenders'):
        user.validate_can_enable_dating()

    # set to empty list of match gender, verify fails
    user.item['matchGenders'] = []
    with pytest.raises(UserException, match='matchGenders'):
        user.validate_can_enable_dating()

    # verify success case
    user.item['matchGenders'] = ['MALE']
    user.validate_can_enable_dating()


def test_validate_can_enable_dating_age(user):
    # set all the required properties except age, verify fails
    user.item.update(
        {
            'fullName': 'HUNTER S',
            'photoPostId': str(uuid4()),
            'gender': 'MALE',
            'location': {'latitude': 50, 'longitude': 50, 'accuracy': 10},
            'matchGenders': ['MALE', 'FEMALE'],
            'matchAgeRange': {'min': 20, 'max': 50},
            'matchLocationRadius': 50,
        }
    )
    assert 'age' not in user.item
    with pytest.raises(UserException, match='age'):
        user.validate_can_enable_dating()

    # verify age must be in [18, 100]
    for age in (17, 101):
        user.item['age'] = age
        with pytest.raises(UserException, match='age'):
            user.validate_can_enable_dating()

    # verify success case
    user.item['age'] = 30
    user.validate_can_enable_dating()


def test_validate_can_enable_dating_match_location_radius_not_required_for_diamond(user):
    # set all the required properties except matchLocationRadius, leave as BASIC, verify fails
    user.item.update(
        {
            'fullName': 'HUNTER S',
            'photoPostId': str(uuid4()),
            'gender': 'MALE',
            'age': 30,
            'location': {'latitude': 50, 'longitude': 50, 'accuracy': 10},
            'matchGenders': ['MALE', 'FEMALE'],
            'matchAgeRange': {'min': 20, 'max': 50},
        }
    )
    assert 'subscriptionLEvel' not in user.item
    assert 'matchLocationRadius' not in user.item
    with pytest.raises(UserException, match='matchLocationRadius'):
        user.validate_can_enable_dating()

    # verify success case
    user.item['subscriptionLevel'] = UserSubscriptionLevel.DIAMOND
    user.validate_can_enable_dating()


def test_set_dating_status(user):
    assert 'datingStatus' not in user.item

    # verify set to disabled when disabled is no-op
    with patch.object(user, 'dynamo') as mock_dynamo:
        user.set_dating_status(UserDatingStatus.DISABLED)
    assert mock_dynamo.mock_calls == []
    assert 'datingStatus' not in user.refresh_item().item

    # verify can't enable if validation fails
    with patch.object(user, 'validate_can_enable_dating', side_effect=UserException('nope')):
        with pytest.raises(UserException):
            user.set_dating_status(UserDatingStatus.ENABLED)
    assert 'datingStatus' not in user.refresh_item().item

    # verify enabling success case
    with patch.object(user, 'validate_can_enable_dating'):
        user.set_dating_status(UserDatingStatus.ENABLED)
    assert user.item['datingStatus'] == UserDatingStatus.ENABLED
    assert user.item == user.refresh_item().item

    # verify set to enabled when already enabled is no-op
    with patch.object(user, 'dynamo') as mock_dynamo:
        user.set_dating_status(UserDatingStatus.ENABLED)
    assert mock_dynamo.mock_calls == []
    assert user.refresh_item().item['datingStatus'] == UserDatingStatus.ENABLED

    # verify we can disable without going through validation
    with patch.object(user, 'validate_can_enable_dating', return_value=False):
        user.set_dating_status(UserDatingStatus.DISABLED)
    assert 'datingStatus' not in user.item
    assert user.item == user.refresh_item().item


def test_generate_dating_profile(user):
    # minimal profile
    assert user.generate_dating_profile() == {'serviceLevel': UserSubscriptionLevel.BASIC}

    # maximal profile
    profile = {
        'age': 30,
        'gender': UserGender.MALE,
        'location': {'latitude': 0, 'longitude': 0},
        'matchAgeRange': {'min': 20, 'max': 30},
        'matchGenders': [UserGender.MALE],
        'matchLocationRadius': 50,
        'serviceLevel': UserSubscriptionLevel.DIAMOND,
    }
    user.item.update(profile)
    assert user.generate_dating_profile() == profile
