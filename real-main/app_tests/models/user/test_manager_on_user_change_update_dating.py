from unittest.mock import call, patch
from uuid import uuid4

import pendulum
import pytest

from app.models.user.enums import UserDatingStatus, UserGender
from app.models.user.exceptions import UserException


@pytest.fixture
def user(user_manager, cognito_client):
    user_id, username = str(uuid4()), str(uuid4())[:8]
    cognito_client.create_user_pool_entry(user_id, username, verified_email=f'{username}@real.app')
    yield user_manager.create_cognito_only_user(user_id, username)


def test_on_user_change_update_dating_calls_dating_project_correctly(user_manager, user):
    assert 'datingStatus' not in user.refresh_item().item
    # won't get called for creation of a user with datingStatus DISABLED

    # fire simulating creating a user with dating disabled, verify no calls
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=user.item)
    assert rdc_mock.mock_calls == []

    # fire for adding all the required dating attributes, but don't enable dating, verify no calls
    old_item = user.item.copy()
    user.dynamo.set_user_photo_post_id(user.id, str(uuid4()))
    user.update_details(
        full_name='grant',
        date_of_birth='2000-01-01',
        gender=UserGender.FEMALE,
        location={'latitude': 45, 'longitude': -120},
        match_age_range={'min': 20, 'max': 30},
        match_genders=[UserGender.FEMALE, UserGender.MALE],
        match_location_radius=50,
    )
    user.update_age(now=pendulum.parse('2020-02-02T00:00:00Z'))
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=user.item, old_item=old_item)
    assert rdc_mock.mock_calls == []

    # fire simulating enabling dating, verify dating project called correctly
    old_item = user.item.copy()
    user.set_dating_status(UserDatingStatus.ENABLED)
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=user.item, old_item=old_item)
    assert rdc_mock.mock_calls == [call.put_user(user.id, user.generate_dating_profile())]

    # fire simulating changing attributes not used by dating project, verify no calls
    new_item = {**user.item, 'fullName': 'cat', 'photoPostId': str(uuid4()), 'bio': 'holding steady'}
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=new_item, old_item=user.item)
    assert rdc_mock.mock_calls == []

    # fire simulating changing attributes used by dating project, verify calls dating project
    old_item = {**user.item, 'gender': UserGender.MALE}
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=user.item, old_item=old_item)
    assert rdc_mock.mock_calls == [call.put_user(user.id, user.generate_dating_profile())]

    # fire for disabling, verify calls dating project
    old_item = user.item.copy()
    user.set_dating_status(UserDatingStatus.DISABLED)
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=user.item, old_item=old_item)
    assert rdc_mock.mock_calls == [call.remove_user(user.id)]


def test_on_user_change_update_dating_disables_dating_if_dating_validation_fails(user_manager, user):
    # set all required dating attributes, enable dating
    user.dynamo.set_user_photo_post_id(user.id, str(uuid4()))
    user.update_details(
        full_name='grant',
        date_of_birth='2000-01-01',
        gender=UserGender.FEMALE,
        location={'latitude': 45, 'longitude': -120},
        match_age_range={'min': 20, 'max': 30},
        match_genders=[UserGender.FEMALE, UserGender.MALE],
        match_location_radius=50,
    )
    user.update_age(now=pendulum.parse('2020-02-02T00:00:00Z'))
    user.validate_can_enable_dating()  # verify does not throw
    user.set_dating_status(UserDatingStatus.ENABLED)

    # fire for a change that gets us into a state in which dating if no longer allowed
    # (ie, remove a required attribute)
    old_item = user.item.copy()
    user.update_details(full_name='')
    with pytest.raises(UserException, match='fullName'):
        user.validate_can_enable_dating()
    assert user.item['datingStatus'] == UserDatingStatus.ENABLED
    with patch.object(user_manager, 'real_dating_client') as rdc_mock:
        user_manager.on_user_change_update_dating(user.id, new_item=user.item, old_item=old_item)
    assert rdc_mock.mock_calls == []
    assert 'datingStatus' not in user.refresh_item().item
