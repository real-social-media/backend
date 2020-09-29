const gql = require('graphql-tag')

const fragments = require('./fragments.js')

module.exports.usernameStatus = gql`
  query UsernameStatus($username: String!) {
    usernameStatus(username: $username)
  }
`

module.exports.self = gql`
  query Self($anonymouslyLikedPostsLimit: Int, $onymouslyLikedPostsLimit: Int, $albumsReverse: Boolean) {
    self {
      userId
      ...SimpleUserFields
      photo {
        ...ImageFragment
      }
      feed {
        items {
          postId
        }
      }
      stories {
        items {
          postId
        }
      }
      posts {
        items {
          postId
        }
      }
      postsWithUnviewedComments {
        items {
          postId
        }
      }
      postsByNewCommentActivity {
        items {
          postId
        }
      }
      anonymouslyLikedPosts(limit: $anonymouslyLikedPostsLimit) {
        items {
          postId
          image {
            url
          }
        }
      }
      onymouslyLikedPosts(limit: $onymouslyLikedPostsLimit) {
        items {
          postId
          image {
            url
          }
        }
      }
      followerUsers {
        items {
          userId
        }
      }
      followedUsers {
        items {
          userId
        }
      }
      followedUsersWithStories {
        items {
          userId
          blockerStatus
          followedStatus
        }
      }
      blockedUsers {
        items {
          userId
          blockedStatus
        }
      }
      albumCount
      albums(reverse: $albumsReverse) {
        items {
          ...AlbumFragment
        }
      }
      cardCount
      cards {
        items {
          ...CardFragment
        }
      }
      chatCount
      chatsWithUnviewedMessagesCount
      chats {
        items {
          ...ChatFragment
        }
      }
      directChat {
        ...ChatFragment
      }
    }
  }
  ${fragments.album}
  ${fragments.card}
  ${fragments.chat}
  ${fragments.image}
  ${fragments.simpleUserFields}
`

module.exports.user = gql`
  query User($userId: ID!) {
    user(userId: $userId) {
      userId
      ...SimpleUserFields
      photo {
        ...ImageFragment
      }
      feed {
        items {
          postId
        }
      }
      stories {
        items {
          postId
        }
      }
      posts {
        items {
          postId
        }
      }
      postsWithUnviewedComments {
        items {
          postId
        }
      }
      postsByNewCommentActivity {
        items {
          postId
        }
      }
      anonymouslyLikedPosts {
        items {
          postId
          image {
            url
          }
        }
      }
      onymouslyLikedPosts {
        items {
          postId
          image {
            url
          }
        }
      }
      followerUsers {
        items {
          userId
        }
      }
      followedUsers {
        items {
          userId
        }
      }
      followedUsersWithStories {
        items {
          userId
        }
      }
      blockedUsers {
        items {
          userId
          blockedStatus
        }
      }
      albumCount
      albums {
        items {
          ...AlbumFragment
        }
      }
      cardCount
      cards {
        items {
          ...CardFragment
        }
      }
      chatCount
      chatsWithUnviewedMessagesCount
      chats {
        items {
          ...ChatFragment
        }
      }
      directChat {
        ...ChatFragment
      }
    }
  }
  ${fragments.album}
  ${fragments.card}
  ${fragments.chat}
  ${fragments.image}
  ${fragments.simpleUserFields}
`

module.exports.searchUsers = gql`
  query SearchUsers($searchToken: String!) {
    searchUsers(searchToken: $searchToken) {
      items {
        userId
        username
        fullName
        photo {
          url
        }
      }
    }
  }
`

module.exports.findUsers = gql`
  query FindUsers($emails: [AWSEmail!], $phoneNumbers: [AWSPhone!]) {
    findUsers(emails: $emails, phoneNumbers: $phoneNumbers) {
      items {
        userId
        username
      }
      nextToken
    }
  }
`

module.exports.post = gql`
  query Post($postId: ID!, $onymouslyLikedByLimit: Int, $commentsReverse: Boolean) {
    post(postId: $postId) {
      postId
      postType
      postStatus
      postedAt
      postedBy {
        userId
        postCount
        blockerStatus
        followedStatus
      }
      expiresAt
      album {
        albumId
      }
      originalPost {
        postId
      }
      text
      textTaggedUsers {
        ...TextTaggedUserFragment
      }
      image {
        ...ImageFragment
      }
      imageUploadUrl
      video {
        ...VideoFragment
      }
      videoUploadUrl
      isVerified
      flagStatus
      likeStatus
      viewedStatus
      commentsDisabled
      commentCount
      commentsCount
      commentsViewedCount: commentsCount(viewedStatus: VIEWED)
      commentsUnviewedCount: commentsCount(viewedStatus: NOT_VIEWED)
      comments(reverse: $commentsReverse) {
        items {
          ...CommentFragment
        }
      }
      likesDisabled
      sharingDisabled
      verificationHidden
      hasNewCommentActivity
      onymousLikeCount
      anonymousLikeCount
      onymouslyLikedBy(limit: $onymouslyLikedByLimit) {
        items {
          userId
        }
      }
      viewedByCount
      viewedBy {
        items {
          userId
          username
        }
      }
    }
  }
  ${fragments.comment}
  ${fragments.image}
  ${fragments.textTaggedUser}
  ${fragments.video}
`

