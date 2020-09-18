const gql = require('graphql-tag')

const fragments = require('./fragments.js')

module.exports.createAnonymousUser = gql`
  mutation CreateAnonymousUser {
    createAnonymousUser {
      AccessToken
      ExpiresIn
      TokenType
      RefreshToken
      IdToken
    }
  }
`

module.exports.createCognitoOnlyUser = gql`
  mutation CreateCognitoOnlyUser($username: String!, $fullName: String) {
    createCognitoOnlyUser(username: $username, fullName: $fullName) {
      userId
      username
      fullName
      email
      phoneNumber
      signedUpAt
    }
  }
`

module.exports.createAppleUser = gql`
  mutation CreateAppleUser($username: String!, $fullName: String, $appleIdToken: String!) {
    createAppleUser(username: $username, fullName: $fullName, appleIdToken: $appleIdToken) {
      userId
      username
      fullName
      email
    }
  }
`

module.exports.createFacebookUser = gql`
  mutation CreateFacebookUser($username: String!, $fullName: String, $facebookAccessToken: String!) {
    createFacebookUser(username: $username, fullName: $fullName, facebookAccessToken: $facebookAccessToken) {
      userId
      username
      fullName
      email
    }
  }
`

module.exports.createGoogleUser = gql`
  mutation CreateGoogleUser($username: String!, $fullName: String, $googleIdToken: String!) {
    createGoogleUser(username: $username, fullName: $fullName, googleIdToken: $googleIdToken) {
      userId
      username
      fullName
      email
    }
  }
`

module.exports.setPassword = gql`
  mutation SetPassword($encryptedPassword: String!) {
    setUserPassword(encryptedPassword: $encryptedPassword) {
      userId
      username
    }
  }
`

module.exports.setUsername = gql`
  mutation SetUsername($username: String!) {
    setUserDetails(username: $username) {
      userId
      username
    }
  }
`

module.exports.setUserPrivacyStatus = gql`
  mutation SetUserPrivacyStatus($privacyStatus: PrivacyStatus!) {
    setUserDetails(privacyStatus: $privacyStatus) {
      userId
      privacyStatus
      followedCount
      followerCount
    }
  }
`

module.exports.setUserAcceptedEULAVersion = gql`
  mutation SetUserEULAVersion($version: String!) {
    setUserAcceptedEULAVersion(version: $version) {
      userId
      acceptedEULAVersion
    }
  }
`

module.exports.setUserAPNSToken = gql`
  mutation SetUserAPNSToken($token: String!) {
    setUserAPNSToken(token: $token) {
      userId
    }
  }
`

module.exports.setUserFollowCountsHidden = gql`
  mutation SetUserFollowCountsHidden($value: Boolean!) {
    setUserDetails(followCountsHidden: $value) {
      userId
      followCountsHidden
    }
  }
`

module.exports.setUserViewCountsHidden = gql`
  mutation SetUserViewCountsHidden($value: Boolean!) {
    setUserDetails(viewCountsHidden: $value) {
      userId
      viewCountsHidden
    }
  }
`

module.exports.setUserDetails = gql`
  mutation SetUserDetails(
    $bio: String
    $fullName: String
    $photoPostId: ID
    $username: String
    $dateOfBirth: AWSDate
    $gender: UserGender
    $location: LocationInput
    $matchAgeRange: AgeRangeInput
    $matchGenders: [UserGender!]
    $matchLocationRadius: Int
  ) {
    setUserDetails(
      bio: $bio
      fullName: $fullName
      photoPostId: $photoPostId
      username: $username
      dateOfBirth: $dateOfBirth
      gender: $gender
      location: $location
      matchAgeRange: $matchAgeRange
      matchGenders: $matchGenders
      matchLocationRadius: $matchLocationRadius
    ) {
      userId
      username
      bio
      fullName
      photo {
        ...ImageFragment
      }
      dateOfBirth
      gender
      matchGenders
      matchLocationRadius
    }
  }
  ${fragments.image}
`

