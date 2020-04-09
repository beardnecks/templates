"""Provides Github/Bitbucket build status updates

The function takes subscribes an SNS topic where CloudWatch publishes
pipeline, stage and action events. On pipeline start it will mark all the pipeline
actions as in progress on the relevant commit on either Bitbucket or Github, and
will continuously update the status as the progress continues.
"""

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

PIPELINE_CONTEXT = "neckbeards-ci"  # Prefix used for all build statuses, e.g. neckbeards-ci/testing/unittest


class GithubStatus(Enum):
    """Github build statuses
    """

    ERROR = "error"
    FAILURE = "failure"
    PENDING = "pending"
    SUCCESS = "success"


class BitbucketStatus(Enum):
    """Bitbucket build status
    """

    STOPPED = "STOPPED"
    FAILED = "FAILED"
    INPROGRESS = "INPROGRESS"
    SUCCESSFUL = "SUCCESSFUL"


class PipelineStates(Enum):
    """CodePipeline states

    Provides an enum of possible pipeline states. Provides
    functions to turn status into description, or to convert
    CodePipeline states into Bitbucket and Github statuses.
    """

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

    @staticmethod
    def get_description_from_pipeline_state(pipeline_state) -> str:
        """Returns description of provided pipeline state

        :param pipeline_state: A pipeline state for which to return description
        :return: A description of the provided state
        """

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

    @staticmethod
    def get_github_status_from_pipeline_state(pipeline_state) -> GithubStatus:
        """Convert a CodePipeline state into Github status

        :param pipeline_state: A pipeline state to convert
        :return: A matching GithubStatus
        """

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

    @staticmethod
    def get_bitbucket_status_from_pipeline_state(pipeline_state) -> BitbucketStatus:
        """Convert a CodePipeline state into Bitbucket status

        :param pipeline_state: A pipeline state to convert
        :return: A matching BitbucketStatus
        """

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
    """CodePipeline stage states

    Provides an enum of possible pipeline stage states. Provides
    functions to turn status into description, or to convert
    CodePipeline stage states into Bitbucket and Github statuses.
    """

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

    @staticmethod
    def get_description_from_stage_state(stage_state) -> str:
        """Returns description of provided pipeline stage state

        :param stage_state: A pipeline stage state for which to return description
        :return: A description of the provided state
        """

        switcher = {
            StageStates.STARTED: "The stage has started!",
            StageStates.RESUMED: "The stage has resumed",
            StageStates.CANCELED: "The stage was canceled",
            StageStates.FAILED: "The stage failed",
            StageStates.SUCCEEDED: "The stage succeeded!",
            StageStates.STOPPED: "The stage was stopped!",
        }
        return switcher[stage_state]

    @staticmethod
    def get_github_status_from_stage_state(stage_state) -> GithubStatus:
        """Convert a CodePipeline state into Github status

        :param stage_state: A pipeline stage state to convert
        :return: A matching GithubStatus
        """

        switcher = {
            StageStates.STARTED: GithubStatus.PENDING,
            StageStates.RESUMED: GithubStatus.PENDING,
            StageStates.CANCELED: GithubStatus.FAILURE,
            StageStates.FAILED: GithubStatus.FAILURE,
            StageStates.SUCCEEDED: GithubStatus.SUCCESS,
            StageStates.STOPPED: GithubStatus.ERROR,
        }
        return switcher[stage_state]

    @staticmethod
    def get_bitbucket_status_from_stage_state(stage_state) -> BitbucketStatus:
        """Convert a CodePipeline state into Bitbucket status

        :param stage_state: A pipeline stage state to convert
        :return: A matching BitbucketStatus
        """

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
    """CodePipeline action states

    Provides an enum of possible pipeline action states. Provides
    functions to turn status into description, or to convert
    CodePipeline action states into Bitbucket and Github statuses.
    """

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

    @staticmethod
    def get_description_from_action_state(action_state) -> str:
        """Returns description of provided pipeline action state

        :param action_state: A pipeline action state for which to return description
        :return: A description of the provided state
        """

        switcher = {
            ActionStates.STARTED: "The action has started!",
            ActionStates.CANCELED: "The action was canceled",
            ActionStates.FAILED: "The action failed",
            ActionStates.SUCCEEDED: "The action succeeded!",
            ActionStates.STOPPED: "The action was stopped!",
            ActionStates.ABANDONED: "The action was abandoned!",
        }
        return switcher[action_state]

    @staticmethod
    def get_github_status_from_action_state(action_state) -> GithubStatus:
        """Convert a CodePipeline action into Github status

        :param action_state: A pipeline action state to convert
        :return: A matching GithubStatus
        """

        switcher = {
            ActionStates.STARTED: GithubStatus.PENDING,
            ActionStates.CANCELED: GithubStatus.FAILURE,
            ActionStates.FAILED: GithubStatus.FAILURE,
            ActionStates.SUCCEEDED: GithubStatus.SUCCESS,
            ActionStates.STOPPED: GithubStatus.ERROR,
            ActionStates.ABANDONED: GithubStatus.ERROR,
        }
        return switcher[action_state]

    @staticmethod
    def get_bitbucket_status_from_action_state(action_state) -> BitbucketStatus:
        """Convert a CodePipeline action into Bitbucket status

        :param action_state: A pipeline action state to convert
        :return: A matching BitbucketStatus
        """

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
) -> requests.Response:
    """Update build status of commit using Github REST API

    Sends a post request to the Github REST API to update the
    build status of a given commit in a given repo.

    :param state: The build state
    :param context: What build status to update, e.g neckbeards-ci/unittest
    :param description: A description of the current status
    :param target_url: A url a user on Github can click for more information about the current build
    :param commit_id: The git commit sha to update the status on
    :param user: The user/organization hosting the repository
    :param repo: The name of the repository where the commit was made
    :param pipeline_name: The name of the pipeline that triggered the notification function.
            Used for getting the correct API token
    :return: Returns the post request response
    """

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
    """Updates the Github build status of a given action

    :param state: State of the action
    :param request: The original request received when the repo source was cloned.
    :param stage: What pipeline stage the action is in
    :param action: The name of the action
    :param push: If the request is a push or not
    :param user: The user/organization that hosts the repository
    :param repo: The name of the repository
    :param pipeline_name: The name of the pipeline running
    :return:
    """

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
) -> requests.Response:
    """Update build status of commit using Bitbucket REST API

    Sends a post request to the Bitbucket REST API to update the
    build status of a given commit in a given repo.

    :param state: The build state
    :param context: What build status to update, e.g neckbeards-ci/unittest
    :param description: A description of the current status
    :param target_url: A url a user on Github can click for more information about the current build
    :param link: API link to a given commit that should get status updated
    :param pipeline_name: The name of the pipeline that triggered the notification function.
            Used for getting the correct API token
    :return: Returns the post request response
    """

    token = get_secret(pipeline_name)
    logger.info(token)
    base64_token_bytes = base64.b64encode(str.encode(token))
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
        headers={"Authorization": "Basic " + base64_token_bytes.decode("utf-8")},
    )
    logger.info(
        "Request response for commit id %s: %s" % (link.split("/")[-1], r.status_code)
    )
    return r


