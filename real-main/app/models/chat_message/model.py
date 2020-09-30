import json
import logging

import pendulum

from app.mixins.flag.model import FlagModelMixin
from app.models.block.enums import BlockStatus
from app.utils import DecimalJsonEncoder

from .exceptions import ChatMessageException

logger = logging.getLogger()


class ChatMessage(FlagModelMixin):

    item_type = 'chatMessage'

    def __init__(
        self,
        item,
        chat_message_dynamo=None,
        chat_message_appsync=None,
        block_manager=None,
        chat_manager=None,
        user_manager=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.dynamo = chat_message_dynamo
        self.appsync = chat_message_appsync

        self.item = item
        self.block_manager = block_manager
        self.chat_manager = chat_manager
        self.user_manager = user_manager
        # immutables
        self.id = item['messageId']
        self.chat_id = self.item['chatId']
        self.user_id = self.item.get('userId')  # system messages have no userId
        self.created_at = pendulum.parse(self.item['createdAt'])

    @property
    def author(self):
        if not hasattr(self, '_author'):
            self._author = self.user_manager.get_user(self.user_id) if self.user_id else None
        return self._author

    @property
    def chat(self):
        if not hasattr(self, '_chat'):
            self._chat = self.chat_manager.get_chat(self.chat_id) if self.chat_id else None
        return self._chat

    def refresh_item(self, strongly_consistent=False):
        self.item = self.dynamo.get_chat_message(self.id, strongly_consistent=strongly_consistent)
        return self

    def serialize(self, caller_user_id):
        resp = self.item.copy()
        resp['author'] = self.user_manager.get_user(self.user_id).serialize(caller_user_id)
        return resp

    def edit(self, text, now=None):
        now = now or pendulum.now('utc')
        text_tags = self.user_manager.get_text_tags(text)
        self.item = self.dynamo.edit_chat_message(self.id, text, text_tags, now=now)
        return self

    def delete(self, forced=False):
        self.item = self.dynamo.delete_chat_message(self.id)
        if forced:
            self.user_manager.dynamo.increment_chat_messages_forced_deletion_count(self.user_id)
        return self

    def flag(self, user):
        if not self.user_id:
            raise ChatMessageException('Cannot flag system chat message')
        if not self.chat.is_member(user.id):
            raise ChatMessageException(f'User is not part of chat of message `{self.id}`')
        return super().flag(user)

    def trigger_notifications(self, notification_type, user_ids=None):
        """
        Trigger onChatMessageNotification to be sent to clients.

        The `user_ids` parameter can be used to ensure that messages will be
        sent to those user_ids even if they aren't found as members in the DB.
        This is useful when members of the chat have just been added and thus
        dynamo may not have converged yet.
        """
        user_ids = user_ids or []
        already_notified_user_ids = set([self.user_id])  # don't notify the msg author

        for user_id in user_ids:
            if user_id in already_notified_user_ids:
                continue
            self.appsync.trigger_notification(notification_type, user_id, self)
            already_notified_user_ids.add(user_id)

        for user_id in self.chat_manager.member_dynamo.generate_user_ids_by_chat(self.chat_id):
            if user_id in already_notified_user_ids:
                continue
            self.appsync.trigger_notification(notification_type, user_id, self)

    def get_author_encoded(self, user_id):
        """
        Return the author in a serialized, stringified form if they exist and there is no
        blocking relationship between the given user and the author.
        """
        if not self.author:
            return None
        serialized = self.author.serialize(user_id)
        if serialized['blockerStatus'] == BlockStatus.BLOCKING:
            return None
        serialized['blockedStatus'] = self.block_manager.get_block_status(user_id, self.author.id)
        if serialized['blockedStatus'] == BlockStatus.BLOCKING:
            return None
        return json.dumps(serialized, cls=DecimalJsonEncoder)

    def is_crowdsourced_forced_removal_criteria_met(self):
        # force-delete the chat message if at least 10% of the members of the chat have flagged it
        flag_count = self.item.get('flagCount', 0)
        user_count = self.chat.item.get('userCount', 0)
        return flag_count > user_count / 10

    def on_add_or_edit(self, old_item):
        if old_item:
            return
        # we have to do this strongly_consistent because we create the first chat messages
        # in the same request-response cycle as the chat itself
        chat = self.chat_manager.get_chat(self.chat_id, strongly_consistent=True)
        if chat:
            chat.on_message_add(self)
