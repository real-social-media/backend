import logging

import pendulum

from . import enums, exceptions, specs

logger = logging.getLogger()


class Card:

    enums = enums
    exceptions = exceptions

    def __init__(self, item, card_appsync=None, card_dynamo=None, post_manager=None, user_manager=None):
        self.appsync = card_appsync
        self.dynamo = card_dynamo
        self.post_manager = post_manager
        self.user_manager = user_manager

        self.item = item
        # immutables
        self.id = item['partitionKey'][len('card/') :]
        self.user_id = item['gsiA1PartitionKey'][len('user/') :]
        self.created_at = pendulum.parse(item['gsiA1SortKey'][len('card/') :])
        self.spec = specs.CardSpec.from_card_id(self.id)

    @property
    def user(self):
        if not hasattr(self, '_user'):
            self._user = self.user_manager.get_user(self.user_id) if self.user_id else None
        return self._user

    @property
    def post(self):
        if not hasattr(self, '_post'):
            post_id = self.spec.post_id if self.spec else None
            self._post = self.post_manager.get_post(post_id) if post_id else None
        return self._post

    @property
    def has_thumbnail(self):
        return bool(self.spec and self.spec.post_id)

    def refresh_item(self, strongly_consistent=False):
        self.item = self.dynamo.get_card(self.id, strongly_consistent=strongly_consistent)
        return self

    def serialize(self, caller_user_id):
        resp = self.item.copy()
        resp['cardId'] = self.id
        return resp

    def get_image_url(self, size):
        return self.post.get_image_readonly_url(size) if self.post else None

    def delete(self):
        transacts = [
            self.dynamo.transact_delete_card(self.id),
            self.user_manager.dynamo.transact_card_deleted(self.user_id),
        ]
        transact_exceptions = [
            self.exceptions.CardDoesNotExist(self.id),
            self.exceptions.CardException('Unable to register card deleted on user item'),
        ]
        self.dynamo.client.transact_write_items(transacts, transact_exceptions)
        self.appsync.trigger_notification(enums.CardNotificationType.DELETED, self)
        return self