Saga Pattern Demo
=================

Implementation of a classic Saga pattern example of booking a trip using Lambda
functions as tasks and Step Functions as an orchestrator.

Booking a trip consists of booking a hotel, a flight and a car. These operations
are considered independent and thus performed in parallel. Each operation has
a compensating operation which rollbacks the action. All operations in this demo
are idempotent so both forward and backward recovery can be used. However, this
demo implements only the backward recovery. In theory, the compensating
operations should be retried until they succeed. For the purpose of the demo we
limit the retries to a high but finite number.

To simulate various failure scenarios, it's possible to configure failure rate
for individual operations via Pulumi stack configuration (see below).

Execution Examples
------------------

Trip successfully booked:

.. image:: docs/succeeded.svg
   :alt: Trip booked

Booking failed and the trip was cancelled:

.. image:: docs/cancelled.svg
   :alt: Trip cancelled

Trip cancellation failed:

.. image:: docs/cancel-failed.svg
   :alt: Trip cancellation failed

Deployment
==========

Create and configure a new stack::

   pulumi -C infra stack init \
     --stack sfn-demo-saga-dev \
     --secrets-provider="awskms://alias/pulumi?region=eu-central-1"
   pulumi -C infra config set aws:region eu-central-1
   pulumi -C infra config set book_hotel_fail_rate 0.1
   pulumi -C infra config set book_flight_fail_rate 0.1
   pulumi -C infra config set book_car_fail_rate 0.1
   pulumi -C infra config set cancel_hotel_fail_rate 0.1
   pulumi -C infra config set cancel_flight_fail_rate 0.1
   pulumi -C infra config set cancel_car_fail_rate 0.1

Create or update resources in the stack::

   pulumi -C infra up

Start state machine execution::

   aws stepfunctions start-execution \
     --state-machine-arn $(pulumi -C infra stack output state_machine) \
     --input "$(cat sample-input.json | jq --arg trip_id $(uuidgen) '.trip_id = $trip_id')"

Destroy the stack and its resources::

   pulumi -C infra destroy

Remove the stack and its configuration::

   pulumi -C infra stack rm

References and Inspiration
==========================

- https://dl.acm.org/doi/abs/10.1145/38713.38742
- https://github.com/theburningmonk/lambda-saga-pattern
- https://yos.io/2017/10/30/distributed-sagas