def get_bb_commit_link(request: dict, push) -> str:
    """Returns API link to commit for a Bitbucket event

    :param request:  The original request received when the repo source was cloned.
    :param push: If the request is a push or not
    :return: A string with API url to the commit
    """

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
    """Updates the Bitbucket build status of a given action

    :param state: State of the action
    :param request: The original request received when the repo source was cloned.
    :param stage: What pipeline stage the action is in
    :param action: The name of the action
    :param push: If the request is a push or not
    :param pipeline_name: The name of the pipeline running
    :return:
    """

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


def pipeline_stop_skip_actions(
    codepipeline_client: client, pipeline_name: str, execution_id: str
):
    """Returns list of pipeline actions that have executed in a pipeline run

    Returns a list of pipeline actions that have executed in a pipeline run. This can be used to
    determine what actions in the pipeline have not yet executed.
    :param codepipeline_client: A boto3 codepipeline client
    :param pipeline_name: The name of the running pipeline
    :param execution_id: Execution ID of current pipeline run
    :return: List of actions to skip
    """
    skip_actions = []

    action_executions = codepipeline_client.list_action_executions(
        pipelineName=pipeline_name, filter={"pipelineExecutionId": execution_id}
    )
    logger.info("Action executions list")
    logger.info(action_executions)
    for action in action_executions["actionExecutionDetails"]:
        skip_actions.append(action["actionName"])

    return skip_actions


def update_all_stages_actions_gh(
    request: dict,
    push: bool,
    user: str,
    repo: str,
    pipeline_name: str,
    state: ActionStates,
    execution_id: str,
):
    """Set all pipeline actions as started on commit

    When the pipeline is started, get all the actions in the pipeline and set them all as started
    :param request: The original request received when the repo source was cloned.
    :param push: If the commit was a push or not
    :param user: The user/organization that hosts the repository
    :param repo: The name of the repository
    :param pipeline_name: The name of the running pipeline
    :param state: The action state to update to
    :param execution_id: Execution ID of current pipeline run
    :return:
    """

    logger.info("Updating all stages/actions")
    codepipeline = client("codepipeline")

    pipeline = codepipeline.get_pipeline(name=pipeline_name)

    skip_actions = []

    if state == ActionStates.STOPPED:
        skip_actions = pipeline_stop_skip_actions(
            codepipeline, pipeline_name, execution_id
        )

    for stage in pipeline["pipeline"]["stages"]:
        if stage["name"] == "Source":
            logger.info("Skipping source stage")
            continue

        for action in stage["actions"]:
            if action["name"] in skip_actions:
                logger.info("Skipping action %s" % action["name"])
                continue

            logger.info("Updating action %s" % action["name"])
            action_change_gh(
                state,
                request,
                stage["name"],
                action["name"],
                push,
                user,
                repo,
                pipeline_name,
            )


