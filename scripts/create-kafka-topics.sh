#!/usr/bin/env bash
# Create Kafka topics for the support resolution system and list topics.
# Requires: kubectl context set to the EKS cluster where Confluent Kafka runs,
#           and DNS so kafka.confluent.local resolves (see docs/create-kafka-topics.md).
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka.confluent.local:9092}"
NAMESPACE="${KAFKA_NAMESPACE:-confluent}"
IMAGE="${KAFKA_CLIENT_IMAGE:-confluentinc/cp-kafka:7.9.0}"

TOPICS=(
  "ticket.events"
  "ticket.triaged.billing"
  "ticket.triaged.technical"
  "ticket.triaged.feature_request"
  "ticket.triaged.account"
  "ticket.triaged.other"
  "ticket.resolved"
)

echo "Creating topics (bootstrap=$BOOTSTRAP, namespace=$NAMESPACE)..."
for topic in "${TOPICS[@]}"; do
  echo "  - $topic"
done

kubectl run kafka-client --rm -i --restart=Never \
  --image="$IMAGE" \
  -n "$NAMESPACE" \
  -- bash -c "
    for t in ticket.events ticket.triaged.billing ticket.triaged.technical ticket.triaged.feature_request ticket.triaged.account ticket.triaged.other ticket.resolved; do
      kafka-topics --bootstrap-server $BOOTSTRAP --create --topic \$t --partitions 6 --replication-factor 3 2>/dev/null || true
    done
    echo '---'
    kafka-topics --bootstrap-server $BOOTSTRAP --list
  "
