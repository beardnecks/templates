import json
import logging
import os
from zipfile import ZipFile

import requests
from boto3 import client
from github import Github

# need to get sha of PR commit
# need to get user that owns repo
# need to get repo name

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers[0].setFormatter(
    logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s")
)
logging.getLogger("boto3").setLevel(logging.ERROR)
logging.getLogger("botocore").setLevel(logging.ERROR)


def lambda_handler(event, context):
    print(event)
    token = os.environ["TOKEN"]
    source_bucket = os.environ["SOURCE_BUCKET"]
    source_bucket_object_key = os.environ["SOURCE_BUCKET_OBJECT_KEY"]
    print(source_bucket)
    print(source_bucket_object_key)
    s3 = client("s3")
    g = Github(token)

    logger.info("Downloading source from s3")
    s3.download_file(source_bucket, source_bucket_object_key, "/tmp/code.zip")
    logger.info("Unzipping...")
    code_zip = ZipFile("/tmp/code.zip", "r")
    ZipFile.extractall(code_zip, "/tmp/code")
    print(os.listdir("/tmp/code"))
    #
    # pull_requests = requests.get(
    #     "https://api.github.com/repos/" + user + "/" + repo + "/pulls",
    #     headers={"Authorization": "token " + token},
    # )
    # if len(pull_requests.json()) > 0:
    #     sha = pull_requests.json()[0]["head"]["sha"]
    # else:
    #     # Only looks at push to master branch
    #     pushes_to_master = requests.get(
    #         "https://api.github.com/repos/" + user + "/" + repo + "/commits/master",
    #         headers={"Authorization": "token " + token},
    #     )
    #     sha = pushes_to_master.json()["sha"]
    #
    # # event['records'][0]['Sns']['Message'] content looks like json, but it is a string
    # # Convert string to json
    # message = event["Records"][0]["Sns"]["Message"]
    # parsed_message = json.loads(message)
    # print(sha)
    #
    # if parsed_message["detail"]["state"] == "STARTED":
    #     r = requests.post(
    #         "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + sha,
    #         json={
    #             "state": "pending",
    #             "context": "AWS-CodePipeline",
    #             "description": "Started!",
    #             "target_url": "http://localhost",
    #         },
    #         headers={"Authorization": "token " + token},
    #     )
    #     print(r)
    #     print("Started! State is %s" % parsed_message["detail"]["state"])
    # elif parsed_message["detail"]["state"] == "SUCCEEDED":
    #     r = requests.post(
    #         "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + sha,
    #         json={
    #             "state": "success",
    #             "context": "AWS-CodePipeline",
    #             "description": "SUCCEEDED",
    #             "target_url": "http://localhost",
    #         },
    #         headers={"Authorization": "token " + token},
    #     )
    #     print("Succeeded! State is %s" % parsed_message["detail"]["state"])
    # elif parsed_message["detail"]["state"] == "FAILED":
    #     r = requests.post(
    #         "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + sha,
    #         json={
    #             "state": "failure",
    #             "context": "AWS-CodePipeline",
    #             "description": "FAILED",
    #             "target_url": "http://localhost",
    #         },
    #         headers={"Authorization": "token " + token},
    #     )
    #     print("Failed! State is %s" % parsed_message["detail"]["state"])
    # else:
    #     print("No such event. %s. Function failed" % parsed_message["detail"]["state"])
    #
    # # ADD CLEANUP
    return "Function finished :)"
