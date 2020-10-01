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
  location: {latitude: 30, longitude: 50}, // different from that used in other test suites
  dateOfBirth: '2000-01-01',
  matchAgeRange: {min: 20, max: 30},
  matchGenders: ['FEMALE'],
  matchLocationRadius: 50,
}

test('Reject and approve match - error cases and basic success', async () => {
  const {client: ourClient, userId: ourUserId} = await loginCache.getCleanLogin()
  const {client: theirClient, userId: theirUserId} = await loginCache.getCleanLogin()

  // verify we can't approve or reject them
  await expect(
    ourClient.mutate({mutation: mutations.rejectMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Match does not exist/)
  await expect(
    ourClient.mutate({mutation: mutations.approveMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Match does not exist/)

  // we both set details that would *almost* make us match each other, and enable dating
  const [pid1, pid2] = [uuidv4(), uuidv4()]
  await ourClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid1, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid1))
  await ourClient
    .mutate({
      mutation: mutations.setUserDetails,
      variables: {...datingVariables, gender: 'MALE', photoPostId: pid1},
    })
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(ourUserId))
  await theirClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid2, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid2))
  await theirClient
    .mutate({mutation: mutations.setUserDetails, variables: {...datingVariables, photoPostId: pid2}})
    .then(({data: {setUserDetails: user}}) => expect(user.userId).toBe(theirUserId))
  await misc.sleep(2000)
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await theirClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))

  // verify we still can't approve or reject them
  await expect(
    ourClient.mutate({mutation: mutations.rejectMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Match does not exist/)
  await expect(
    ourClient.mutate({mutation: mutations.approveMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Match does not exist/)

  // we adjust our details, so now we are a match, so now we can reject them and they can approve us
  await ourClient.mutate({mutation: mutations.setUserDetails, variables: {gender: 'FEMALE'}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))
  await misc.sleep(2000)
  await ourClient.mutate({mutation: mutations.rejectMatch, variables: {userId: theirUserId}})
  await theirClient.mutate({mutation: mutations.approveMatch, variables: {userId: ourUserId}})
})

test('POTENTIAL -> CONFIRMED', async () => {
  const {client: ourClient, userId: ourUserId} = await loginCache.getCleanLogin()
  const {client: theirClient, userId: theirUserId} = await loginCache.getCleanLogin()

  // we both set details that would make us match each other, and enable dating
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

  // we approve them, check statues
  await ourClient.mutate({mutation: mutations.approveMatch, variables: {userId: theirUserId}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('APPROVED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))

  // check now we can't reject them, or re-approve them
  await expect(
    ourClient.mutate({mutation: mutations.rejectMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)
  await expect(
    ourClient.mutate({mutation: mutations.approveMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)

  // they approve us, check statuses
  await theirClient.mutate({mutation: mutations.approveMatch, variables: {userId: ourUserId}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('CONFIRMED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('CONFIRMED'))

  // check now they can't reject us, or re-approve us
  await expect(
    theirClient.mutate({mutation: mutations.rejectMatch, variables: {userId: ourUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)
  await expect(
    theirClient.mutate({mutation: mutations.approveMatch, variables: {userId: ourUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)
})

test('POTENTIAL -> REJECTED & APPROVED', async () => {
  const {client: ourClient, userId: ourUserId} = await loginCache.getCleanLogin()
  const {client: theirClient, userId: theirUserId} = await loginCache.getCleanLogin()

  // we both set details that would make us match each other, and enable dating
  const [pid1, pid2] = [uuidv4(), uuidv4()]
  await ourClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid1, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid1))
  await ourClient.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      fullName: 'Hunter S',
      photoPostId: pid1,
      gender: 'FEMALE',
      location: {latitude: 30, longitude: 0},
      dateOfBirth: '2000-01-01',
      matchAgeRange: {min: 20, max: 30},
      matchGenders: ['FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await theirClient
    .mutate({mutation: mutations.addPost, variables: {postId: pid2, imageData: imageDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(pid2))
  await theirClient.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      fullName: 'Hunter S',
      photoPostId: pid2,
      gender: 'FEMALE',
      location: {latitude: 30, longitude: 0},
      dateOfBirth: '2000-01-01',
      matchAgeRange: {min: 20, max: 30},
      matchGenders: ['FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)
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

  // we reject them, check statues
  await ourClient.mutate({mutation: mutations.rejectMatch, variables: {userId: theirUserId}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('REJECTED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('POTENTIAL'))

  // check now we can't reject them, or re-approve them
  await expect(
    ourClient.mutate({mutation: mutations.rejectMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)
  await expect(
    ourClient.mutate({mutation: mutations.approveMatch, variables: {userId: theirUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)

  // they approve us, check statuses
  await theirClient.mutate({mutation: mutations.approveMatch, variables: {userId: ourUserId}})
  await misc.sleep(2000)
  await ourClient
    .query({query: queries.user, variables: {userId: theirUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('REJECTED'))
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.matchStatus).toBe('APPROVED'))

  // check now they can't reject us, or re-approve us
  await expect(
    theirClient.mutate({mutation: mutations.rejectMatch, variables: {userId: ourUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)
  await expect(
    theirClient.mutate({mutation: mutations.approveMatch, variables: {userId: ourUserId}}),
  ).rejects.toThrow(/ClientError: Invalid match transition/)
})
