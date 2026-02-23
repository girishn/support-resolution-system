#!/usr/bin/env bash
# Create the ticket.events Kafka topic (Option A) and list topics.
# Requires: kubectl context set to the EKS cluster where Confluent Kafka runs,
#           and DNS so kafka.confluent.local resolves (see docs/create-kafka-topics.md).
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka.confluent.local:9092}"
NAMESPACE="${KAFKA_NAMESPACE:-confluent}"
IMAGE="${KAFKA_CLIENT_IMAGE:-confluentinc/cp-kafka:7.9.0}"

echo "Creating topic ticket.events (bootstrap=$BOOTSTRAP, namespace=$NAMESPACE)..."
kubectl run kafka-client --rm -i --restart=Never \
  --image="$IMAGE" \
  -n "$NAMESPACE" \
  -- bash -c "
    kafka-topics --bootstrap-server $BOOTSTRAP --create --topic ticket.events --partitions 6 --replication-factor 3 || true
    echo '---'
    kafka-topics --bootstrap-server $BOOTSTRAP --list
  "
