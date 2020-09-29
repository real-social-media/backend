/* GraphQL query fragments */

const gql = require('graphql-tag')

module.exports.chat = gql`
  fragment ChatFragment on Chat {
    chatId
    chatType
    name
    createdAt
    lastMessageActivityAt
    flagStatus
    messageCount
    messagesCount
    messagesViewedCount: messagesCount(viewedStatus: VIEWED)
    messagesUnviewedCount: messagesCount(viewedStatus: NOT_VIEWED)
    userCount
    usersCount
    users {
      items {
        userId
      }
    }
  }
`

module.exports.chatMessage = gql`
  fragment ChatMessageFragment on ChatMessage {
    messageId
    text
    textTaggedUsers {
      tag
      user {
        userId
      }
    }
    createdAt
    lastEditedAt
    chat {
      chatId
    }
    authorUserId
    author {
      userId
      username
      photo {
        url64p
      }
    }
  }
`

module.exports.image = gql`
  fragment ImageFragment on Image {
    url
    url4k
    url1080p
    url480p
    url64p
    width
    height
    colors {
      r
      g
      b
    }
  }
`

module.exports.video = gql`
  fragment VideoFragment on Video {
    urlMasterM3U8
    accessCookies {
      domain
      path
      expiresAt
      policy
      signature
      keyPairId
    }
  }
`

module.exports.album = gql`
  fragment AlbumFragment on Album {
    albumId
    ownedBy {
      userId
    }
    createdAt
    name
    description
    art {
      ...ImageFragment
    }
    postCount
    postsLastUpdatedAt
    posts {
      items {
        postId
      }
    }
  }
  ${module.exports.image}
`

module.exports.card = gql`
  fragment CardFragment on Card {
    cardId
    title
    subTitle
    action
    thumbnail {
      ...ImageFragment
    }
  }
  ${module.exports.image}
`

module.exports.comment = gql`
  fragment CommentFragment on Comment {
    commentId
    commentedAt
    commentedBy {
      userId
    }
    text
    textTaggedUsers {
      tag
      user {
        userId
        username
      }
    }
    viewedStatus
    flagStatus
  }
`

module.exports.textTaggedUser = gql`
  fragment TextTaggedUserFragment on TextTaggedUser {
    tag
    user {
      userId
      username
    }
  }
`

module.exports.simpleUserFields = gql`
  fragment SimpleUserFields on User {
    username
    fullName
    bio
    email
    phoneNumber
    dateOfBirth
    gender
    privacyStatus
    postCount
    followedStatus
    followerStatus
    followCountsHidden
    followedCount
    followedsCount
    followerCount
    followersCount
    followersRequestedCount: followersCount(followStatus: REQUESTED)
    languageCode
    themeCode
    blockedStatus
    blockerStatus
    acceptedEULAVersion
    commentsDisabled
    likesDisabled
    sharingDisabled
    verificationHidden
    postViewedByCount
    viewCountsHidden
    signedUpAt
    userStatus
    subscriptionLevel
    subscriptionExpiresAt
    lastFoundUsersAt
    matchGenders
    matchLocationRadius
    location {
      latitude
      longitude
      accuracy
    }
    matchAgeRange {
      min
      max
    }
    datingStatus
    matchStatus
  }
`
