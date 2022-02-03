import json
from typing import Optional

import pulumi
import pulumi_aws as aws


__all__ = ["FlightServiceArgs", "FlightService"]


class FlightServiceArgs:
    def __init__(
        self,
        book_flight_fail_rate: float = 0.0,
        cancel_flight_fail_rate: float = 0.0,
    ):
        self.book_flight_fail_rate = book_flight_fail_rate
        self.cancel_flight_fail_rate = cancel_flight_fail_rate


class FlightService(pulumi.ComponentResource):
    def __init__(
        self,
        name: str,
        args: FlightServiceArgs,
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("sfn-demo-saga:FlightService", name, {}, opts)

        bookings_table = aws.dynamodb.Table(
            f"{name}-bookings",
            attributes=[
                aws.dynamodb.TableAttributeArgs(name="trip_id", type="S"),
            ],
            billing_mode="PROVISIONED",
            hash_key="trip_id",
            read_capacity=1,
            write_capacity=1,
            opts=pulumi.ResourceOptions(parent=self),
        )

        lambda_role = aws.iam.Role(
            f"{name}-lambda-role",
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
            opts=pulumi.ResourceOptions(parent=self),
        )

        lambda_role_policy = aws.iam.RolePolicy(
            f"{name}-lambda-role-policy",
            role=lambda_role.id,
            policy=bookings_table.arn.apply(
                lambda bookings_table: json.dumps(
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
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "dynamodb:GetItem",
                                    "dynamodb:PutItem",
                                    "dynamodb:UpdateItem",
                                ],
                                "Resource": bookings_table,
                            },
                        ],
                    }
                )
            ),
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.book_flight_lambda = aws.lambda_.Function(
            f"{name}-book-flight",
            runtime="python3.8",
            code=pulumi.AssetArchive(
                {".": pulumi.FileArchive("../lambdas/book-flight")}
            ),
            handler="lambda_function.lambda_handler",
            timeout=1,
            role=lambda_role.arn,
            publish=True,
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "BOOKINGS_TABLE": bookings_table.id,
                    "FAIL_RATE": str(args.book_flight_fail_rate),
                }
            ),
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[lambda_role_policy]
            ),
        )

        aws.cloudwatch.LogGroup(
            f"{name}-book-flight",
            name=self.book_flight_lambda.name.apply(
                lambda name: f"/aws/lambda/{name}"
            ),
            retention_in_days=7,
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.book_flight_lambda]
            ),
        )

        self.cancel_flight_lambda = aws.lambda_.Function(
            f"{name}-cancel-flight",
            runtime="python3.8",
            code=pulumi.AssetArchive(
                {".": pulumi.FileArchive("../lambdas/cancel-flight")}
            ),
            handler="lambda_function.lambda_handler",
            timeout=1,
            role=lambda_role.arn,
            publish=True,
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "BOOKINGS_TABLE": bookings_table.id,
                    "FAIL_RATE": str(args.cancel_flight_fail_rate),
                }
            ),
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[lambda_role_policy]
            ),
        )

        aws.cloudwatch.LogGroup(
            f"{name}-cancel-flight",
            name=self.cancel_flight_lambda.name.apply(
                lambda name: f"/aws/lambda/{name}"
            ),
            retention_in_days=7,
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.cancel_flight_lambda]
            ),
        )

        self.register_outputs({})
