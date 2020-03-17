import json
import logging
import os
from enum import Enum
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

PIPELINE_CHANGE = "CodePipeline Pipeline Execution State Change"
STAGE_CHANGE = "CodePipeline Stage Execution State Change"
ACTION_CHANGE = "CodePipeline Action Execution State Change"

STARTED = "STARTED"

user = "beardnecks"
repo = "suricata"
token = os.environ["TOKEN"]


class GithubStatus(Enum):
    ERROR = "error"
    FAILURE = "failure"
    PENDING = "pending"
    SUCCESS = "success"


class PipelineStates(Enum):
    # The pipeline execution is currently running.
    STARTED = "STARTED"
    # The pipeline execution was completed successfully.
    SUCCEEDED = "SUCCEEDED"
    # A failed pipeline execution has been retried in response to the RetryStageExecution API call.
    RESUMED = "RESUMED"
    # The pipeline execution was not completed successfully.
    FAILED = "FAILED"
    # The pipeline execution was canceled because the pipeline structure was updated.
    CANCELED = "CANCELED"
    # While this pipeline execution was waiting for the next stage to be completed,
    # a newer pipeline execution advanced and continued through the pipeline instead.
    SUPERSEDED = "SUPERSEDED"

    def get_description_from_pipeline_state(self, pipeline_state):
        switcher = {
            PipelineStates.STARTED: "The pipeline has started!",
            PipelineStates.RESUMED: "The pipeline has resumed",
            PipelineStates.SUPERSEDED: "The pipeline was superseded",
            PipelineStates.CANCELED: "The pipeline was canceled",
            PipelineStates.FAILED: "The pipeline failed",
            PipelineStates.SUCCEEDED: "The pipeline succeeded!",
        }
        return switcher[pipeline_state]

    def get_github_status_from_pipeline_state(self, pipeline_state):
        switcher = {
            PipelineStates.STARTED: GithubStatus.PENDING,
            PipelineStates.RESUMED: GithubStatus.PENDING,
            PipelineStates.SUPERSEDED: GithubStatus.PENDING,
            PipelineStates.CANCELED: GithubStatus.FAILURE,
            PipelineStates.FAILED: GithubStatus.FAILURE,
            PipelineStates.SUCCEEDED: GithubStatus.SUCCESS,
        }
        return switcher[pipeline_state]


class StageStates(Enum):
    # The stage is currently running.
    STARTED = "STARTED"
    # The stage was completed successfully.
    SUCCEEDED = "SUCCEEDED"
    # A failed stage has been retried in response to the RetryStageExecution API call.
    RESUMED = "RESUMED"
    # The stage was not completed successfully.
    FAILED = "FAILED"
    # The stage was canceled because the pipeline structure was updated.
    CANCELED = "CANCELED"

    def get_description_from_stage_state(self, stage_state):
        switcher = {
            StageStates.STARTED: "The pipeline has started!",
            StageStates.RESUMED: "The pipeline has resumed",
            StageStates.CANCELED: "The pipeline was canceled",
            StageStates.FAILED: "The pipeline failed",
            StageStates.SUCCEEDED: "The pipeline succeeded!",
        }
        return switcher[stage_state]

    def get_github_status_from_stage_state(self, stage_state):
        switcher = {
            StageStates.STARTED: GithubStatus.PENDING,
            StageStates.RESUMED: GithubStatus.PENDING,
            StageStates.CANCELED: GithubStatus.FAILURE,
            StageStates.FAILED: GithubStatus.FAILURE,
            StageStates.SUCCEEDED: GithubStatus.SUCCESS,
        }
        return switcher[stage_state]


class ActionStates(Enum):
    # The action is currently running.
    STARTED = "STARTED"
    # The action was completed successfully.
    SUCCEEDED = "SUCCEEDED"
    # For Approval actions, the FAILED state means the action was either
    # rejected by the reviewer or failed due to an incorrect action configuration.
    FAILED = "FAILED"
    # The action was canceled because the pipeline structure was updated.
    CANCELED = "CANCELED"


