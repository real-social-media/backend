import logging

import pendulum

from . import enums, exceptions

logger = logging.getLogger()


class ViewModelMixin:

    view_enums = enums
    view_exceptions = exceptions

    def __init__(self, view_dynamo=None, **kwargs):
        super().__init__(**kwargs)
        if view_dynamo:
            self.view_dynamo = view_dynamo

    def get_viewed_status(self, user_id):
        if self.user_id == user_id:  # owner of the item
            return enums.ViewedStatus.VIEWED
        elif self.view_dynamo.get_view(self.id, user_id):
            return enums.ViewedStatus.VIEWED
        else:
            return enums.ViewedStatus.NOT_VIEWED

    def delete_views(self):
        view_item_generator = self.view_dynamo.generate_views(self.id, pks_only=True)
        self.view_dynamo.delete_views(view_item_generator)

    def record_view_count(self, user_id, view_count, viewed_at=None):
        viewed_at = viewed_at or pendulum.now('utc')
        is_first_view_for_user = False
        view_item = self.view_dynamo.get_view(self.id, user_id)
        if view_item:
            self.view_dynamo.increment_view_count(self.id, user_id, view_count, viewed_at)
        else:
            try:
                self.view_dynamo.add_view(self.id, user_id, view_count, viewed_at)
            except exceptions.ViewAlreadyExists:
                # we lost a race condition to add the view, so still need to record our data
                self.view_dynamo.increment_view_count(self.id, user_id, view_count, viewed_at)
            else:
                is_first_view_for_user = True
        return is_first_view_for_user