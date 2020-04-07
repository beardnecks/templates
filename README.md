# Cloudformation Templates
The master template will initiate the nested stacks to create the pipeline.

# Templates
The templates must be uploaded to an S3 bucket.

# Parameters
All parameters will be passed to the Master CFN tempalte which will then assign the correct values to the correct templates

# Example
## Preparation
The pipelines have several configurable parameters. Configure all the environment variables below in your terminal environment before moving on.
```bash
# Prefixes for stack names to indicate production or development
DEV_PREFIX="<DEV_PREFIX>"
PROD_PREFIX="<PROD_PREFIX>"

# Which S3 bucket to upload templates to, and what folder to use. Bucket must already exist.
UPLOAD_BUCKET="<TEMPLATE_UPLOAD_BUCKET>"
PREFIX="<STACK_UPLOAD_PREFIX>/"

# Name of root stack
STACKNAME="<STACKNAME>"

# AccountID used to retrieve docker images from ECR repository
ACCOUNT_ID="<ACCOUNT_ID>"

# The bucket where the pipeline will look for the source
SOURCE_BUCKET_NAME="<SOURCE_BUCKET_NAME>"

# Name of user or organization that owns repository
REPO_USERNAME="<USERNAME>"
# Name of repository
REPO_NAME="<REPO_NAME>"
# API token to use GitHub API, or basic auth token for Bitbucket API
API_TOKEN="<API_TOKEN>"
```

## Build and Upload files
Build, package and upload notification function:
```bash
sam build --use-container -t notification/function/template.json
sam package -t .aws-sam/build/notificationFunction/template.json --s3-bucket "$UPLOAD_BUCKET" --use-json --output-template-file notification/function.json --s3-prefix "${PREFIX: : -1}"
```

Upload CloudFormation templates:
```bash
aws s3 cp notification/function.json s3://${UPLOAD_BUCKET}/${PREFIX}notification/
aws s3 cp --recursive codeBuild s3://${UPLOAD_BUCKET}/${PREFIX}codeBuild/
aws s3 cp --recursive codePipeline s3://${UPLOAD_BUCKET}/${PREFIX}codePipeline/
```

## Production Pipeline
Launch production pipeline stack
```bash
# Example of how to deploy from cli
aws cloudformation create-stack --stack-name "${PROD_PREFIX}-${STACKNAME}" --template-body file://prod-master.json \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND --on-failure DO_NOTHING --parameters \
  ParameterKey=UnitTestBuildSpecFileName,ParameterValue="qa/buildspec/unittest.yml" \
  ParameterKey=VerifyBuildSpecFileName,ParameterValue="qa/buildspec/suricata-verify.yml" \
  ParameterKey=CoccinelleBuildSpecFileName,ParameterValue="qa/buildspec/coccinelle.yml" \
  ParameterKey=ClangBuildSpecFileName,ParameterValue="qa/buildspec/clang.yml" \
  ParameterKey=RustBuildSpecFileName,ParameterValue="qa/buildspec/rust.yml" \
  ParameterKey=PackagingBuildSpecFileName,ParameterValue="qa/buildspec/packaging.yml" \
  ParameterKey=DockerBuildBuildSpecFileName,ParameterValue="qa/buildspec/dockerbuild.yml" \
  ParameterKey=DockerDeployBuildSpecFileName,ParameterValue="dockerdeploy.yml" \
  ParameterKey=BuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/build/suricata-devops" \
  ParameterKey=CoccinelleBuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/build/suricata-coccinelle" \
  ParameterKey=PipelineName,ParameterValue="${PROD_PREFIX}-${STACKNAME}" \
  ParameterKey=SourceBucket,ParameterValue="${SOURCE_BUCKET_NAME}" \
  ParameterKey=SourceBucketObjectKey,ParameterValue="${REPO_USERNAME}/${REPO_NAME}/prod/${REPO_USERNAME}_${REPO_NAME}.zip" \
  ParameterKey=PipelineTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codePipeline/prod-pipeline.json" \
  ParameterKey=UnitTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/unittest.json" \
  ParameterKey=VerifyTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/verify.json" \
  ParameterKey=CoccinelleTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/coccinelle.json" \
  ParameterKey=ClangTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/clang.json" \
  ParameterKey=RustTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/rust.json" \
  ParameterKey=PackagingTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/package.json" \
  ParameterKey=DockerBuildTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/dockerBuild.json" \
  ParameterKey=DockerDeployTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/dockerDeploy.json" \
  ParameterKey=NotificationTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}notification/function.json" \
  ParameterKey=OutputBucketName,ParameterValue="${PREFIX: : -1}-rpm" \
  ParameterKey=token,ParameterValue="${API_TOKEN}" \
  ParameterKey=snsTopicName,ParameterValue="${PROD_PREFIX}-${PREFIX: : -1}-sns" \
  ParameterKey=snsDisplayName,ParameterValue="Github Notification Service"
```

## Development Pipeline
Launch development pipeline stack
```bash
aws cloudformation create-stack --stack-name "${DEV_PREFIX}-${STACKNAME}" --template-body file://dev-master.json \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND --on-failure DO_NOTHING --parameters \
  ParameterKey=UnitTestBuildSpecFileName,ParameterValue="qa/buildspec/unittest.yml" \
  ParameterKey=VerifyBuildSpecFileName,ParameterValue="qa/buildspec/suricata-verify.yml" \
  ParameterKey=CoccinelleBuildSpecFileName,ParameterValue="qa/buildspec/coccinelle.yml" \
  ParameterKey=ClangBuildSpecFileName,ParameterValue="qa/buildspec/clang.yml" \
  ParameterKey=RustBuildSpecFileName,ParameterValue="qa/buildspec/rust.yml" \
  ParameterKey=BuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/build/suricata-devops" \
  ParameterKey=CoccinelleBuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.eu-west-1.amazonaws.com/build/suricata-coccinelle" \
  ParameterKey=PipelineName,ParameterValue="${DEV_PREFIX}-${STACKNAME}" \
  ParameterKey=SourceBucket,ParameterValue="${SOURCE_BUCKET_NAME}" \
  ParameterKey=SourceBucketObjectKey,ParameterValue="${REPO_USERNAME}/${REPO_NAME}/dev/${REPO_USERNAME}_${REPO_NAME}.zip" \
  ParameterKey=PipelineTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codePipeline/dev-pipeline.json" \
  ParameterKey=UnitTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/unittest.json" \
  ParameterKey=VerifyTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/verify.json" \
  ParameterKey=CoccinelleTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/coccinelle.json" \
  ParameterKey=ClangTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/clang.json" \
  ParameterKey=RustTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/rust.json" \
  ParameterKey=NotificationTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3-eu-west-1.amazonaws.com/${PREFIX}notification/function.json" \
  ParameterKey=token,ParameterValue="${API_TOKEN}" \
  ParameterKey=snsTopicName,ParameterValue="${DEV_PREFIX}-${PREFIX: : -1}-sns" \
  ParameterKey=snsDisplayName,ParameterValue="Github Notification Service"
```
