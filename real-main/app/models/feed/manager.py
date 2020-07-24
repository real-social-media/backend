import itertools
import logging

from app import models
from app.models.follower.enums import FollowStatus
from app.models.post.enums import PostStatus

from .dynamo import FeedDynamo

logger = logging.getLogger()


class FeedManager:
    def __init__(self, clients, managers=None):
        managers = managers or {}
        managers['feed'] = self
        self.follower_manager = managers.get('follower') or models.FollowerManager(clients, managers=managers)
        self.post_manager = managers.get('post') or models.PostManager(clients, managers=managers)

        self.clients = clients
        if 'dynamo' in clients:
            self.dynamo = FeedDynamo(clients['dynamo'])

    def add_users_posts_to_feed(self, feed_user_id, posted_by_user_id):
        post_item_generator = self.post_manager.dynamo.generate_posts_by_user(posted_by_user_id, completed=True)
        self.dynamo.add_posts_to_feed(feed_user_id, post_item_generator)

    def add_post_to_followers_feeds(self, followed_user_id, post_item):
        user_id_gen = itertools.chain(
            [followed_user_id], self.follower_manager.generate_follower_user_ids(followed_user_id)
        )
        self.dynamo.add_post_to_feeds(user_id_gen, post_item)

    def delete_post_from_followers_feeds(self, followed_user_id, post_id):
        # TODO: add an index to the feed, delete this method entirely
        user_id_gen = itertools.chain(
            [followed_user_id], self.follower_manager.generate_follower_user_ids(followed_user_id)
        )
        self.dynamo.delete_by_post(post_id, user_id_gen)

    def on_user_follow_status_change_sync_feed(self, followed_user_id, new_item=None, old_item=None):
        follower_user_id = (new_item or old_item)['followerUserId']
        new_status = (new_item or {}).get('followStatus', FollowStatus.NOT_FOLLOWING)
        if new_status == FollowStatus.FOLLOWING:
            self.add_users_posts_to_feed(follower_user_id, followed_user_id)
        else:
            self.dynamo.delete_by_post_owner(follower_user_id, followed_user_id)

    def on_post_status_change_sync_feed(self, post_id, new_item=None, old_item=None):
        posted_by_user_id = (new_item or old_item)['postedByUserId']
        new_status = (new_item or {}).get('postStatus')
        old_status = (old_item or {}).get('postStatus')
        if new_status == PostStatus.COMPLETED:
            self.add_post_to_followers_feeds(posted_by_user_id, new_item)
        elif old_status == PostStatus.COMPLETED:
            # TODO: remove above check on old_status once index on post_id added to feed items
            self.delete_post_from_followers_feeds(posted_by_user_id, post_id)
