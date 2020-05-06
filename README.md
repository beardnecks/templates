# Suricata pipeline
This project is a product of a bachelor thesis written by three students from NTNU Gjøvik. 
The projects goal is to automate testing and deployment of Suricata using AWS. 

The solution is split up in two services, the first one being integration. This service integrtes GitHub or Bitbucket with AWS. The second service is the pipeline service, this service runs the CodePipeline pipeline and the notification service.

The two services are connected by one S3 bucket called which contains the source code the user wants to run.

This repository contains the pipeline service. Other relevant git repos can be found in [Necessary Git repositories](#necessary-git-repositories).
## Table of Contents
1. [Design overview](#design-overview)
2. [Necessary git repositories](#necessary-git-repositories)
3. [CloudFormation Templates](#cloudformation-templates)
4. [IAM Policy](#iam-policy)
5. [Deployment example](#deployment-example)
    * [Preperation](#preparation)
    * [Build and Upload files](#build-and-upload-files)
    * [Production Pipeline](#production-pipeline)
    * [Development Pipeline](#development-pipeline)

## Design overview
This High-Level design figure depics the entire solution with both integration service and the pipeline service.

![HLD](/AWS-Plan.png)

## Necessary git repositories
[aws-git-intgeration](https://github.com/beardnecks/aws-git-integration)
* Integrate GitHub or Bitbucket to AWS by uploading source code to a S3 bucket.
 
[suricata-pipeline-config-files](https://github.com/beardnecks/suricata-pipeline-config-files)
* Files required by the pipeline to run tests on and build Suricata

## CloudFormation Templates
The master template will initiate the nested stacks to create a pipeline in AWS CodePipeline.

## IAM Policy
The master templates creates a `DevOpsLogViewPolicy` and `DevOpsLogViewGroup` that admins can use to give developers read only access
to the pipeline created in the stack. The user will be able to view the execution state, history and logs of the pipeline, but will not have rights to
modify, stop, run or otherwise affect the pipeline. It also does not provide access to other parts of the AWS account

# Deployment Example
## Preparation
The pipelines have several configurable parameters. Configure all the environment variables below in your terminal environment before moving on.
```bash
# Prefixes for stack names to indicate production or development
DEV_PREFIX="<DEV_PREFIX>"
PROD_PREFIX="<PROD_PREFIX>"

# Region stack should be deployed in
REGION="<REGION>"

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
  ParameterKey=BuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/build/suricata-devops" \
  ParameterKey=CoccinelleBuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/build/suricata-coccinelle" \
  ParameterKey=PipelineName,ParameterValue="${PROD_PREFIX}-${STACKNAME}" \
  ParameterKey=SourceBucket,ParameterValue="${SOURCE_BUCKET_NAME}" \
  ParameterKey=SourceBucketObjectKey,ParameterValue="${REPO_USERNAME}/${REPO_NAME}/prod/${REPO_USERNAME}_${REPO_NAME}.zip" \
  ParameterKey=PipelineTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codePipeline/prod-pipeline.json" \
  ParameterKey=UnitTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/unittest.json" \
  ParameterKey=VerifyTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/verify.json" \
  ParameterKey=CoccinelleTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/coccinelle.json" \
  ParameterKey=ClangTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/clang.json" \
  ParameterKey=RustTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/rust.json" \
  ParameterKey=PackagingTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/package.json" \
  ParameterKey=DockerBuildTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/dockerBuild.json" \
  ParameterKey=DockerDeployTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/dockerDeploy.json" \
  ParameterKey=NotificationTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}notification/function.json" \
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
  ParameterKey=BuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/build/suricata-devops" \
  ParameterKey=CoccinelleBuildImage,ParameterValue="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/build/suricata-coccinelle" \
  ParameterKey=PipelineName,ParameterValue="${DEV_PREFIX}-${STACKNAME}" \
  ParameterKey=SourceBucket,ParameterValue="${SOURCE_BUCKET_NAME}" \
  ParameterKey=SourceBucketObjectKey,ParameterValue="${REPO_USERNAME}/${REPO_NAME}/dev/${REPO_USERNAME}_${REPO_NAME}.zip" \
  ParameterKey=PipelineTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codePipeline/dev-pipeline.json" \
  ParameterKey=UnitTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/unittest.json" \
  ParameterKey=VerifyTestTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/verify.json" \
  ParameterKey=CoccinelleTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/coccinelle.json" \
  ParameterKey=ClangTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/clang.json" \
  ParameterKey=RustTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}codeBuild/rust.json" \
  ParameterKey=NotificationTemplateURL,ParameterValue="https://${UPLOAD_BUCKET}.s3.${REGION}.amazonaws.com/${PREFIX}notification/function.json" \
  ParameterKey=token,ParameterValue="${API_TOKEN}" \
  ParameterKey=snsTopicName,ParameterValue="${DEV_PREFIX}-${PREFIX: : -1}-sns" \
  ParameterKey=snsDisplayName,ParameterValue="Github Notification Service"
```
