import base64
import uuid
from os import path
from unittest import mock

import moto
import pytest

from app import clients, models
from app.models.card.templates import CardTemplate

from .dynamodb.table_schema import feed_table_schema, main_table_schema

heic_path = path.join(path.dirname(__file__), 'fixtures', 'IMG_0265.HEIC')
grant_path = path.join(path.dirname(__file__), 'fixtures', 'grant.jpg')
tiny_path = path.join(path.dirname(__file__), 'fixtures', 'tiny.jpg')


@pytest.fixture
def image_data():
    with open(tiny_path, 'rb') as fh:
        yield fh.read()


@pytest.fixture
def image_data_b64(image_data):
    yield base64.b64encode(image_data)


@pytest.fixture
def grant_data():
    with open(grant_path, 'rb') as fh:
        yield fh.read()


@pytest.fixture
def grant_data_b64(grant_data):
    yield base64.b64encode(grant_data)


@pytest.fixture
def heic_data():
    with open(heic_path, 'rb') as fh:
        yield fh.read()


@pytest.fixture
def heic_data_b64(heic_data):
    yield base64.b64encode(heic_data)


@pytest.fixture
def heic_dims():
    # (widith, height) of the 'heic_data' image
    yield (4032, 3024)


@pytest.fixture
def appsync_client():
    yield mock.Mock(clients.AppSyncClient(appsync_graphql_url='my-graphql-url'))


@pytest.fixture
def cloudfront_client():
    yield mock.Mock(clients.CloudFrontClient(None, 'my-domain'))


@pytest.fixture
def mediaconvert_client():
    endpoint = 'https://my-media-convert-endpoint.com'
    yield mock.Mock(
        clients.MediaConvertClient(
            endpoint=endpoint, aws_account_id='aws-aid', role_arn='role-arn', uploads_bucket='uploads-bucket'
        )
    )


@pytest.fixture
def post_verification_client():
    # by default, all images pass verification
    yield mock.Mock(clients.PostVerificationClient(lambda: None), **{'verify_image.return_value': True})


@pytest.fixture
def cognito_client():
    with moto.mock_cognitoidp():
        # https://github.com/spulec/moto/blob/80b64f9b3ff5/tests/test_cognitoidp/test_cognitoidp.py#L1133
        cognito_client = clients.CognitoClient('dummy', 'dummy')
        cognito_client.user_pool_id = cognito_client.user_pool_client.create_user_pool(
            PoolName=str(uuid.uuid4()),
            AliasAttributes=[
                'phone_number',
                'email',
                'preferred_username',
            ],  # seems moto doesn't enforce uniqueness
        )['UserPool']['Id']
        cognito_client.client_id = cognito_client.user_pool_client.create_user_pool_client(
            UserPoolId=cognito_client.user_pool_id,
            ClientName=str(uuid.uuid4()),
            ReadAttributes=['email', 'phone_number'],
        )['UserPoolClient']['ClientId']
        cognito_client.identity_pool_client = mock.Mock(cognito_client.identity_pool_client)
        cognito_client.user_pool_client.admin_set_user_password = mock.Mock()
        yield cognito_client


@pytest.fixture
def dynamo_clients():
    with moto.mock_dynamodb2():
        yield (
            clients.DynamoClient(table_name='main-table', create_table_schema=main_table_schema),
            clients.DynamoClient(table_name='feed-table', create_table_schema=feed_table_schema),
        )


@pytest.fixture
def dynamo_client(dynamo_clients):
    yield dynamo_clients[0]


@pytest.fixture
def dynamo_feed_client(dynamo_clients):
    yield dynamo_clients[1]


@pytest.fixture
def elasticsearch_client():
    yield mock.Mock(clients.ElasticSearchClient(domain='my-es-domain.com'))


@pytest.fixture
def appstore_client():
    yield mock.Mock(clients.AppStoreClient(lambda: {'bundleId': '-', 'sharedSecret': '-'}))


@pytest.fixture
def apple_client():
    yield mock.Mock(clients.AppleClient())


@pytest.fixture
def facebook_client():
    yield mock.Mock(clients.FacebookClient())


@pytest.fixture
def google_client():
    yield mock.Mock(clients.GoogleClient(lambda: {}))


@pytest.fixture
def real_dating_client():
    yield mock.Mock(clients.RealDatingClient())


