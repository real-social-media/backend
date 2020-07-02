import logging

from .enums import FollowStatus

logger = logging.getLogger()


class FollowerPostProcessor:
    def __init__(self, user_manager=None):
        self.user_manager = user_manager

    def run(self, pk, sk, old_item, new_item):
        followed_user_id = pk[len('user/') :]
        follower_sk_parts_left = sk[len('follower/') :].split('/')
        follower_user_id = follower_sk_parts_left.pop(0)

        if follower_sk_parts_left == []:
            old_status = old_item['followStatus'] if old_item else FollowStatus.NOT_FOLLOWING
            new_status = new_item['followStatus'] if new_item else FollowStatus.NOT_FOLLOWING

            # incr/decr followedCount and followerCount if follow status changed to/from FOLLOWING
            if old_status != FollowStatus.FOLLOWING and new_status == FollowStatus.FOLLOWING:
                self.user_manager.dynamo.increment_followed_count(follower_user_id)
                self.user_manager.dynamo.increment_follower_count(followed_user_id)
            if old_status == FollowStatus.FOLLOWING and new_status != FollowStatus.FOLLOWING:
                self.user_manager.dynamo.decrement_followed_count(follower_user_id, fail_soft=True)
                self.user_manager.dynamo.decrement_follower_count(followed_user_id, fail_soft=True)

            # incr/decr followersRequestedCount if follow status changed to/from REQUESTED
            if old_status != FollowStatus.REQUESTED and new_status == FollowStatus.REQUESTED:
                self.user_manager.dynamo.increment_followers_requested_count(followed_user_id)
            if old_status == FollowStatus.REQUESTED and new_status != FollowStatus.REQUESTED:
                self.user_manager.dynamo.decrement_followers_requested_count(followed_user_id, fail_soft=True)
