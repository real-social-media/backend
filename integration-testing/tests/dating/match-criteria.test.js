const uuidv4 = require('uuid/v4')

const cognito = require('../../utils/cognito')
const misc = require('../../utils/misc')
const {mutations, queries} = require('../../schema')

const imageData = misc.generateRandomJpeg(8, 8)
const imageDataB64 = new Buffer.from(imageData).toString('base64')
const loginCache = new cognito.AppSyncLoginCache()
jest.retryTimes(1)

beforeAll(async () => {
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
})
beforeEach(async () => await loginCache.clean())
afterAll(async () => await loginCache.reset())

// generic dating criteria that matches itself
const datingVariables = {
  fullName: 'Hunter S',
  gender: 'FEMALE',
  location: {latitude: 30, longitude: 0}, // different from that used in other test suites
  dateOfBirth: '2000-01-01',
  matchAgeRange: {min: 20, max: 30},
  matchGenders: ['FEMALE'],
  matchLocationRadius: 50,
}

test('We do not match ourselves', async () => {
  const {client, userId} = await loginCache.getCleanLogin()

  // check we don't match ourselves without dating enabled
  await client
    .query({query: queries.self})
    .then(({data: {self: user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))

  // set our dating parameters so we would match ourselves, enable dating
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client
    .mutate({mutation: mutations.setUserDetails, variables: {...datingVariables, photoPostId: postId}})
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(userId))
  await misc.sleep(2000)
  await client
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))

  // check we still don't match ourselves
  await client
    .query({query: queries.self})
    .then(({data: {self: user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))
})

test('Enable & disable dating changes match status', async () => {
  const {client: ourClient, userId: ourUserId} = await loginCache.getCleanLogin()
  const {client: theirClient, userId: theirUserId} = await loginCache.getCleanLogin()

  // check start with no match in either direction
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))

  // we both set details that would make us match each other
  const [pid1, pid2] = [uuidv4(), uuidv4()]
  await ourClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid1, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid1))
  await ourClient
    .mutate({mutation: mutations.setUserDetails, variables: {...datingVariables, photoPostId: pid1}})
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(ourUserId))
  await theirClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid2, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid2))
  await theirClient
    .mutate({mutation: mutations.setUserDetails, variables: {...datingVariables, photoPostId: pid2}})
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(theirUserId))
  await misc.sleep(2000)

  // we enable dating, but they don't yet, check still no match in either direction
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))

  // they enable dating, check matches in both directions
  await theirClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))

  // we disable dating, check matches disappeared
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'DISABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('DISABLED'))
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))

  // we enable dating, check matches are back
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
})

test('Changing match criteria changes match status', async () => {
  const {client: ourClient, userId: ourUserId} = await loginCache.getCleanLogin()
  const {client: theirClient, userId: theirUserId} = await loginCache.getCleanLogin()

  // we both set details that would make us match each other
  const [pid1, pid2] = [uuidv4(), uuidv4()]
  await ourClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid1, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid1))
  await ourClient
    .mutate({mutation: mutations.setUserDetails, variables: {...datingVariables, photoPostId: pid1}})
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(ourUserId))
  await theirClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid2, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid2))
  await theirClient
    .mutate({mutation: mutations.setUserDetails, variables: {...datingVariables, photoPostId: pid2}})
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(theirUserId))
  await misc.sleep(2000)

  // we both enable dating, check matches in both directions
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await theirClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))

  // we adjust our matchGenders, check match disappears
  await ourClient.mutate({mutation: mutations.setUserDetails, variables: {matchGenders: ['MALE']}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))

  // they adjust their gender, check match reappears
  await theirClient.mutate({mutation: mutations.setUserDetails, variables: {gender: 'MALE'}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))

  // they adjust their location, check match disappears
  await theirClient.mutate({
    mutation: mutations.setUserDetails,
    variables: {location: {latitude: -30, longitude: -30}},
  })
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('NOT_MATCHED'))

  // we adjust our location, check match reappears
  await ourClient.mutate({
    mutation: mutations.setUserDetails,
    variables: {location: {latitude: -30, longitude: -30}},
  })
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
})
