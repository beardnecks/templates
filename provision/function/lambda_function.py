"""Provisions codepipeline pipelines on demand

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


def lambda_handler(event, context):
    """Update build status for a git repository based on pipeline events

    :param event: Lambda event information provided by SNS
    :param context: Not used
    :return:
    """
    pipeline_prefix = os.environ["PIPELINE_NAME"]

    logger.info("Function was triggered!")
    logger.info(event)

    updated_file = event["detail"]["requestParameters"]["key"]

    if ".zip" not in updated_file:
        logger.error("File is not a source code zip file, ignoring")
        return

    # Get branch
    branch = updated_file.replace(".zip", "").rsplit("/", 1)[1]
    logger.info("Branch is %s" % branch)

    # Check if pipeline for that branch already exists

    codepipeline = client("codepipeline")
    response = codepipeline.list_pipelines()
    pipelines = response["pipelines"]

    logger.info(response)

    while "nextToken" in response:
        response = codepipeline.list_pipelines(nextToken=response["nextToken"])
        pipelines.extend(response["pipelines"])
        logger.info("nextToken: %s" % response["nextToken"])

    logger.info("Pipelines: ")
    logger.info(pipelines)

    for pipeline in pipelines:
        if "%s-%s" % (pipeline_prefix, branch) in pipeline["name"]:
            logger.error("Pipeline already exists for branch, exiting...")
            return

    # Create pipeline
    logger.info("Pipeline does not exist for current branch, creating...")
