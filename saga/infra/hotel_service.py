import json
from typing import Optional

import pulumi
import pulumi_aws as aws


__all__ = ["HotelServiceArgs", "HotelService"]


class HotelServiceArgs:
    def __init__(
        self,
        book_hotel_fail_rate: float = 0.0,
        cancel_hotel_fail_rate: float = 0.0,
    ):
        self.book_hotel_fail_rate = book_hotel_fail_rate
        self.cancel_hotel_fail_rate = cancel_hotel_fail_rate


class HotelService(pulumi.ComponentResource):
    def __init__(
        self,
        name: str,
        args: HotelServiceArgs,
        opts: Optional[pulumi.ResourceOptions] = None,
    ):
        super().__init__("sfn-demo-saga:HotelService", name, {}, opts)

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

        self.book_hotel_lambda = aws.lambda_.Function(
            f"{name}-book-hotel",
            runtime="python3.8",
            code=pulumi.AssetArchive(
                {".": pulumi.FileArchive("../lambdas/book-hotel")}
            ),
            handler="lambda_function.lambda_handler",
            timeout=1,
            role=lambda_role.arn,
            publish=True,
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "BOOKINGS_TABLE": bookings_table.id,
                    "FAIL_RATE": str(args.book_hotel_fail_rate),
                }
            ),
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[lambda_role_policy]
            ),
        )

        aws.cloudwatch.LogGroup(
            f"{name}-book-hotel",
            name=self.book_hotel_lambda.name.apply(
                lambda name: f"/aws/lambda/{name}"
            ),
            retention_in_days=7,
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.book_hotel_lambda]
            ),
        )

        self.cancel_hotel_lambda = aws.lambda_.Function(
            f"{name}-cancel-hotel",
            runtime="python3.8",
            code=pulumi.AssetArchive(
                {".": pulumi.FileArchive("../lambdas/cancel-hotel")}
            ),
            handler="lambda_function.lambda_handler",
            timeout=1,
            role=lambda_role.arn,
            publish=True,
            environment=aws.lambda_.FunctionEnvironmentArgs(
                variables={
                    "BOOKINGS_TABLE": bookings_table.id,
                    "FAIL_RATE": str(args.cancel_hotel_fail_rate),
                }
            ),
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[lambda_role_policy]
            ),
        )

        aws.cloudwatch.LogGroup(
            f"{name}-cancel-hotel",
            name=self.cancel_hotel_lambda.name.apply(
                lambda name: f"/aws/lambda/{name}"
            ),
            retention_in_days=7,
            opts=pulumi.ResourceOptions(
                parent=self, depends_on=[self.cancel_hotel_lambda]
            ),
        )

        self.register_outputs({})
