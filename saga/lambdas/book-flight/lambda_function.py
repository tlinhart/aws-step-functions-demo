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


class BookingCancelledError(Exception):
    """Booking has already been cancelled."""


def serialize(data):
    """Serialize Python types to DynamoDB types."""
    return {k: serializer.serialize(v) for k, v in data.items()}


def deserialize(data):
    """Deserialize DynamoDB types to Python types."""
    return {k: deserializer.deserialize(v) for k, v in data.items()}


def lambda_handler(event, context):
    logger.debug("Input data:\n%s", pformat(event))

    if random.random() < float(os.environ["FAIL_RATE"]):
        raise Exception("Failed to create booking")

    item = {
        "trip_id": event["trip_id"],
        "depart": event["depart"],
        "depart_at": event["depart_at"],
        "arrive": event["arrive"],
        "arrive_at": event["arrive_at"],
        "status": "booked",
        "date_booked": datetime.utcnow().isoformat(timespec="milliseconds"),
    }
    try:
        dynamodb.put_item(
            TableName=os.environ["BOOKINGS_TABLE"],
            Item=serialize(item),
            ConditionExpression="attribute_not_exists(trip_id)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            logger.warning(
                "Booking already exists for trip ID %s", item["trip_id"]
            )
            key = {"trip_id": item["trip_id"]}
            response = dynamodb.get_item(
                TableName=os.environ["BOOKINGS_TABLE"],
                Key=serialize(key),
                ConsistentRead=True,
            )
            item = deserialize(response["Item"])
            logger.debug("Item data:\n%s", pformat(item))
            if item["status"] == "booked":
                result = {
                    "status": item["status"],
                    "date_booked": item["date_booked"],
                }
            elif item["status"] == "cancelled":
                raise BookingCancelledError(
                    "Booking has already been cancelled"
                ) from None
        else:
            raise
    else:
        logger.info("Created booking for trip ID %s", item["trip_id"])
        result = {"status": item["status"], "date_booked": item["date_booked"]}

    logger.debug("Result:\n%s", pformat(result))
    return result
