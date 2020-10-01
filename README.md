# REAL Backend

## Overview

[serverless](https://serverless.com) is used to manage this project.

The backend is organized as a series of cloudformation stacks to speed up the standard deploy and to help protect stateful resources. The stacks so far are:

- `real-main`
- `real-auth`
- `real-cloudfront`
- `real-lambda-layers`

## Getting started

Installed on your system you will need `nodejs12`, `yarn`, `python3.8`, `poetry`, `docker`.

In each of the stack root directories, run `yarn install` to install serverless and required plugins.

To lint python files you will need `black` and `flake8` installed globally.

## Deployment

To deploy each serverless stack, run `yarn deploy` in that stack's root directory.

### AWS Credentials

By default, serverless will use aws credentials stored in the profile with name `real-{stage}` (ie: `real-dev`, `real-staging`, or `real-production`). This behavior can be overridden by using the [`--aws-profile`](https://serverless.com/framework/docs/providers/aws/guide/credentials/#using-aws-profiles) option.

Serverless expects the AWS credentials to have `AdministratorAccess` policy attached.

### First-time deployment manual steps

#### CloudWatch

_Once per AWS Account, must be done before first deployment_

- Create a LogGroup with name `sns/<aws-region>/<aws-account-id>/DirectPublishToPhoneNumber/Failure`. This log group will be referenced by all deployments in the account, and used by SNS to log SMS delivery failures.

#### IAM

_Once per AWS Account_

- Google needs to be configured as an [IAM OIDC Provider](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) before `real-main` can be deployed. Step-by-step instructions are available [here](https://medium.com/fullstack-with-react-native-aws-serverless-and/set-up-openid-connect-oidc-provider-in-aws-91d498f3c9f7).

#### Pinpoint

_Once per deployment_

Pinpoint must be manually configured to send Apple Push notifications. After first deployment, from the [Pinpoint console](https://console.aws.amazon.com/pinpoint/home?region=us-east-1)
  - navigate REAL Pinpoint Project -> Settings -> Push notifications -> Edit -> Apple Push Notification Service
  - Enable APNS and choose 'Key credentials' as authentication type
    - Our 'Bundle identifier' is `app.real.mobile` and our 'Team identifier' is `YA5Y244F5C`
    - A 'Key ID' corresponding 'Authentication key (.p8 file)' are available from the frontend iOS team

#### SecretsManager

_Once per deployment_

- Credentials to access the post verification API must be added. Reference the environment variable in `serverless.yml` for required format. Talk to the backend team lead to get a set of credentials.

_Once per AWS Account_

- A CloudFront Key Pair must be generated and added. To do so, one must login to the AWS Console using the account's *root* credentials. See [Setting up CloudFront Signed URLs](#setting-up-cloudfront-signed-urls) for details.
- Google OAuth Client Ids must be added to support logging in with google auth. These client ids are available from our google app's profile on the [google app console](https://console.developers.google.com/). The secret value must be a json map with keys `ios` and `web`, while the secret name must match the environment variable defined in `serverless.yml`.
- The Apple AppStore parameters must be added in order to process & verify appstore receipts. The secret value must be a json map with keys `bundleId` and [`sharedSecret`](https://developer.apple.com/documentation/appstorereceipts/requestbody), while the secret name must match the environment variable defined in `serverless.yml`. Talk to the frontend team lead to get the values for these parameters.
- A RSA Key Pair must be generated for internal use, namely for encrypting passwords when passed as arguments via GQL. To generate a key pair from the command line using [`openssl`](https://www.openssl.org/docs/man1.0.2/man1/openssl.html):

  ```sh
  openssl genrsa -out private-key.pem
  openssl rsa -in private-key.pem -outform PEM -pubout -out public-key.pem
  ```

  The secret name must match the environment variable defined in `serverless.yml`, while the secret value should should be

  ```json
  {
    "publicKey": "<cat public-key.pem | sed '1d;$d'>",
    "privateKey": "<cat private-key.pem | sed '1d;$d'>"
  }
  ```

#### SES

_Once per AWS Account_

To allow [SES](https://console.aws.amazon.com/ses/home) to send transactional emails from Cognito:

- Add and verify the domain `real.app`. To do this you will need to be able to add a code to a TXT record on the `real.app` domain.
- Configure the MAIL FROM domain of `mail.real.app`
- If this is a production account, you will also want to configure DKIM for `real.app` in the SES interface.

You must also confirm, using the SES interface,  the email address you wish to send email from (even if you've already confirmed the domain). By default `no-reply@real.app` will be used. You can either:

- confirm that email address. You would want to do this for a brand-new production deployment, and possibly for a new staging or pre-production deployment.
- alternatively, you can set the environment variable `SES_SENDER_ADDRESS` in a `.env` file in the `real-main` directory to an email address you control, and then confirm that email address in SES.

#### SNS

_Once per AWS Account_

- Use [this guide](https://docs.aws.amazon.com/sns/latest/dg/sms_stats_cloudwatch.html#sns-viewing-cloudwatch-logs) to enable CloudWatch Logs for all SMS messages

_Once per deployment_

- If you wish to receive notifications for error alerts, after the first deployment is complete you can subscribe your email or phone to the auto-generated SNS topics using the [AWS SNS Console](https://console.aws.amazon.com/sns/v3/home).

### Other stacks outside this repo

Please talk to the backend team lead to get access to these stacks.

#### `themes`

_Required, must be deployed before real-main_

The `themes` stack will create an S3 bucket, within which there is a subdirectory `placeholder-photos`. The integration tests in this repo expect that subdirectory to be empty.

#### `dating`

_Optional, no deployment order constraints_

Only required in order for dating-related operations and tests to work correctly.

### First-time stack deployment order

Resource dependencies between the stacks make initial deployment tricky. Stacks should be deployed in this order:

- `real-lambda-layers`
- `real-main`, with the following commented out from `serverless.yml`
  - the `AWS::S3::BucketPolicy` resource that depends on `real-cloudfront`
  - the `AWS::Logs::MetricFilter`s and `AWS::CloudWatch::Alarm` that depend on a AppSync GraphQL LogGroup
- `real-cloudfront`
- `real-main` again, with nothing commented out
- `real-auth`

### Updates to an existing deployment

In general, only stacks that have been changed since the last deployment need to be redeployed.

However, if a stack changed naming or versioning of a resource that another stack depends on, then the dependent stack needs to be redeployed as well. For example:

- when the `real-lambda-layers` stack is redeployed with new python packages, its lambda layer version number is incremented
- old versions of the `real-lambda-layers` are retained to allow rolling back a deployment of a dependent stack (ie: `real-main`) if necessary. Old versions of the layer should be deleted manually via the AWS Console once all stacks using the layer have been upgraded to use the new version.
- in order for the `real-main` lambda handlers to the latest version of that lambda layer, `real-main` must be redeployed as well

## External-facing API's, resources

### AppSync graphql endpoint

- Browse the [graphql schema](./real-main/schema.graphql).
- Endpoint url is provided by CloudFormation output `real-<stage>-main.GraphQlApiUrl`

### Cognito User Pool

- Allows authentication of new and existing users with email/phone and password
- User pool client id is provided by CloudFormation output `real-<stage>-main.CognitoFrontendUserPoolClientId`
- If SES is still in sandbox mode for the AWS Account (it is if you haven't [moved it out of the sandbox](https://docs.aws.amazon.com/ses/latest/DeveloperGuide/request-production-access.html)) then Cognito will only be able to send emails to addresses that have been verified either in IAM or in SES.

## Running the tests

### Integration tets

Please see the [Integation Testing README](./integration-testing/README.md)

### Unit tests

The unit tests of the python lambda handlers in the primary stack use [pytest](http://doc.pytest.org/en/latest/). To run them:

```sh
cd real-main
poetry shell
pytest --cov=app app_tests/
```

## Development

### The serverless stacks

#### `real-main`

This is the primary stack, it holds everything not explicitly relegated to one of the other stacks.

Most development takes place here. To initialize the development environment, run `poetry install` in the stack root directory.

#### `real-auth`

Holds:

- Api endpoints to asist in sign up / sign in process
- Planned: Cognito resources will be moved in here (they are still in `real-main` at the moment)

Please see the [real-auth README](./real-auth/README.md) for further details.

#### `real-cloudfront`

Holds:

- CloudFront CDN for the main 'uploads' bucket
- Lambda@Edge handlers for that CloudFront instance

The Lambda@Edge handlers need to be broken into a separate stack because:

- they are included in every deploy regardless of whether they have changed or not
- re-deploying them takes ~20 minutes

CloudFront is included because:

- changes to the CloudFront config, while somewhat uncommon, also trigger a ~20 minute deploy
- separating the CloudFront config and the Lambda@Edge handlers into separate stacks isn't supported by the [cloudfront-lambda-edge serverless plugin](https://github.com/silvermine/serverless-plugin-cloudfront-lambda-edge/)

#### `real-lambda-layers`

Holds the [lambda layers](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html). The python packages which the lambda handlers in the primary stack depend on are stored in a layer. This reduces the size of the deployment package of the primary stack from several megabytes to several kilobytes, making deploys of the primary stack much faster.

### Adding new python dependencies

Note that new python packages dependencies for the lambda handlers in the primary `real-main` stack should be installed in two places:

- in the primary `real-main` stack as a dev dependency: `poetry add --dev <package name>`
- in the `real-main-lambda-layers` stack as a runtime dependency: `poetry add <package name>`

After adding a new dependency, the `real-main-lambda-layers` stack should be re-deployed first, followed by the `real-main` stack.

### Setting up CloudFront Signed URLs

After a deploy to a new account, a CloudFront key pair needs to be manually generated and stored in the AWS secrets manager.

- a new CloudFront key pair can be generated in the [your security credentials](https://console.aws.amazon.com/iam/home#/security_credentials) section of IAM in the AMZ console. This is *only* available when logging in using AWS account's *root* credentials.

- the public and private parts of the generated key should be stored in an entry in the [AWS Secrets Manager](https://us-east-1.console.aws.amazon.com/secretsmanager/home)

  - the name of the secret must match the value in the environment variable `SECRETSMANAGER_CLOUDFRONT_KEY_PAIR_NAME` as defined in the `environment` section of [serverless.yml](./real-main/serverless.yml)
  - the `publicKey` and `privateKey` values in the secret must *not* contain the header and footer lines (ie the `----- BEGIN/END RSA PRIVATE KEY -----` lines)
  - the format of the secret should be

    ```json
    {
      "keyId": "<access key id>",
      "publicKey": "<cat public-key.pem | sed '1d;$d'>",
      "privateKey": "<cat private-key.pem | sed '1d;$d'>"
    }
    ```

## Internal stateful services

### DynamoDB

#### Table Schema

Please see the [SCHEMA.md](./SCHEMA.md) document.

#### Data Migrations

The order of operations to implement a data migration is:

  - deploy code that can read from both old and new `schemaVersion`, and uses new `schemaVersion` when creating new items
  - run data migration transforming all items with old `schemaVersion` to new `schemaVersion`
  - deploy code that only reads and writes new `schemaVersion`

### S3

The following objects are stored with the given path structures:

- Image posts:
  - `{userId}/post/{postId}/image/***.jpg`
- Video posts:
  - `{userId}/post/{postId}/video/video-original.mov`.
  - `{userId}/post/{postId}/video/video-hls/*`
  - `{userId}/post/{postId}/image/***.jpg`
- User profile photo: `{userId}/profile-photo/{photoPostId}/***.jpg`
- Album art: `{userId}/album/{albumId}/{artHash}/***.jpg`
