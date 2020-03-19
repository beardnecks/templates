import base64
import json
import logging
import os
from enum import Enum
from zipfile import ZipFile

import requests
from boto3 import client, session
from botocore.exceptions import ClientError

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

PIPELINE_CONTEXT = "neckbeards-ci"


class GithubStatus(Enum):
    ERROR = "error"
    FAILURE = "failure"
    PENDING = "pending"
    SUCCESS = "success"


class BitbucketStatus(Enum):
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    INPROGRESS = "INPROGRESS"
    SUCCESSFUL = "SUCCESSFUL"


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
    STOPPED = "STOPPED"

    def get_description_from_pipeline_state(self, pipeline_state):
        switcher = {
            PipelineStates.STARTED: "The pipeline has started!",
            PipelineStates.RESUMED: "The pipeline has resumed",
            PipelineStates.SUPERSEDED: "The pipeline was superseded",
            PipelineStates.CANCELED: "The pipeline was canceled",
            PipelineStates.FAILED: "The pipeline failed",
            PipelineStates.SUCCEEDED: "The pipeline succeeded!",
            PipelineStates.STOPPED: "The pipeline was stopped!",
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
            PipelineStates.STOPPED: GithubStatus.ERROR,
        }
        return switcher[pipeline_state]

    def get_bitbucket_status_from_pipeline_state(self, pipeline_state):
        switcher = {
            PipelineStates.STARTED: BitbucketStatus.INPROGRESS,
            PipelineStates.RESUMED: BitbucketStatus.INPROGRESS,
            PipelineStates.SUPERSEDED: BitbucketStatus.INPROGRESS,
            PipelineStates.CANCELED: BitbucketStatus.FAILED,
            PipelineStates.FAILED: BitbucketStatus.FAILED,
            PipelineStates.SUCCEEDED: BitbucketStatus.SUCCESSFUL,
            PipelineStates.STOPPED: BitbucketStatus.STOPPED,
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
    STOPPED = "STOPPED"

    def get_description_from_stage_state(self, stage_state):
        switcher = {
            StageStates.STARTED: "The stage has started!",
            StageStates.RESUMED: "The stage has resumed",
            StageStates.CANCELED: "The stage was canceled",
            StageStates.FAILED: "The stage failed",
            StageStates.SUCCEEDED: "The stage succeeded!",
            StageStates.STOPPED: "The stage was stopped!",
        }
        return switcher[stage_state]

    def get_github_status_from_stage_state(self, stage_state):
        switcher = {
            StageStates.STARTED: GithubStatus.PENDING,
            StageStates.RESUMED: GithubStatus.PENDING,
            StageStates.CANCELED: GithubStatus.FAILURE,
            StageStates.FAILED: GithubStatus.FAILURE,
            StageStates.SUCCEEDED: GithubStatus.SUCCESS,
            StageStates.STOPPED: GithubStatus.ERROR,
        }
        return switcher[stage_state]

    def get_bitbucket_status_from_stage_state(self, stage_state):
        switcher = {
            StageStates.STARTED: BitbucketStatus.INPROGRESS,
            StageStates.RESUMED: BitbucketStatus.INPROGRESS,
            StageStates.CANCELED: BitbucketStatus.FAILED,
            StageStates.FAILED: BitbucketStatus.FAILED,
            StageStates.SUCCEEDED: BitbucketStatus.SUCCESSFUL,
            StageStates.STOPPED: BitbucketStatus.STOPPED,
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
    STOPPED = "STOPPED"
    ABANDONED = "ABANDONED"

    def get_description_from_action_state(self, action_state):
        switcher = {
            ActionStates.STARTED: "The action has started!",
            ActionStates.CANCELED: "The action was canceled",
            ActionStates.FAILED: "The action failed",
            ActionStates.SUCCEEDED: "The action succeeded!",
            ActionStates.STOPPED: "The action was stopped!",
            ActionStates.ABANDONED: "The action was abandoned!",
        }
        return switcher[action_state]

    def get_github_status_from_action_state(self, action_state):
        switcher = {
            ActionStates.STARTED: GithubStatus.PENDING,
            ActionStates.CANCELED: GithubStatus.FAILURE,
            ActionStates.FAILED: GithubStatus.FAILURE,
            ActionStates.SUCCEEDED: GithubStatus.SUCCESS,
            ActionStates.STOPPED: GithubStatus.ERROR,
            ActionStates.ABANDONED: GithubStatus.ERROR,
        }
        return switcher[action_state]

    def get_bitbucket_status_from_action_state(self, action_state):
        switcher = {
            ActionStates.STARTED: BitbucketStatus.INPROGRESS,
            ActionStates.CANCELED: BitbucketStatus.FAILED,
            ActionStates.FAILED: BitbucketStatus.FAILED,
            ActionStates.SUCCEEDED: BitbucketStatus.SUCCESSFUL,
            ActionStates.STOPPED: BitbucketStatus.STOPPED,
            ActionStates.ABANDONED: BitbucketStatus.STOPPED,
        }
        return switcher[action_state]


def update_github_status(
    state: str,
    context: str,
    description: str,
    target_url: str,
    commit_id: str,
    user: str,
    repo: str,
    pipeline_name: str,
):
    token = get_secret(pipeline_name)

    r = requests.post(
        "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + commit_id,
        json={
            "state": state,
            "context": context,
            "description": description,
            "target_url": target_url,
        },
        headers={"Authorization": "token " + token},
    )
    logger.info("Request response for commit id %s: %s" % (commit_id, r.status_code))
    return r


def action_change_gh(
    state: ActionStates,
    request: dict,
    stage: str,
    action: str,
    push: bool,
    user: str,
    repo: str,
    pipeline_name: str,
):
    if push:
        commit_id = request["body-json"]["head_commit"]["id"]
    else:
        commit_id = request["body-json"]["pull_request"]["head"]["sha"]

    logger.info("Commit id is: %s" % commit_id)

    update_github_status(
        state.get_github_status_from_action_state(state).value,
        PIPELINE_CONTEXT + "/" + stage + "/" + action,
        state.get_description_from_action_state(state),
        "http://localhost",
        commit_id,
        user,
        repo,
        pipeline_name,
    )


def update_bitbucket_status(
    state: str,
    context: str,
    description: str,
    target_url: str,
    link: str,
    pipeline_name: str,
):
    token = get_secret(pipeline_name)
    logger.info(token)
    base64_token = base64.b64encode(str.encode(token))
    logger.info("link is %s" % link + "/statuses/build")
    r = requests.post(
        link + "/statuses/build",
        json={
            "key": "build/%s" % context,
            "url": target_url,
            "state": state,
            "name": context,
            "description": description,
        },
        headers={"Authorization": "Basic " + base64_token.decode("utf-8")},
    )
    logger.info(
        "Request response for commit id %s: %s" % (link.split("/")[-1], r.status_code)
    )
    return r


def get_bb_commit_link(request: dict, push):
    if push:
        return request["body-json"]["push"]["changes"][0]["commits"][0]["links"][
            "self"
        ]["href"]

    return request["body-json"]["pullrequest"]["source"]["commit"]["links"]["self"][
        "href"
    ]


def action_change_bb(
    state: ActionStates,
    request: dict,
    stage: str,
    action: str,
    push: bool,
    pipeline_name: str,
):
    link = get_bb_commit_link(request, push)

    logger.info("Commit id is: %s" % link.split("/")[-1])

    update_bitbucket_status(
        state.get_bitbucket_status_from_action_state(state).value,
        PIPELINE_CONTEXT + "/" + stage + "/" + action,
        state.get_description_from_action_state(state),
        "http://localhost",
        link,
        pipeline_name,
    )


def update_all_stages_actions_gh(
    request: dict, push: bool, user: str, repo: str, pipeline_name: str,
):
    logger.info("Updating all stages/actions")
    codepipeline = client("codepipeline")

    pipeline = codepipeline.get_pipeline(name=pipeline_name)

    for stage in pipeline["pipeline"]["stages"]:
        if stage["name"] == "Source":
            logger.info("Skipping source stage")
            continue

        for action in stage["actions"]:
            logger.info("Updating action %s" % action["name"])
            action_change_gh(
                ActionStates.STARTED,
                request,
                stage["name"],
                action["name"],
                push,
                user,
                repo,
                pipeline_name,
            )


def update_all_stages_actions_bb(
    request: dict, push: bool, user: str, repo: str, pipeline_name: str,
):
    logger.info("Updating all stages/actions")
    codepipeline = client("codepipeline")

    pipeline = codepipeline.get_pipeline(name=pipeline_name)

    for stage in pipeline["pipeline"]["stages"]:
        if stage["name"] == "Source":
            logger.info("Skipping source stage")
            continue

        for action in stage["actions"]:
            logger.info("Updating action %s" % action["name"])
            action_change_bb(
                ActionStates.STARTED,
                request,
                stage["name"],
                action["name"],
                push,
                pipeline_name,
            )


def github_state_update(request: dict, message: dict):
    user = request["body-json"]["repository"]["full_name"].split("/")[0]
    repo = request["body-json"]["repository"]["full_name"].split("/")[1]

    push = False
    if request["params"]["header"]["X-GitHub-Event"] == "push":
        push = True

    logger.info(message["detail-type"])
    if message["detail-type"] == PIPELINE_CHANGE:
        logger.info(message["detail"]["state"])
        if message["detail"]["state"] == PipelineStates.STARTED.value:
            update_all_stages_actions_gh(
                request, push, user, repo, message["detail"]["pipeline"],
            )
        return

    if message["detail-type"] == ACTION_CHANGE:
        logger.info(message["detail"]["state"])
        for action_state in ActionStates:
            logger.info(action_state)
            if message["detail"]["state"] == action_state.value:
                logger.info("Stage change func")
                action_change_gh(
                    action_state,
                    request,
                    message["detail"]["stage"],
                    message["detail"]["action"],
                    push,
                    user,
                    repo,
                    message["detail"]["pipeline"],
                )

                return


def bitbucket_state_update(request: dict, message: dict):
    user = request["body-json"]["repository"]["full_name"].split("/")[0]
    repo = request["body-json"]["repository"]["full_name"].split("/")[1]

    push = False
    if request["params"]["header"]["X-Event-Key"] == "repo:push":
        push = True

    logger.info(message["detail-type"] + "  -:-  " + PIPELINE_CHANGE)
    if message["detail-type"] == PIPELINE_CHANGE:
        logger.info(message["detail"]["state"])
        if message["detail"]["state"] == PipelineStates.STARTED.value:
            update_all_stages_actions_bb(
                request, push, user, repo, message["detail"]["pipeline"],
            )

        return

    if message["detail-type"] == ACTION_CHANGE:
        logger.info(message["detail"]["state"])
        for action_state in ActionStates:
            logger.info(action_state)
            if message["detail"]["state"] == action_state.value:
                logger.info("Stage change func")
                action_change_bb(
                    action_state,
                    request,
                    message["detail"]["stage"],
                    message["detail"]["action"],
                    push,
                    message["detail"]["pipeline"],
                )

                return


def lambda_handler(event, context):
    print(event)
    message = json.loads(event["Records"][0]["Sns"]["Message"])

    source_bucket = os.environ["SOURCE_BUCKET"]
    source_bucket_object_key = os.environ["SOURCE_BUCKET_OBJECT_KEY"]
    s3 = client("s3")
    codepipeline = client("codepipeline")
    pipeline_execution = codepipeline.get_pipeline_execution(
        pipelineName=message["detail"]["pipeline"],
        pipelineExecutionId=message["detail"]["execution-id"],
    )
    s3_version_id = pipeline_execution["pipelineExecution"]["artifactRevisions"][0][
        "revisionId"
    ]
    logger.info(
        "Downloading source from s3://%s/%s with VersionId %s"
        % (source_bucket, source_bucket_object_key, s3_version_id)
    )
    s3.download_file(
        source_bucket,
        source_bucket_object_key,
        "/tmp/code.zip",
        ExtraArgs={"VersionId": s3_version_id},
    )
    logger.info("Unzipping top /tmp/code...")
    code_zip = ZipFile("/tmp/code.zip", "r")
    ZipFile.extractall(code_zip, "/tmp/code")

    # Open json file
    f = open("/tmp/code/event.json", "r")
    content = f.readline()
    request = json.loads(content)

    if "GitHub" in request["params"]["header"]["User-Agent"]:
        github_state_update(request, message)
    elif "Bitbucket" in request["params"]["header"]["User-Agent"]:
        bitbucket_state_update(request, message)
    else:
        logger.error("Unknown git host %s" % request["params"]["header"]["User-Agent"])
        raise Exception(
            "Unknown git host %s" % request["params"]["header"]["User-Agent"]
        )

    logger.error("Detail Type did not match pipeline, stage or action change!")


def get_secret(pipeline_name: str):
    region_name = os.environ["AWS_REGION"]
    secret_name = pipeline_name + "-NotifySecret"

    sess = session.Session()
    ssm_client = sess.client(service_name="secretsmanager", region_name=region_name,)

    try:
        logger.info(
            "Getting secret with name %s in region %s" % (secret_name, region_name)
        )
        get_secret_value_response = ssm_client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.error("The requested secret " + secret_name + " was not found")
        elif e.response["Error"]["Code"] == "InvalidRequestException":
            logger.error("The request was invalid due to: %s" % e)
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            logger.error("The request had invalid params: %s" % e)
        logger.error("Unknown error: %s" % e)
    else:
        logger.info("Returning %s" % get_secret_value_response["SecretString"])
        return get_secret_value_response["SecretString"]