module.exports.setUserLanguageCode = gql`
  mutation SetUserLanguageCode($languageCode: String) {
    setUserDetails(languageCode: $languageCode) {
      userId
      languageCode
    }
  }
`

module.exports.setUserThemeCode = gql`
  mutation SetUserThemeCode($themeCode: String) {
    setUserDetails(themeCode: $themeCode) {
      userId
      themeCode
    }
  }
`

module.exports.setUserMentalHealthSettings = gql`
  mutation SetUserCommentsDisabled(
    $commentsDisabled: Boolean
    $likesDisabled: Boolean
    $sharingDisabled: Boolean
    $verificationHidden: Boolean
  ) {
    setUserDetails(
      commentsDisabled: $commentsDisabled
      likesDisabled: $likesDisabled
      sharingDisabled: $sharingDisabled
      verificationHidden: $verificationHidden
    ) {
      userId
      commentsDisabled
      likesDisabled
      sharingDisabled
      verificationHidden
    }
  }
`

module.exports.setUserLocation = gql`
  mutation SetUserLocation($latitude: Float!, $longitude: Float!, $accuracy: Int) {
    setUserDetails(location: {latitude: $latitude, longitude: $longitude, accuracy: $accuracy}) {
      userId
      location {
        latitude
        longitude
        accuracy
      }
    }
  }
`

module.exports.setUserAgeRange = gql`
  mutation SetUserAgeRange($min: Int, $max: Int) {
    setUserDetails(matchAgeRange: {min: $min, max: $max}) {
      userId
      matchAgeRange {
        min
        max
      }
    }
  }
`

module.exports.setUserDatingStatus = gql`
  mutation SetUserDatingStatus($status: DatingStatus!) {
    setUserDatingStatus(status: $status) {
      userId
      datingStatus
    }
  }
`

module.exports.updateUserContactInfo = gql`
  mutation SetUserContactInfo($accessToken: String!) {
    updateUserContactInfo(authProvider: COGNITO, accessToken: $accessToken) {
      userId
      email
      phoneNumber
    }
  }
`

module.exports.disableUser = gql`
  mutation DisableUser {
    disableUser {
      userId
      username
      userStatus
    }
  }
`

module.exports.deleteUser = gql`
  mutation DeleteUser {
    deleteUser {
      userId
      username
      userStatus
    }
  }
`

module.exports.grantUserSubscriptionBonus = gql`
  mutation GrantUserSubscriptionBonus {
    grantUserSubscriptionBonus {
      userId
      subscriptionLevel
      subscriptionExpiresAt
    }
  }
`

module.exports.addAppStoreReceipt = gql`
  mutation AddAppStoreReceipt($receiptData: String!) {
    addAppStoreReceipt(receiptData: $receiptData)
  }
`

module.exports.resetUser = gql`
  mutation ResetUser($newUsername: String) {
    resetUser(newUsername: $newUsername) {
      userId
      username
      fullName
      userStatus
    }
  }
`

module.exports.followUser = gql`
  mutation FollowUser($userId: ID!) {
    followUser(userId: $userId) {
      userId
      followedStatus
      followerCount
    }
  }
`

module.exports.unfollowUser = gql`
  mutation UnfollowUser($userId: ID!) {
    unfollowUser(userId: $userId) {
      userId
      followedStatus
      followerCount
    }
  }
`

module.exports.acceptFollowerUser = gql`
  mutation AcceptFollowerUser($userId: ID!) {
    acceptFollowerUser(userId: $userId) {
      userId
      followerStatus
      followedCount
    }
  }
`

module.exports.denyFollowerUser = gql`
  mutation DenyFollowerUser($userId: ID!) {
    denyFollowerUser(userId: $userId) {
      userId
      followerStatus
      followedCount
    }
  }
`