def update_all_stages_actions_bb(
    request: dict,
    push: bool,
    pipeline_name: str,
    state: ActionStates,
    execution_id: str,
):
    """Set all pipeline actions as started on commit

    When the pipeline is started, get all the actions in the pipeline and set them all as started
    :param request: The original request received when the repo source was cloned.
    :param push: If the commit was a push or not
    :param pipeline_name: The name of the running pipeline
    :param state: The action state to update to
    :param execution_id: Execution ID of current pipeline run
    :return:
    """

    logger.info("Updating all stages/actions")
    codepipeline = client("codepipeline")

    pipeline = codepipeline.get_pipeline(name=pipeline_name)

    skip_actions = []

    if state == ActionStates.STOPPED:
        skip_actions = pipeline_stop_skip_actions(
            codepipeline, pipeline_name, execution_id
        )

    for stage in pipeline["pipeline"]["stages"]:
        if stage["name"] == "Source":
            logger.info("Skipping source stage")
            continue

        for action in stage["actions"]:
            if action["name"] in skip_actions:
                logger.info("Skipping action %s" % action["name"])
                continue

            logger.info("Updating action %s" % action["name"])
            action_change_bb(
                state, request, stage["name"], action["name"], push, pipeline_name,
            )


def github_state_update(request: dict, message: dict):
    """Update the build state on a Github commit

    :param request: The original request received when the repo source was cloned.
    :param message: The message field from the SNS event
    :return:
    """

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
                request,
                push,
                user,
                repo,
                message["detail"]["pipeline"],
                ActionStates.STARTED,
                message["detail"]["execution-id"],
            )
        elif message["detail"]["state"] == PipelineStates.STOPPED.value:
            update_all_stages_actions_gh(
                request,
                push,
                user,
                repo,
                message["detail"]["pipeline"],
                ActionStates.STOPPED,
                message["detail"]["execution-id"],
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
    """Update the build state on a Bitbucket commit

    :param request: The original request received when the repo source was cloned.
    :param message: The message field from the SNS event
    :return:
    """

    push = False
    if request["params"]["header"]["X-Event-Key"] == "repo:push":
        push = True

    logger.info(message["detail-type"])
    if message["detail-type"] == PIPELINE_CHANGE:
        logger.info(message["detail"]["state"])
        if message["detail"]["state"] == PipelineStates.STARTED.value:
            update_all_stages_actions_bb(
                request,
                push,
                message["detail"]["pipeline"],
                ActionStates.STARTED,
                message["detail"]["execution-id"],
            )
        elif message["detail"]["state"] == PipelineStates.STOPPED.value:
            update_all_stages_actions_bb(
                request,
                push,
                message["detail"]["pipeline"],
                ActionStates.STOPPED,
                message["detail"]["execution-id"],
            )

        return  # The state change is not action, no point in going further

    if message["detail-type"] == ACTION_CHANGE:
        logger.info(message["detail"]["state"])
        for action_state in ActionStates:
            logger.info(action_state)
            if message["detail"]["state"] == action_state.value:
                logger.info("Updating pipeline action %s" % message["detail"]["action"])
                action_change_bb(
                    action_state,
                    request,
                    message["detail"]["stage"],
                    message["detail"]["action"],
                    push,
                    message["detail"]["pipeline"],
                )

                return  # Found matching action, return and skip rest of for loop


def lambda_handler(event, context):
    """Update build status for a git repository based on pipeline events

    :param event: Lambda event information provided by SNS
    :param context: Not used
    :return:
    """

    logger.info(event)
    message = json.loads(event["Records"][0]["Sns"]["Message"])

    source_bucket = os.environ["SOURCE_BUCKET"]
    source_bucket_object_key = os.environ["SOURCE_BUCKET_OBJECT_KEY"]

    s3 = client("s3")
    codepipeline = client("codepipeline")

    # Get S3 file version of the source zip used in the pipeline execution to get the correct version.
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

    # Open json file containing event data from when the source zip was created
    f = open("/tmp/code/event.json", "r")
    content = f.readline()
    request = json.loads(content)

    if "GitHub" in request["params"]["header"]["User-Agent"]:
        github_state_update(request, message)
        return
    elif "Bitbucket" in request["params"]["header"]["User-Agent"]:
        bitbucket_state_update(request, message)
        return

    logger.error("Unknown git host %s" % request["params"]["header"]["User-Agent"])
    raise Exception("Unknown git host %s" % request["params"]["header"]["User-Agent"])


def get_secret(pipeline_name: str) -> str:
    """Get API secret from SecretsManager for a given pipeline

    :param pipeline_name: Name of the executing pipeline
    :return: The secret
    """

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
