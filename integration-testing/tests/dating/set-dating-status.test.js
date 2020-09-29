const fs = require('fs')
const path = require('path')
const uuidv4 = require('uuid/v4')

const cognito = require('../../utils/cognito')
const misc = require('../../utils/misc')
const {mutations, queries} = require('../../schema')

const grantData = fs.readFileSync(path.join(__dirname, '..', '..', 'fixtures', 'grant.jpg'))
const grantDataB64 = new Buffer.from(grantData).toString('base64')
const loginCache = new cognito.AppSyncLoginCache()
jest.retryTimes(1)

beforeAll(async () => {
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
  loginCache.addCleanLogin(await cognito.getAppSyncLogin())
})
beforeEach(async () => await loginCache.clean())
afterAll(async () => await loginCache.reset())

test('Enable, disable dating as a BASIC user, privacy', async () => {
  const {client: ourClient, userId: ourUserId} = await loginCache.getCleanLogin()
  const {client: theirClient} = await loginCache.getCleanLogin()

  // Check if the new user's datingStatus is DISABLED
  await ourClient.query({query: queries.self}).then(({data: {self: user}}) => {
    expect(user.datingStatus).toBe('DISABLED')
    expect(user.subscriptionLevel).toBe('BASIC')
  })

  // check they can't see our dating status
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.datingStatus).toBeNull())

  // check we cannot enable dating without setting stuff
  await expect(
    ourClient.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: .* required to enable dating/)

  // we set all the stuff needed for dating
  const postId = uuidv4()
  await ourClient
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await ourClient.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      photoPostId: postId,
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // enable dating, verify value saved
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
  await ourClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.datingStatus).toBe('ENABLED'))

  // check another user still can't see our datingStatus
  await theirClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.datingStatus).toBeNull())

  // we disable dating, verify value saved
  await ourClient
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'DISABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('DISABLED'))
  await ourClient
    .query({query: queries.user, variables: {userId: ourUserId}})
    .then(({data: {user}}) => expect(user.datingStatus).toBe('DISABLED'))
})

test('FullName required to enable dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // set all the stuff needed for dating, except fullName
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      photoPostId: postId,
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'fullName'}` required to enable dating/)
})

test('Profile photo required to enable dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // set all the stuff needed for dating except a profile photo
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'photoPostId'}` required to enable dating/)
})

test('Gender required to enable dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // set all the stuff needed for dating, except gender
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      photoPostId: postId,
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'gender'}` required to enable dating/)
})

test('location required to enable dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // set all the stuff needed for dating, except location
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      photoPostId: postId,
      gender: 'MALE',
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'location'}` required to enable dating/)
})

test('matchAgeRange required to enable dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // we set all the stuff needed for dating, except matchAgeRange
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      photoPostId: postId,
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'matchAgeRange'}` required to enable dating/)
})

test('matchGenders required to enable dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // we set all the stuff needed for dating, except matchGenders
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      photoPostId: postId,
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'matchGenders'}` required to enable dating/)
})

test('BASIC users require matchLocationRadius to enable dating, DIAMOND users do not', async () => {
  const {client} = await loginCache.getCleanLogin()

  // we set all the stuff needed for dating, except matchLocationRadius
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      dateOfBirth: '2000-01-01',
      fullName: 'Hunter S',
      photoPostId: postId,
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'matchLocationRadius'}` required to enable dating/)

  // give ourselves some free DIAMOND
  await client
    .mutate({mutation: mutations.grantUserSubscriptionBonus})
    .then(({data: {grantUserSubscriptionBonus: user}}) => expect(user.subscriptionLevel).toBe('DIAMOND'))

  // verify now we can enable dating
  await client
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
})

test('Age required and must be in allowed age range for enabling dating', async () => {
  const {client} = await loginCache.getCleanLogin()

  // we set all the stuff needed for dating
  const postId = uuidv4()
  await client
    .mutate({mutation: mutations.addPost, variables: {postId, imageData: grantDataB64, takenInReal: true}})
    .then(({data: {addPost: post}}) => expect(post.postId).toBe(postId))
  await client.mutate({
    mutation: mutations.setUserDetails,
    variables: {
      fullName: 'Hunter S',
      photoPostId: postId,
      gender: 'MALE',
      location: {latitude: 50.01, longitude: 50.01, accuracy: 20},
      matchAgeRange: {min: 20, max: 50},
      matchGenders: ['MALE', 'FEMALE'],
      matchLocationRadius: 50,
    },
  })
  await misc.sleep(2000)

  // verify can't enable dating
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: `{'age'}` required to enable dating/)

  // set age, but too young
  await client.mutate({mutation: mutations.setUserDetails, variables: {dateOfBirth: '2019-01-01'}})
  await misc.sleep(2000)
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: age .* must be between /)

  // set age, but too old
  await client.mutate({mutation: mutations.setUserDetails, variables: {dateOfBirth: '1900-01-01'}})
  await misc.sleep(2000)
  await expect(
    client.mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}}),
  ).rejects.toThrow(/ClientError: age .* must be between /)

  // set age to an allowed dating age
  await client.mutate({mutation: mutations.setUserDetails, variables: {dateOfBirth: '1980-01-01'}})
  await misc.sleep(2000)
  await client
    .mutate({mutation: mutations.setUserDatingStatus, variables: {status: 'ENABLED'}})
    .then(({data: {setUserDatingStatus: user}}) => expect(user.datingStatus).toBe('ENABLED'))
})