module.exports.blockUser = gql`
  mutation BlockUser($userId: ID!) {
    blockUser(userId: $userId) {
      userId
      blockedStatus
    }
  }
`

module.exports.unblockUser = gql`
  mutation UnblockUser($userId: ID!) {
    unblockUser(userId: $userId) {
      userId
      blockedStatus
    }
  }
`

module.exports.addPost = gql`
  mutation AddPost(
    $postId: ID!
    $postType: PostType
    $albumId: ID
    $text: String
    $imageData: String
    $takenInReal: Boolean
    $imageFormat: ImageFormat
    $originalFormat: String
    $originalMetadata: String
    $lifetime: String
    $commentsDisabled: Boolean
    $likesDisabled: Boolean
    $sharingDisabled: Boolean
    $verificationHidden: Boolean
    $setAsUserPhoto: Boolean
    $crop: CropInput
  ) {
    addPost(
      postId: $postId
      postType: $postType
      albumId: $albumId
      text: $text
      imageInput: {
        takenInReal: $takenInReal
        imageFormat: $imageFormat
        originalFormat: $originalFormat
        originalMetadata: $originalMetadata
        imageData: $imageData
        crop: $crop
      }
      lifetime: $lifetime
      commentsDisabled: $commentsDisabled
      likesDisabled: $likesDisabled
      sharingDisabled: $sharingDisabled
      verificationHidden: $verificationHidden
      setAsUserPhoto: $setAsUserPhoto
    ) {
      postId
      postedAt
      postType
      postStatus
      expiresAt
      verificationHidden
      image {
        url
        url4k
      }
      imageUploadUrl
      videoUploadUrl
      isVerified
      viewedStatus
      text
      textTaggedUsers {
        ...TextTaggedUserFragment
      }
      image {
        ...ImageFragment
      }
      album {
        albumId
      }
      originalPost {
        postId
      }
      postedBy {
        userId
        postCount
        blockerStatus
        followedStatus
      }
      commentsDisabled
      commentCount
      commentsCount
      comments {
        items {
          ...CommentFragment
        }
      }
      likesDisabled
      sharingDisabled
      verificationHidden
      hasNewCommentActivity
      flagStatus
    }
  }
  ${fragments.comment}
  ${fragments.image}
  ${fragments.textTaggedUser}
`

module.exports.editPost = gql`
  mutation EditPost(
    $postId: ID!
    $text: String
    $commentsDisabled: Boolean
    $likesDisabled: Boolean
    $sharingDisabled: Boolean
    $verificationHidden: Boolean
  ) {
    editPost(
      postId: $postId
      text: $text
      commentsDisabled: $commentsDisabled
      likesDisabled: $likesDisabled
      sharingDisabled: $sharingDisabled
      verificationHidden: $verificationHidden
    ) {
      postId
      postStatus
      postedBy {
        userId
        postCount
        blockerStatus
        followedStatus
      }
      text
      textTaggedUsers {
        ...TextTaggedUserFragment
      }
      image {
        url
      }
      commentsDisabled
      likesDisabled
      sharingDisabled
      verificationHidden
    }
  }
  ${fragments.textTaggedUser}
`

module.exports.editPostAlbum = gql`
  mutation EditPostAlbum($postId: ID!, $albumId: ID) {
    editPostAlbum(postId: $postId, albumId: $albumId) {
      postId
      album {
        albumId
      }
    }
  }
`

module.exports.editPostAlbumOrder = gql`
  mutation EditPostAlbumOrder($postId: ID!, $precedingPostId: ID) {
    editPostAlbumOrder(postId: $postId, precedingPostId: $precedingPostId) {
      postId
      album {
        albumId
      }
    }
  }
`

module.exports.editPostExpiresAt = gql`
  mutation EditPostExpiresAt($postId: ID!, $expiresAt: AWSDateTime) {
    editPostExpiresAt(postId: $postId, expiresAt: $expiresAt) {
      postId
      expiresAt
    }
  }
`