PIPELINE_CONTEXT = "neckbeards-ci"


def update_pipeline_status(
    pipeline_state: PipelineStates,
    context: str,
    description: str,
    target_url: str,
    commit_id: str,
):
    r = requests.post(
        "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + commit_id,
        json={
            "state": pipeline_state.get_github_status_from_pipeline_state(
                pipeline_state
            ),
            "context": context,
            "description": pipeline_state.get_description_from_pipeline_state(
                pipeline_state
            ),
            "target_url": target_url,
        },
        headers={"Authorization": "token " + token},
    )
    logger.info("Request response for commit id %s: %s" % (commit_id, r.status_code))
    return r


def update_stage_status(
    stage_state: StageStates,
    context: str,
    description: str,
    target_url: str,
    commit_id: str,
):
    r = requests.post(
        "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + commit_id,
        json={
            "state": stage_state.get_github_status_from_stage_state(stage_state),
            "context": context,
            "description": stage_state.get_description_from_stage_state(stage_state),
            "target_url": target_url,
        },
        headers={"Authorization": "token " + token},
    )
    logger.info("Request response for commit id %s: %s" % (commit_id, r.status_code))
    return r


def pipeline_change(state: str, request: dict, push: bool):
    if push:
        commit_id = request["body-json"]["head_commit"]["id"]
    else:
        commit_id = request["body-json"]["pull_request"]["head"]["sha"]

    logger.info("Commit id is: %s" % commit_id)

    for pstate in PipelineStates:
        if state == pstate:
            update_pipeline_status(
                pstate,
                PIPELINE_CONTEXT,
                "The pipeline is %s" % pstate,
                "http://localhost",
                commit_id,
            )

    print("test")


def stage_change(state: str, request: dict, stage: str, push: bool):
    if push:
        commit_id = request["body-json"]["head_commit"]["id"]
    else:
        commit_id = request["body-json"]["pull_request"]["head"]["sha"]

    logger.info("Commit id is: %s" % commit_id)

    for sstate in StageStates:
        if state == sstate:
            update_stage_status(
                sstate,
                PIPELINE_CONTEXT + "/",
                "The stage is %s" % sstate,
                "http://localhost",
                commit_id,
            )

    print("test")


def lambda_handler(event, context):
    print(event)
    source_bucket = os.environ["SOURCE_BUCKET"]
    source_bucket_object_key = os.environ["SOURCE_BUCKET_OBJECT_KEY"]
    print(source_bucket)
    print(source_bucket_object_key)
    s3 = client("s3")

    logger.info("Downloading source from s3")
    s3.download_file(source_bucket, source_bucket_object_key, "/tmp/code.zip")
    logger.info("Unzipping...")
    code_zip = ZipFile("/tmp/code.zip", "r")
    ZipFile.extractall(code_zip, "/tmp/code")

    # Open json file
    f = open("/tmp/code/event.json", "r")
    content = f.readline()
    request = json.loads(content)

    pr = False
    push = True
    if request["params"]["header"]["X-GitHub-Event"] == "pull_request":
        pr = True
    elif request["params"]["header"]["X-GitHub-Event"] == "push":
        push = True

    message = json.loads(event["Records"][0]["Sns"]["Message"])
    logger.info(message["detail-type"] + "  -:-  " + PIPELINE_CHANGE)
    if message["detail-type"] == PIPELINE_CHANGE:
        logger.info(message["detail"]["state"] + "  -:-  " + STARTED)
        for pstate in PipelineStates:
            if message["detail"]["state"] == pstate:
                logger.info("Pipeline change func")
                pipeline_change(pstate, request, push)
    elif message["detail-type"] == STAGE_CHANGE:
        logger.info(message["detail"]["state"] + "  -:-  " + STARTED)
        for pstate in PipelineStates:
            if message["detail"]["state"] == pstate:
                logger.info("Stage change func")
                stage_change(pstate, request, message["detail"]["stage"], push)

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
