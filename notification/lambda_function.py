import json
import os

import boto3
import requests

# need to get sha of PR commit
# need to get user that owns repo
# need to get repo name


def lambda_handler(event, context):
    token = os.environ["TOKEN"]
    # test values
    # sha = os.environ['SHA']
    user = "beardnecks"
    repo = "suricata"
    pullrequests = requests.get(
        "https://api.github.com/repos/" + user + "/" + repo + "/pulls",
        headers={"Authorization": "token " + token},
    )
    if len(pullrequests.json()) > 0:
        sha = pullrequests.json()[0]["head"]["sha"]
    else:
        # Only looks at push to master bran
        pushes_to_master = requests.get(
            "https://api.github.com/repos/" + user + "/" + repo + "/commits/master",
            headers={"Authorization": "token " + token},
        )
        sha = pushes_to_master.json()["sha"]

    # event['records'][0]['Sns']['Message'] content looks like json, but it is a string
    # Convert string to json
    message = event["Records"][0]["Sns"]["Message"]
    parsed_message = json.loads(message)
    print(sha)

    if parsed_message["detail"]["state"] == "STARTED":
        r = requests.post(
            "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + sha,
            json={
                "state": "pending",
                "context": "AWS-CodePipeline",
                "description": "Started!",
                "target_url": "http://localhost",
            },
            headers={"Authorization": "token " + token},
        )
        print(r)
        print("Started! State is %s" % parsed_message["detail"]["state"])
    elif parsed_message["detail"]["state"] == "SUCCEEDED":
        r = requests.post(
            "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + sha,
            json={
                "state": "success",
                "context": "AWS-CodePipeline",
                "description": "SUCCEEDED",
                "target_url": "http://localhost",
            },
            headers={"Authorization": "token " + token},
        )
        print("Succeeded! State is %s" % parsed_message["detail"]["state"])
    elif parsed_message["detail"]["state"] == "FAILED":
        r = requests.post(
            "https://api.github.com/repos/" + user + "/" + repo + "/statuses/" + sha,
            json={
                "state": "failure",
                "context": "AWS-CodePipeline",
                "description": "FAILED",
                "target_url": "http://localhost",
            },
            headers={"Authorization": "token " + token},
        )
        print("Failed! State is %s" % parsed_message["detail"]["state"])
    else:
        print("No such event. %s. Function failed" % parsed_message["detail"]["state"])

    # ADD CLEANUP
    return "state was %s" % parsed_message["detail"]["state"]
