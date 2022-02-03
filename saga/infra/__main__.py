import json

import pulumi
import pulumi_aws as aws
from pulumi_aws_tags import register_auto_tags

from car_service import CarService, CarServiceArgs
from flight_service import FlightService, FlightServiceArgs
from hotel_service import HotelService, HotelServiceArgs


config = pulumi.Config()

# Automatically inject tags to created AWS resources.
register_auto_tags(
    {"user:Project": pulumi.get_project(), "user:Stack": pulumi.get_stack()}
)

# Create a hotel booking service.
service_args = {
    "book_hotel_fail_rate": config.get_float("book_hotel_fail_rate"),
    "cancel_hotel_fail_rate": config.get_float("cancel_hotel_fail_rate"),
}
service_args = {k: v for k, v in service_args.items() if v is not None}
hotel_service = HotelService(
    "sfn-demo-saga-hotel-service", HotelServiceArgs(**service_args)
)

# Create a flight booking service.
service_args = {
    "book_flight_fail_rate": config.get_float("book_flight_fail_rate"),
    "cancel_flight_fail_rate": config.get_float("cancel_flight_fail_rate"),
}
service_args = {k: v for k, v in service_args.items() if v is not None}
flight_service = FlightService(
    "sfn-demo-saga-flight-service", FlightServiceArgs(**service_args)
)

# Create a car booking service.
service_args = {
    "book_car_fail_rate": config.get_float("book_car_fail_rate"),
    "cancel_car_fail_rate": config.get_float("cancel_car_fail_rate"),
}
service_args = {k: v for k, v in service_args.items() if v is not None}
car_service = CarService(
    "sfn-demo-saga-car-service", CarServiceArgs(**service_args)
)

# Create a role for state machine.
state_machine_role = aws.iam.Role(
    "sfn-demo-saga-state-machine-role",
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
    "sfn-demo-saga-state-machine-role-policy",
    role=state_machine_role.id,
    policy=pulumi.Output.all(
        book_hotel_lambda=hotel_service.book_hotel_lambda.arn,
        cancel_hotel_lambda=hotel_service.cancel_hotel_lambda.arn,
        book_flight_lambda=flight_service.book_flight_lambda.arn,
        cancel_flight_lambda=flight_service.cancel_flight_lambda.arn,
        book_car_lambda=car_service.book_car_lambda.arn,
        cancel_car_lambda=car_service.cancel_car_lambda.arn,
    ).apply(
        lambda args: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["lambda:InvokeFunction"],
                        "Resource": [
                            args["book_hotel_lambda"],
                            args["cancel_hotel_lambda"],
                            args["book_flight_lambda"],
                            args["cancel_flight_lambda"],
                            args["book_car_lambda"],
                            args["cancel_car_lambda"],
                        ],
                    }
                ],
            }
        )
    ),
)