module.exports.postsThree = gql`
  query Posts($postId1: ID!, $postId2: ID!, $postId3: ID!) {
    post1: post(postId: $postId1) {
      postId
      postStatus
    }
    post2: post(postId: $postId2) {
      postId
      postStatus
    }
    post3: post(postId: $postId3) {
      postId
      postStatus
    }
  }
`

module.exports.userPosts = gql`
  query UserPosts($userId: ID!, $postStatus: PostStatus, $postType: PostType) {
    user(userId: $userId) {
      posts(postStatus: $postStatus, postType: $postType) {
        items {
          postId
          postedAt
          postType
          postStatus
          expiresAt
          text
          image {
            url
          }
          postedBy {
            userId
            postCount
            blockerStatus
            followedStatus
          }
        }
      }
    }
  }
`

module.exports.followedUsers = gql`
  query FollowedUsers($userId: ID!, $followStatus: FollowStatus) {
    user(userId: $userId) {
      followedUsers(followStatus: $followStatus) {
        items {
          userId
          followedStatus
          followerStatus
        }
      }
    }
  }
`

module.exports.followerUsers = gql`
  query FollowerUsers($userId: ID!, $followStatus: FollowStatus) {
    user(userId: $userId) {
      followerUsers(followStatus: $followStatus) {
        items {
          userId
          followedStatus
          followerStatus
        }
      }
    }
  }
`

module.exports.ourFollowedUsers = gql`
  query OurFollowedUsers($followStatus: FollowStatus) {
    self {
      followedUsers(followStatus: $followStatus) {
        items {
          userId
          privacyStatus
          fullName
          bio
          email
          phoneNumber
          followedStatus
          followerStatus
        }
      }
    }
  }
`

module.exports.ourFollowerUsers = gql`
  query OurFollowerUsers($followStatus: FollowStatus) {
    self {
      followerUsers(followStatus: $followStatus) {
        items {
          userId
          followedStatus
          followerStatus
        }
      }
    }
  }
`

module.exports.userStories = gql`
  query UserStories($userId: ID!) {
    user(userId: $userId) {
      stories {
        items {
          postId
          postedAt
          postedBy {
            userId
            blockerStatus
            followedStatus
          }
          expiresAt
          text
          image {
            url
          }
        }
      }
    }
  }
`

module.exports.selfFeed = gql`
  query SelfFeed($limit: Int) {
    self {
      feed(limit: $limit) {
        items {
          postId
          postType
          postedBy {
            userId
            blockerStatus
            followedStatus
          }
          text
          image {
            url
          }
          imageUploadUrl
          videoUploadUrl
          onymousLikeCount
          anonymousLikeCount
        }
      }
    }
  }
`

module.exports.trendingUsers = gql`
  query TrendingUsers($limit: Int) {
    trendingUsers(limit: $limit) {
      items {
        userId
        blockerStatus
      }
    }
  }
`

module.exports.trendingPosts = gql`
  query TrendingPosts($limit: Int, $viewedStatus: ViewedStatus, $isVerified: Boolean) {
    trendingPosts(limit: $limit) {
      items(viewedStatus: $viewedStatus, isVerified: $isVerified) {
        postId
        postedBy {
          userId
          privacyStatus
          blockerStatus
          followedStatus
        }
        viewedStatus
      }
    }
  }
`

module.exports.album = gql`
  query Album($albumId: ID!) {
    album(albumId: $albumId) {
      ...AlbumFragment
    }
  }
  ${fragments.album}
`

module.exports.chat = gql`
  query Chat($chatId: ID!, $reverse: Boolean) {
    chat(chatId: $chatId) {
      ...ChatFragment
      messages(reverse: $reverse) {
        items {
          ...ChatMessageFragment
          flagStatus
          viewedStatus
        }
      }
    }
  }
  ${fragments.chat}
  ${fragments.chatMessage}
`

module.exports.chatUsers = gql`
  query Chat($chatId: ID!, $excludeUserId: ID) {
    chat(chatId: $chatId) {
      chatId
      usersCount
      users(excludeUserId: $excludeUserId) {
        items {
          userId
        }
      }
    }
  }
`

module.exports.matchedUsers = gql`
  query MatchedUsers($matchStatus: MatchStatus!) {
    self {
      userId
      matchedUsers(matchStatus: $matchStatus) {
        items {
          userId
        }
      }
    }
  }
`

module.exports.allMatchedUsersForUser = gql`
  query MatchedUsers($userId: ID!) {
    user(userId: $userId) {
      userId
      potentialMatchedUsers: matchedUsers(matchStatus: POTENTIAL) {
        items {
          userId
        }
      }
      rejectedMatchedUsers: matchedUsers(matchStatus: REJECTED) {
        items {
          userId
        }
      }
      approvedMatchedUsers: matchedUsers(matchStatus: APPROVED) {
        items {
          userId
        }
      }
      confirmedMatchedUsers: matchedUsers(matchStatus: CONFIRMED) {
        items {
          userId
        }
      }
    }
  }
`