module.exports.flagPost = gql`
  mutation FlagPost($postId: ID!) {
    flagPost(postId: $postId) {
      postId
      postStatus
      flagStatus
    }
  }
`

module.exports.deletePost = gql`
  mutation DeletePost($postId: ID!) {
    deletePost(postId: $postId) {
      postId
      postStatus
    }
  }
`

module.exports.archivePost = gql`
  mutation ArchivePost($postId: ID!) {
    archivePost(postId: $postId) {
      postId
      postStatus
      postedBy {
        userId
        postCount
        blockerStatus
        followedStatus
      }
      image {
        url
      }
      imageUploadUrl
      videoUploadUrl
    }
  }
`

module.exports.restoreArchivedPost = gql`
  mutation RestoreArchivePost($postId: ID!) {
    restoreArchivedPost(postId: $postId) {
      postId
      postStatus
      postedBy {
        userId
        postCount
        blockerStatus
        followedStatus
      }
      image {
        url
      }
    }
  }
`

module.exports.onymouslyLikePost = gql`
  mutation OnymouslyLikePost($postId: ID!) {
    onymouslyLikePost(postId: $postId) {
      postId
      likeStatus
      onymousLikeCount
      anonymousLikeCount
      onymouslyLikedBy {
        items {
          userId
        }
      }
    }
  }
`

module.exports.anonymouslyLikePost = gql`
  mutation AnonymouslyLikePost($postId: ID!) {
    anonymouslyLikePost(postId: $postId) {
      postId
      likeStatus
      onymousLikeCount
      anonymousLikeCount
      onymouslyLikedBy {
        items {
          userId
        }
      }
    }
  }
`

module.exports.dislikePost = gql`
  mutation DislikePost($postId: ID!) {
    dislikePost(postId: $postId) {
      postId
      likeStatus
      onymousLikeCount
      anonymousLikeCount
      onymouslyLikedBy {
        items {
          userId
        }
      }
    }
  }
`

module.exports.reportPostViews = gql`
  mutation ReportPostViews($postIds: [ID!]!, $viewType: ViewType) {
    reportPostViews(postIds: $postIds, viewType: $viewType)
  }
`

module.exports.reportScreenViews = gql`
  mutation ReportScreenViews($screens: [String!]!) {
    reportScreenViews(screens: $screens)
  }
`

module.exports.deleteCard = gql`
  mutation DeleteCard($cardId: ID!) {
    deleteCard(cardId: $cardId) {
      ...CardFragment
    }
  }
  ${fragments.card}
`

module.exports.addComment = gql`
  mutation AddComment($commentId: ID!, $postId: ID!, $text: String!) {
    addComment(commentId: $commentId, postId: $postId, text: $text) {
      ...CommentFragment
    }
  }
  ${fragments.comment}
`

module.exports.deleteComment = gql`
  mutation DeleteComment($commentId: ID!) {
    deleteComment(commentId: $commentId) {
      ...CommentFragment
    }
  }
  ${fragments.comment}
`

module.exports.flagComment = gql`
  mutation FlagComment($commentId: ID!) {
    flagComment(commentId: $commentId) {
      commentId
      flagStatus
    }
  }
`

module.exports.addAlbum = gql`
  mutation AddAlbum($albumId: ID!, $name: String!, $description: String) {
    addAlbum(albumId: $albumId, name: $name, description: $description) {
      ...AlbumFragment
    }
  }
  ${fragments.album}
`

module.exports.editAlbum = gql`
  mutation EditAlbum($albumId: ID!, $name: String, $description: String) {
    editAlbum(albumId: $albumId, name: $name, description: $description) {
      ...AlbumFragment
    }
  }
  ${fragments.album}
`

module.exports.deleteAlbum = gql`
  mutation DeleteAlbum($albumId: ID!) {
    deleteAlbum(albumId: $albumId) {
      ...AlbumFragment
    }
  }
  ${fragments.album}
`