# Create the state machine.
state_machine = aws.sfn.StateMachine(
    "sfn-demo-saga-state-machine",
    role_arn=state_machine_role.arn,
    definition=pulumi.Output.all(
        book_hotel_lambda=hotel_service.book_hotel_lambda.name,
        cancel_hotel_lambda=hotel_service.cancel_hotel_lambda.name,
        book_flight_lambda=flight_service.book_flight_lambda.name,
        cancel_flight_lambda=flight_service.cancel_flight_lambda.name,
        book_car_lambda=car_service.book_car_lambda.name,
        cancel_car_lambda=car_service.cancel_car_lambda.name,
    ).apply(
        lambda args: json.dumps(
            {
                "Comment": "Saga pattern demo using AWS Step Functions",
                "StartAt": "BookTrip",
                "States": {
                    "BookTrip": {
                        "Type": "Parallel",
                        "Branches": [
                            {
                                "StartAt": "BookHotel",
                                "States": {
                                    "BookHotel": {
                                        "Type": "Task",
                                        "Resource": "arn:aws:states:::lambda:invoke",  # noqa: E501
                                        "Parameters": {
                                            "FunctionName": args[
                                                "book_hotel_lambda"
                                            ],
                                            "Payload": {
                                                "trip_id.$": "$.trip_id",
                                                "hotel.$": "$.hotel",
                                                "check_in.$": "$.check_in",
                                                "check_out.$": "$.check_out",
                                            },
                                        },
                                        "ResultSelector": {
                                            "result.$": "$.Payload"
                                        },
                                        "ResultPath": "$",
                                        "Retry": [
                                            {
                                                "ErrorEquals": [
                                                    "Lambda.ServiceException",
                                                    "Lambda.AWSLambdaException",  # noqa: E501
                                                    "Lambda.SdkClientException",  # noqa: E501
                                                ],
                                                "IntervalSeconds": 1,
                                                "MaxAttempts": 5,
                                                "BackoffRate": 2,
                                            }
                                        ],
                                        "End": True,
                                    }
                                },
                            },
                            {
                                "StartAt": "BookFlight",
                                "States": {
                                    "BookFlight": {
                                        "Type": "Task",
                                        "Resource": "arn:aws:states:::lambda:invoke",  # noqa: E501
                                        "Parameters": {
                                            "FunctionName": args[
                                                "book_flight_lambda"
                                            ],
                                            "Payload": {
                                                "trip_id.$": "$.trip_id",
                                                "depart.$": "$.depart",
                                                "depart_at.$": "$.depart_at",
                                                "arrive.$": "$.arrive",
                                                "arrive_at.$": "$.arrive_at",
                                            },
                                        },
                                        "ResultSelector": {
                                            "result.$": "$.Payload"
                                        },
                                        "ResultPath": "$",
                                        "Retry": [
                                            {
                                                "ErrorEquals": [
                                                    "Lambda.ServiceException",
                                                    "Lambda.AWSLambdaException",  # noqa: E501
                                                    "Lambda.SdkClientException",  # noqa: E501
                                                ],
                                                "IntervalSeconds": 1,
                                                "MaxAttempts": 5,
                                                "BackoffRate": 2,
                                            }
                                        ],
                                        "End": True,
                                    }
                                },
                            },
                            {
                                "StartAt": "BookCar",
                                "States": {
                                    "BookCar": {
                                        "Type": "Task",
                                        "Resource": "arn:aws:states:::lambda:invoke",  # noqa: E501
                                        "Parameters": {
                                            "FunctionName": args[
                                                "book_car_lambda"
                                            ],
                                            "Payload": {
                                                "trip_id.$": "$.trip_id",
                                                "rental.$": "$.rental",
                                                "rental_from.$": "$.rental_from",  # noqa: E501
                                                "rental_to.$": "$.rental_to",
                                            },
                                        },
                                        "ResultSelector": {
                                            "result.$": "$.Payload"
                                        },
                                        "ResultPath": "$",
                                        "Retry": [
                                            {
                                                "ErrorEquals": [
                                                    "Lambda.ServiceException",
                                                    "Lambda.AWSLambdaException",  # noqa: E501
                                                    "Lambda.SdkClientException",  # noqa: E501
                                                ],
                                                "IntervalSeconds": 1,
                                                "MaxAttempts": 5,
                                                "BackoffRate": 2,
                                            }
                                        ],
                                        "End": True,
                                    }
                                },
                            },
                        ],
                        "ResultSelector": {
                            "book_hotel.$": "$[0].result",
                            "book_flight.$": "$[1].result",
                            "book_car.$": "$[2].result",
                        },
                        "ResultPath": "$.results.book_trip",
                        "Next": "TripBooked",
                        "Catch": [
                            {
                                "ErrorEquals": ["States.ALL"],
                                "ResultPath": "$.errors.book_trip",
                                "Next": "CancelTrip",
                            }
                        ],
                    },
                    "CancelTrip": {
                        "Type": "Parallel",
                        "Branches": [
                            {
                                "StartAt": "CancelHotel",
                                "States": {
                                    "CancelHotel": {
                                        "Type": "Task",
                                        "Resource": "arn:aws:states:::lambda:invoke",  # noqa: E501
                                        "Parameters": {
                                            "FunctionName": args[
                                                "cancel_hotel_lambda"
                                            ],
                                            "Payload": {
                                                "trip_id.$": "$.trip_id"
                                            },
                                        },
                                        "ResultSelector": {
                                            "result.$": "$.Payload"
                                        },
                                        "ResultPath": "$",
                                        "Retry": [
                                            {
                                                "ErrorEquals": ["States.ALL"],
                                                "IntervalSeconds": 1,
                                                "MaxAttempts": 100,
                                                "BackoffRate": 2,
                                            }
                                        ],
                                        "End": True,
                                    }
                                },
                            },
                            {
                                "StartAt": "CancelFlight",
                                "States": {
                                    "CancelFlight": {
                                        "Type": "Task",
                                        "Resource": "arn:aws:states:::lambda:invoke",  # noqa: E501
                                        "Parameters": {
                                            "FunctionName": args[
                                                "cancel_flight_lambda"
                                            ],
                                            "Payload": {
                                                "trip_id.$": "$.trip_id"
                                            },
                                        },
                                        "ResultSelector": {
                                            "result.$": "$.Payload"
                                        },
                                        "ResultPath": "$",
                                        "Retry": [
                                            {
                                                "ErrorEquals": ["States.ALL"],
                                                "IntervalSeconds": 1,
                                                "MaxAttempts": 100,
                                                "BackoffRate": 2,
                                            }
                                        ],
                                        "End": True,
                                    }
                                },
                            },
                            {
                                "StartAt": "CancelCar",
                                "States": {
                                    "CancelCar": {
                                        "Type": "Task",
                                        "Resource": "arn:aws:states:::lambda:invoke",  # noqa: E501
                                        "Parameters": {
                                            "FunctionName": args[
                                                "cancel_car_lambda"
                                            ],
                                            "Payload": {
                                                "trip_id.$": "$.trip_id"
                                            },
                                        },
                                        "ResultSelector": {
                                            "result.$": "$.Payload"
                                        },
                                        "ResultPath": "$",
                                        "Retry": [
                                            {
                                                "ErrorEquals": ["States.ALL"],
                                                "IntervalSeconds": 1,
                                                "MaxAttempts": 100,
                                                "BackoffRate": 2,
                                            }
                                        ],
                                        "End": True,
                                    }
                                },
                            },
                        ],
                        "ResultSelector": {
                            "cancel_hotel.$": "$[0].result",
                            "cancel_flight.$": "$[1].result",
                            "cancel_car.$": "$[2].result",
                        },
                        "ResultPath": "$.results.cancel_trip",
                        "Next": "TripCancelled",
                        "Catch": [
                            {
                                "ErrorEquals": ["States.ALL"],
                                "ResultPath": "$.errors.cancel_trip",
                                "Next": "TripCancelFailed",
                            }
                        ],
                    },
                    "TripBooked": {"Type": "Succeed"},
                    "TripCancelled": {
                        "Type": "Fail",
                        "Error": "TripCancelledError",
                        "Cause": "Trip cancelled due to error",
                    },
                    "TripCancelFailed": {
                        "Type": "Fail",
                        "Error": "TripCancelFailedError",
                        "Cause": "Trip cancellation failed due to error",
                    },
                },
            }
        )
    ),
)

# Export stack outputs.
pulumi.export("state_machine", state_machine.id)
