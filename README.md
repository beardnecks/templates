# Cloudformation Templates
The master template will initiate the nested stacks to create the pipeline.

# Templates
The templates must be uploaded to an S3 bucket.

# Parameters
All parameters will be passed to the Master CFN tempalte which will then assign the correct values to the correct templates

# Example
```bash
# Example of how to deploy from cli
aws cloudformation create-stack --stack-name example-name --template-body file://.\master.json \
--capabilities CAPABILITY_IAM --parameters ParameterKey=UnitTestName,ParameterValue=example-name \
ParameterKey=VerifyTestName,ParameterValue=example-name \
ParameterKey=PackagingBuildName,ParameterValue=example-name \
ParameterKey=BuildImage,ParameterValue="imageName"
# Needs parameter keys and values for S3 URLs as well
```