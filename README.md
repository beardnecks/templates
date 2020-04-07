# Cloudformation Templates
The master template will initiate the nested stacks to create the pipeline.

# Templates
The templates must be uploaded to an S3 bucket.

# Parameters
All parameters will be passed to the Master CFN tempalte which will then assign the correct values to the correct templates

# Example
```bash
# Example of how to deploy from cli
PREFIX="<STACK_UPLOAD_PREFIX>/"
STACKNAME="<STACKNAME>"
UPLOAD_BUCKET="<TEMPLATE_UPLOAD_BUCKET>"
ACCOUNT_ID="<ACCOUNT_ID>"
SOURCE_BUCKET_NAME="<SOURCE_BUCKET_NAME>"
REPO_USERNAME="<USERNAME>"
REPO_NAME="<REPO_NAME>"
API_TOKEN="<API_TOKEN>"

sam build --use-container -t notification/function/template.json
sam package -t .aws-sam/build/notificationFunction/template.json --s3-bucket $UPLOAD_BUCKET --use-json --output-template-file notification/function.json --s3-prefix ${PREFIX: : -1}
aws s3 cp prod-master.json s3://${UPLOAD_BUCKET}/${PREFIX}
aws s3 cp dev-master.json s3://${UPLOAD_BUCKET}/${PREFIX}
aws s3 cp notification/function.json s3://${UPLOAD_BUCKET}/${PREFIX}notification/
aws s3 cp --recursive codeBuild s3://${UPLOAD_BUCKET}/${PREFIX}codeBuild/
aws s3 cp --recursive codePipeline s3://${UPLOAD_BUCKET}/${PREFIX}codePipeline/

aws cloudformation create-stack --stack-name ${STACKNAME} --template-body file://prod-master.json \
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
  ParameterKey=PipelineName,ParameterValue=${STACKNAME} \
  ParameterKey=SourceBucket,ParameterValue="${SOURCE_BUCKET_NAME}" \
  ParameterKey=SourceBucketObjectKey,ParameterValue="${USERNAME}/${REPONAME}/prod/${USERNAME}_${REPONAME}.zip" \
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
  ParameterKey=snsTopicName,ParameterValue="${PREFIX: : -1}-sns" \
  ParameterKey=snsDisplayName,ParameterValue="Github Notification Service"
```