@pytest.fixture
def pinpoint_client():
    yield mock.Mock(clients.PinpointClient(app_id='my-app-id'))


# can't nest the moto context managers, it appears. To be able to use two mocked S3 buckets
# they thus need to be yielded under the same context manager
@pytest.fixture
def s3_clients():
    with moto.mock_s3():
        yield {
            'uploads': clients.S3Client(bucket_name='uploads-bucket', create_bucket=True),
            'placeholder-photos': clients.S3Client(bucket_name='placerholder-photos-bucket', create_bucket=True),
        }


@pytest.fixture
def s3_uploads_client(s3_clients):
    yield s3_clients['uploads']


@pytest.fixture
def s3_placeholder_photos_client(s3_clients):
    yield s3_clients['placeholder-photos']


@pytest.fixture
def album_manager(dynamo_client, s3_uploads_client, cloudfront_client):
    yield models.AlbumManager(
        {'dynamo': dynamo_client, 's3_uploads': s3_uploads_client, 'cloudfront': cloudfront_client}
    )


@pytest.fixture
def appstore_manager(appstore_client, dynamo_client):
    yield models.AppStoreManager({'appstore': appstore_client, 'dynamo': dynamo_client})


@pytest.fixture
def block_manager(dynamo_client):
    yield models.BlockManager({'dynamo': dynamo_client})


@pytest.fixture
def card_manager(dynamo_client, appsync_client, pinpoint_client):
    yield models.CardManager({'appsync': appsync_client, 'dynamo': dynamo_client, 'pinpoint': pinpoint_client})


@pytest.fixture
def TestCardTemplate():
    class TestCardTemplate(CardTemplate):
        def __init__(self, user_id, **kwargs):
            super().__init__(user_id)
            self.card_id = str(uuid.uuid4())
            for k, v in kwargs.items():
                setattr(self, k, v)

    yield TestCardTemplate


@pytest.fixture
def chat_manager(dynamo_client, appsync_client):
    yield models.ChatManager({'appsync': appsync_client, 'dynamo': dynamo_client})


@pytest.fixture
def chat_message_manager(dynamo_client, appsync_client, cloudfront_client):
    yield models.ChatMessageManager(
        {'appsync': appsync_client, 'cloudfront': cloudfront_client, 'dynamo': dynamo_client}
    )


@pytest.fixture
def comment_manager(dynamo_client, user_manager, appsync_client):
    yield models.CommentManager(
        {'appsync': appsync_client, 'dynamo': dynamo_client}, managers={'user': user_manager}
    )


@pytest.fixture
def feed_manager(appsync_client, dynamo_client, dynamo_feed_client):
    yield models.FeedManager(
        {'appsync': appsync_client, 'dynamo': dynamo_client, 'dynamo_feed': dynamo_feed_client}
    )


@pytest.fixture
def follower_manager(dynamo_client):
    yield models.FollowerManager({'appsync': appsync_client, 'dynamo': dynamo_client})


@pytest.fixture
def like_manager(dynamo_client):
    yield models.LikeManager({'dynamo': dynamo_client})


@pytest.fixture
def post_manager(appsync_client, dynamo_client, s3_uploads_client, cloudfront_client, post_verification_client):
    yield models.PostManager(
        {
            'appsync': appsync_client,
            'dynamo': dynamo_client,
            's3_uploads': s3_uploads_client,
            'cloudfront': cloudfront_client,
            'post_verification': post_verification_client,
        }
    )


@pytest.fixture
def screen_manager(dynamo_client):
    yield models.ScreenManager({'dynamo': dynamo_client})


@pytest.fixture
def user_manager(
    appsync_client,
    cloudfront_client,
    dynamo_client,
    s3_uploads_client,
    s3_placeholder_photos_client,
    cognito_client,
    apple_client,
    facebook_client,
    google_client,
    pinpoint_client,
    elasticsearch_client,
    real_dating_client,
):
    yield models.UserManager(
        {
            'appsync': appsync_client,
            'cloudfront': cloudfront_client,
            'dynamo': dynamo_client,
            's3_uploads': s3_uploads_client,
            's3_placeholder_photos': s3_placeholder_photos_client,
            'cognito': cognito_client,
            'apple': apple_client,
            'facebook': facebook_client,
            'google': google_client,
            'pinpoint': pinpoint_client,
            'elasticsearch': elasticsearch_client,
            'real_dating': real_dating_client,
        }
    )