module.exports.createDirectChat = gql`
  mutation CreateDirectChat($chatId: ID!, $userId: ID!, $messageId: ID!, $messageText: String!) {
    createDirectChat(chatId: $chatId, userId: $userId, messageId: $messageId, messageText: $messageText) {
      ...ChatFragment
      messages {
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

module.exports.createGroupChat = gql`
  mutation CreateGroupChat(
    $chatId: ID!
    $name: String
    $userIds: [ID!]!
    $messageId: ID!
    $messageText: String!
  ) {
    createGroupChat(
      chatId: $chatId
      name: $name
      userIds: $userIds
      messageId: $messageId
      messageText: $messageText
    ) {
      ...ChatFragment
      messages {
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

module.exports.editGroupChat = gql`
  mutation EditGroupChat($chatId: ID!, $name: String!) {
    editGroupChat(chatId: $chatId, name: $name) {
      ...ChatFragment
      messages {
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

module.exports.addToGroupChat = gql`
  mutation AddToGroupChat($chatId: ID!, $userIds: [ID!]!) {
    addToGroupChat(chatId: $chatId, userIds: $userIds) {
      ...ChatFragment
      messages {
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

module.exports.leaveGroupChat = gql`
  mutation LeaveGroupChat($chatId: ID!) {
    leaveGroupChat(chatId: $chatId) {
      ...ChatFragment
      messages {
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

module.exports.reportChatViews = gql`
  mutation ReportChatViews($chatIds: [ID!]!) {
    reportChatViews(chatIds: $chatIds)
  }
`

module.exports.flagChat = gql`
  mutation FlagChat($chatId: ID!) {
    flagChat(chatId: $chatId) {
      chatId
      flagStatus
    }
  }
`

module.exports.addChatMessage = gql`
  mutation AddChatMessage($chatId: ID!, $messageId: ID!, $text: String!) {
    addChatMessage(chatId: $chatId, messageId: $messageId, text: $text) {
      ...ChatMessageFragment
      flagStatus
      viewedStatus
    }
  }
  ${fragments.chatMessage}
`

module.exports.editChatMessage = gql`
  mutation EditChatMessage($messageId: ID!, $text: String!) {
    editChatMessage(messageId: $messageId, text: $text) {
      ...ChatMessageFragment
      flagStatus
      viewedStatus
    }
  }
  ${fragments.chatMessage}
`

module.exports.deleteChatMessage = gql`
  mutation DeleteChatMessage($messageId: ID!) {
    deleteChatMessage(messageId: $messageId) {
      ...ChatMessageFragment
      flagStatus
      viewedStatus
    }
  }
  ${fragments.chatMessage}
`

module.exports.flagChatMessage = gql`
  mutation FlagChatMessage($messageId: ID!) {
    flagChatMessage(messageId: $messageId) {
      messageId
      flagStatus
    }
  }
`

module.exports.rejectMatch = gql`
  mutation RejectMatch($userId: ID!) {
    rejectMatch(userId: $userId)
  }
`

module.exports.approveMatch = gql`
  mutation ApproveMatch($userId: ID!) {
    approveMatch(userId: $userId)
  }
`

module.exports.triggerNotification = gql`
  mutation TriggerNotification($input: NotificationInput!) {
    triggerNotification(input: $input) {
      userId
    }
  }
`

module.exports.triggerCardNotification = gql`
  mutation TriggerCardNotification($input: CardNotificationInput!) {
    triggerCardNotification(input: $input) {
      userId
    }
  }
`

module.exports.triggerChatMessageNotification = gql`
  mutation TriggerChatMessageNotification($input: ChatMessageNotificationInput!) {
    triggerChatMessageNotification(input: $input) {
      userId
    }
  }
`

module.exports.triggerPostNotification = gql`
  mutation TriggerPostNotification($input: PostNotificationInput!) {
    triggerPostNotification(input: $input) {
      userId
    }
  }
`
