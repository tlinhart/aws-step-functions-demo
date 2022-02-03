from datetime import datetime
import functools
import json
import logging
import os
import random

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


# Setup logging.
logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))

# Initialize DynamoDB client.
dynamodb = boto3.client("dynamodb")

# Serializer and deserializer for DynamoDB types.
serializer = TypeSerializer()
deserializer = TypeDeserializer()

# Data pretty formatter.
pformat = functools.partial(
    json.dumps, ensure_ascii=False, indent=2, default=str
)


def serialize(data):
    """Serialize Python types to DynamoDB types."""
    return {k: serializer.serialize(v) for k, v in data.items()}


def deserialize(data):
    """Deserialize DynamoDB types to Python types."""
    return {k: deserializer.deserialize(v) for k, v in data.items()}


def lambda_handler(event, context):
    logger.debug("Input data:\n%s", pformat(event))

    if random.random() < float(os.environ["FAIL_RATE"]):
        raise Exception("Failed to cancel booking")

    key = {"trip_id": event["trip_id"]}
    try:
        response = dynamodb.update_item(
            TableName=os.environ["BOOKINGS_TABLE"],
            Key=serialize(key),
            ConditionExpression="#status <> :status",
            UpdateExpression="SET #status = :status, date_cancelled = :date",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues=serialize(
                {
                    ":status": "cancelled",
                    ":date": datetime.utcnow().isoformat(
                        timespec="milliseconds"
                    ),
                }
            ),
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(
                "Booking has already been cancelled for trip ID %s",
                key["trip_id"],
            )
            response = dynamodb.get_item(
                TableName=os.environ["BOOKINGS_TABLE"],
                Key=serialize(key),
                ConsistentRead=True,
            )
            item = deserialize(response["Item"])
            logger.debug("Item data:\n%s", pformat(item))
            result = {
                "status": item["status"],
                "date_cancelled": item["date_cancelled"],
            }
        else:
            raise
    else:
        logger.info("Cancelled booking for trip ID %s", key["trip_id"])
        item = deserialize(response["Attributes"])
        logger.debug("Item data:\n%s", pformat(item))
        result = {
            "status": item["status"],
            "date_cancelled": item["date_cancelled"],
        }

    logger.debug("Result:\n%s", pformat(result))
    return result
