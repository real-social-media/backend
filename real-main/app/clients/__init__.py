__all__ = [
    'AppleClient',
    'AppStoreClient',
    'AppSyncClient',
    'CloudFrontClient',
    'CognitoClient',
    'DynamoClient',
    'ElasticSearchClient',
    'FacebookClient',
    'GoogleClient',
    'MediaConvertClient',
    'PinpointClient',
    'PostVerificationClient',
    'RealDatingClient',
    'S3Client',
    'SecretsManagerClient',
]
from .apple import AppleClient
from .appstore import AppStoreClient
from .appsync import AppSyncClient
from .cloudfront import CloudFrontClient
from .cognito import CognitoClient
from .dynamo import DynamoClient
from .elasticsearch import ElasticSearchClient
from .facebook import FacebookClient
from .google import GoogleClient
from .mediaconvert import MediaConvertClient
from .pinpoint import PinpointClient
from .post_verification import PostVerificationClient
from .real_dating import RealDatingClient
from .s3 import S3Client
from .secretsmanager import SecretsManagerClient
