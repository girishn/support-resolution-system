#!/usr/bin/env bash
# E2E test for the Triage Agent: produce one ticket.created, then verify ticket.triaged appears.
# Runs inside the cluster so Kafka (kafka.confluent.local) is reachable.
# Requires: kubectl context set to the EKS cluster; topic ticket.events exists; triage agent running.
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka.confluent.local:9092}"
NAMESPACE="${KAFKA_NAMESPACE:-confluent}"
IMAGE="${KAFKA_CLIENT_IMAGE:-confluentinc/cp-kafka:7.9.0}"
TICKET_ID="e2e-$(date +%s)"
CREATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

TRACE_ID="e2e-trace-$(date +%s)"
PAYLOAD=$(cat <<EOF
{"event_type":"ticket.created","ticket_id":"$TICKET_ID","customer_id":"e2e-cust","trace_id":"$TRACE_ID","subject":"Billing question","body":"Why was I charged twice? Please help.","created_at":"$CREATED_AT","channel":"portal"}
EOF
)

echo "E2E Triage: ticket_id=$TICKET_ID"

echo "Producing ticket.created..."
kubectl run e2e-triage-producer --rm -i --restart=Never \
  --image="$IMAGE" \
  -n "$NAMESPACE" \
  -- bash -c "
    echo '$PAYLOAD' | kafka-console-producer --bootstrap-server $BOOTSTRAP --topic ticket.events
    echo 'Produced.'
  "

echo "Waiting 30s for agent to produce ticket.triaged..."
sleep 30

# Consumer reads from beginning, then exits after 90s with no new message (enough time to catch up on busy topics).
echo "Consuming from ticket.events (from beginning, 90s idle timeout)..."
OUTPUT=$(kubectl run e2e-triage-consumer --rm -i --restart=Never \
  --image="$IMAGE" \
  -n "$NAMESPACE" \
  -- kafka-console-consumer --bootstrap-server $BOOTSTRAP --topic ticket.events --from-beginning --timeout-ms 90000 2>&1 || true)

if echo "$OUTPUT" | grep '"event_type":"ticket.triaged"' | grep -q "\"ticket_id\":\"$TICKET_ID\""; then
  echo "PASS: Found ticket.triaged for ticket_id=$TICKET_ID"
  echo "$OUTPUT" | grep '"event_type":"ticket.triaged"' | grep "$TICKET_ID" | head -1
  exit 0
else
  echo "FAIL: No ticket.triaged for ticket_id=$TICKET_ID in consumer output."
  echo "Consumer output (last 20 lines):"
  echo "$OUTPUT" | tail -20
  echo ""
  echo "Debug: kubectl logs -n support-agents -l app=triage-agent --tail=150"
  exit 1
fi
