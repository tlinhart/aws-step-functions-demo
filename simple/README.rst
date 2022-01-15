Simple Demo
===========

Simple AWS Step Functions demo using Lambda functions.

Deployment
==========

Create and configure a new stack::

   pulumi -C infra stack init \
     --stack sfn-demo-simple-dev \
     --secrets-provider="awskms://alias/pulumi?region=eu-central-1"
   pulumi -C infra config set aws:region eu-central-1

Create or update resources in the stack::

   pulumi -C infra up

Start state machine execution::

   aws stepfunctions start-execution \
     --state-machine-arn $(pulumi -C infra stack output state_machine) \
     --input '{"name": "John"}'

Destroy the stack and its resources::

   pulumi -C infra destroy

Remove the stack and its configuration::

   pulumi -C infra stack rm
