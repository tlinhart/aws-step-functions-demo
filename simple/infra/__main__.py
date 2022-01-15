import json

import pulumi
import pulumi_aws as aws
from pulumi_aws_tags import register_auto_tags


# Automatically inject tags to created AWS resources.
register_auto_tags(
    {"user:Project": pulumi.get_project(), "user:Stack": pulumi.get_stack()}
)

# Create a role for Lambda functions.
lambda_role = aws.iam.Role(
    "sfn-demo-simple-lambda-role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Effect": "Allow",
                    "Sid": "",
                }
            ],
        }
    ),
)

lambda_role_policy = aws.iam.RolePolicy(
    "sfn-demo-simple-lambda-role-policy",
    role=lambda_role.id,
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": "arn:aws:logs:*:*:*",
                }
            ],
        }
    ),
)

# Create the Lambda functions and log groups (to be able to specify retention).
greet_lambda = aws.lambda_.Function(
    "sfn-demo-simple-greet",
    runtime="python3.8",
    code=pulumi.AssetArchive({".": pulumi.FileArchive("../lambdas/greet")}),
    handler="lambda_function.lambda_handler",
    timeout=1,
    role=lambda_role.arn,
    publish=True,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role_policy]),
)

greet_lambda_log_group = aws.cloudwatch.LogGroup(
    "sfn-demo-simple-greet",
    name=greet_lambda.name.apply(lambda name: f"/aws/lambda/{name}"),
    retention_in_days=7,
    opts=pulumi.ResourceOptions(depends_on=[greet_lambda]),
)

reply_lambda = aws.lambda_.Function(
    "sfn-demo-simple-reply",
    runtime="python3.8",
    code=pulumi.AssetArchive({".": pulumi.FileArchive("../lambdas/reply")}),
    handler="lambda_function.lambda_handler",
    timeout=1,
    role=lambda_role.arn,
    publish=True,
    opts=pulumi.ResourceOptions(depends_on=[lambda_role_policy]),
)

reply_lambda_log_group = aws.cloudwatch.LogGroup(
    "sfn-demo-simple-reply",
    name=reply_lambda.name.apply(lambda name: f"/aws/lambda/{name}"),
    retention_in_days=7,
    opts=pulumi.ResourceOptions(depends_on=[reply_lambda]),
)

# Create a role for state machine.
state_machine_role = aws.iam.Role(
    "sfn-demo-simple-state-machine-role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": f"states.{aws.config.region}.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    ),
)

state_machine_role_policy = aws.iam.RolePolicy(
    "sfn-demo-simple-state-machine-role-policy",
    role=state_machine_role.id,
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["lambda:InvokeFunction"],
                    "Resource": "*",
                }
            ],
        }
    ),
)

# Create the state machine.
state_machine = aws.sfn.StateMachine(
    "sfn-demo-simple-state-machine",
    role_arn=state_machine_role.arn,
    definition=pulumi.Output.all(
        greet_lambda=greet_lambda.arn, reply_lambda=reply_lambda.arn
    ).apply(
        lambda args: json.dumps(
            {
                "Comment": "Simple demo of AWS Step Functions",
                "StartAt": "Greet",
                "States": {
                    "Greet": {
                        "Type": "Task",
                        "Resource": args["greet_lambda"],
                        "ResultPath": None,
                        "Next": "Reply",
                    },
                    "Reply": {
                        "Type": "Task",
                        "Resource": args["reply_lambda"],
                        "End": True,
                    },
                },
            }
        )
    ),
)

# Export stack outputs.
pulumi.export("state_machine", state_machine.id)
