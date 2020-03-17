#!/bin/bash
PREFIX="t-joachim/"
STACKNAME="p-joachim-pipeline"
sam build --use-container -t notification/function/template.yaml
sam package -t .aws-sam/build/notificationFunction/template.yaml --s3-bucket t-neckbeards-stackinit-s --use-json --output-template-file notification/function.json --s3-prefix ${PREFIX: : -1}
aws s3 cp prod-master.json s3://t-neckbeards-stackinit-s/${PREFIX}
aws s3 cp dev-master.json s3://t-neckbeards-stackinit-s/${PREFIX}
aws s3 cp notification/function.json s3://t-neckbeards-stackinit-s/${PREFIX}notification/
aws s3 cp --recursive codeBuild s3://t-neckbeards-stackinit-s/${PREFIX}codeBuild/
aws s3 cp --recursive codePipeline s3://t-neckbeards-stackinit-s/${PREFIX}codePipeline/
aws cloudformation create-stack --stack-name ${STACKNAME} --template-body file://prod-master.json \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND --parameters \
  ParameterKey=UnitTestBuildSpecFileName,ParameterValue="qa/buildspec/unittest.yml" \
  ParameterKey=VerifyBuildSpecFileName,ParameterValue="qa/buildspec/suricata-verify.yml" \
  ParameterKey=CoccinelleBuildSpecFileName,ParameterValue="qa/buildspec/coccinelle.yml" \
  ParameterKey=ClangBuildSpecFileName,ParameterValue="qa/buildspec/clang.yml" \
  ParameterKey=RustBuildSpecFileName,ParameterValue="qa/buildspec/rust.yml" \
  ParameterKey=BuildImage,ParameterValue="389941814333.dkr.ecr.eu-west-1.amazonaws.com/build/suricata-devops:centos8" \
  ParameterKey=CoccinelleBuildImage,ParameterValue="389941814333.dkr.ecr.eu-west-1.amazonaws.com/build/suricata-coccinelle:ubuntu18.04" \
  ParameterKey=ArtifactStoreName,ParameterValue="artifactstore" \
  ParameterKey=PipelineName,ParameterValue=${STACKNAME} \
  ParameterKey=SourceBucket,ParameterValue="t-martin-outputbucket" \
  ParameterKey=SourceBucketObjectKey,ParameterValue="beardnecks/suricata/dev/beardnecks_suricata.zip" \
  ParameterKey=PipelineTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}codePipeline/dev-pipeline.json" \
  ParameterKey=UnitTestTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/unittest.json" \
  ParameterKey=VerifyTestTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/verify.json" \
  ParameterKey=CoccinelleTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/coccinelle.json" \
  ParameterKey=ClangTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/clang.json" \
  ParameterKey=RustTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}codeBuild/rust.json" \
  ParameterKey=NotificationTemplateURL,ParameterValue="https://t-neckbeards-stackinit-s.s3-eu-west-1.amazonaws.com/${PREFIX}notification/function.json" \
  ParameterKey=token,ParameterValue="insert_token_here" \
  ParameterKey=snsTopicName,ParameterValue="${PREFIX: : -1}-sns" \
  ParameterKey=snsDisplayName,ParameterValue="Github Notification Service"
