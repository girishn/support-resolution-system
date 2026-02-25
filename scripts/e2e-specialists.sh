#!/usr/bin/env bash
# E2E test for full flow: ticket.created -> triage -> specialist -> ticket.resolved
# With MOCK_LLM, triage always returns "billing", so we test via billing agent.
# Requires: kubectl context set to EKS; topics created; triage + billing agents running with MOCK_LLM=true.
set -e

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka.confluent.local:9092}"
NAMESPACE="${KAFKA_NAMESPACE:-confluent}"
IMAGE="${KAFKA_CLIENT_IMAGE:-confluentinc/cp-kafka:7.9.0}"
TICKET_ID="e2e-spec-$(date +%s)"
CREATED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TRACE_ID="e2e-trace-$(date +%s)"

PAYLOAD=$(cat <<EOF
{"event_type":"ticket.created","ticket_id":"$TICKET_ID","customer_id":"e2e-cust","trace_id":"$TRACE_ID","subject":"Billing question","body":"Why was I charged twice? Please help.","created_at":"$CREATED_AT","channel":"portal"}
EOF
)

echo "E2E Specialists (full flow): ticket_id=$TICKET_ID"
echo "Flow: ticket.created -> triage -> ticket.triaged.billing -> billing agent -> ticket.resolved"

echo "Producing ticket.created..."
kubectl run e2e-spec-producer --rm -i --restart=Never \
  --image="$IMAGE" \
  -n "$NAMESPACE" \
  -- bash -c "
    echo '$PAYLOAD' | kafka-console-producer --bootstrap-server $BOOTSTRAP --topic ticket.events
    echo 'Produced.'
  "

echo "Waiting 45s for triage + billing agents to process..."
sleep 45

echo "Consuming from ticket.resolved (from beginning, 90s idle timeout)..."
OUTPUT=$(kubectl run e2e-spec-consumer --rm -i --restart=Never \
  --image="$IMAGE" \
  -n "$NAMESPACE" \
  -- kafka-console-consumer --bootstrap-server $BOOTSTRAP --topic ticket.resolved --from-beginning --timeout-ms 90000 2>&1 || true)

if echo "$OUTPUT" | grep '"event_type":"ticket.resolved"' | grep -q "\"ticket_id\":\"$TICKET_ID\""; then
  echo "PASS: Found ticket.resolved for ticket_id=$TICKET_ID"
  echo "$OUTPUT" | grep '"event_type":"ticket.resolved"' | grep "$TICKET_ID" | head -1
  # Sanity check: resolved_by should be billing
  if echo "$OUTPUT" | grep "$TICKET_ID" | grep -q '"resolved_by":"billing"'; then
    echo "PASS: resolved_by=billing confirmed"
  fi
  exit 0
else
  echo "FAIL: No ticket.resolved for ticket_id=$TICKET_ID in consumer output."
  echo "Consumer output (last 30 lines):"
  echo "$OUTPUT" | tail -30
  echo ""
  echo "Debug: kubectl logs -n support-agents -l app=triage-agent --tail=100"
  echo "       kubectl logs -n support-agents -l app=billing-agent --tail=100"
  echo "Note: Ensure triage and billing agents have MOCK_LLM=true for deterministic e2e"
  exit 1
fi
