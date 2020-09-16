import json
import os

import boto3

FUNCTION_PREFIX = os.environ.get('REAL_DATING_FUNCTION_PREFIX')


class RealDatingClient:
    def __init__(self, function_prefix=FUNCTION_PREFIX):
        self.boto3_client = boto3.client('lambda')
        self.function_prefix = function_prefix

    def put_user(self, user_item):
        self.boto3_client.invoke(
            FunctionName=f'{self.function_prefix}-put-user',
            InvocationType='Event',  # async
            Payload=json.dumps(user_item),
        )

    def remove_user(self, user_id):
        self.boto3_client.invoke(
            FunctionName=f'{self.function_prefix}-remove-user',
            InvocationType='Event',  # async
            Payload=json.dumps({'userId': user_id}),
        )
