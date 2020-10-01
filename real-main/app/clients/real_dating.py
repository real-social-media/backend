import json
import logging
import os

import boto3

from app.utils import DecimalJsonEncoder

logger = logging.getLogger()

PUT_USER_ARN = os.environ.get('REAL_DATING_PUT_USER_ARN')
REMOVE_USER_ARN = os.environ.get('REAL_DATING_REMOVE_USER_ARN')
MATCH_STATUS_ARN = os.environ.get('REAL_DATING_MATCH_STATUS_ARN')


class RealDatingClient:
    def __init__(
        self,
        put_user_arn=PUT_USER_ARN,
        remove_user_arn=REMOVE_USER_ARN,
        match_status_arn=MATCH_STATUS_ARN,
    ):
        self.boto3_client = boto3.client('lambda')
        self.put_user_arn = put_user_arn
        self.remove_user_arn = remove_user_arn
        self.match_status_arn = match_status_arn

    def put_user(self, user_id, user_dating_profile):
        self.boto3_client.invoke(
            FunctionName=self.put_user_arn,
            InvocationType='Event',  # async
            Payload=json.dumps({'userId': user_id, **user_dating_profile}, cls=DecimalJsonEncoder),
        )

    def remove_user(self, user_id, fail_soft=False):
        try:
            self.boto3_client.invoke(
                FunctionName=self.remove_user_arn,
                InvocationType='Event',  # async
                Payload=json.dumps({'userId': user_id}),
            )
        except Exception as err:
            if not fail_soft:
                raise err
            logger.warning(f'Unable to remove user from real dating: {err}')

    def match_status(self, user_id, match_user_id):
        self.boto3_client.invoke(
            FunctionName=self.match_user_arn,
            InvocationType='Event',  # async
            Payload=json.dumps({'userId': user_id, 'matchUserId': match_user_id}),
        )
