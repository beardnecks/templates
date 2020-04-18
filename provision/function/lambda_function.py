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
    logger.info("Function was triggered!")
    logger.info(event)
