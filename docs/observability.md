# Observability

Trace IDs, structured logging, and Prometheus metrics are implemented for the triage agent.

## Trace ID propagation

- **Input**: `ticket.created` can include a `trace_id` in the payload. If missing, the agent generates one.
- **Output**: `ticket.triaged` includes `trace_id` in the payload and in Kafka headers (`trace_id`).
- **Logs**: All agent logs include `trace_id` and `ticket_id` when processing a ticket.

Downstream agents should read `trace_id` from the payload or headers and propagate it.

## Structured logging

- **Format**: Set `LOG_FORMAT=json` (default in k8s) for JSON logs, or `LOG_FORMAT=console` for dev.
- **Fields**: Each log line includes `timestamp`, `level`, `trace_id`, `ticket_id` (when bound), `event`, etc.
- **Example** (JSON): `{"event": "Produced ticket.triaged", "trace_id": "abc123", "ticket_id": "T-1", "type": "billing", "priority": "high", "timestamp": "..."}`

## Prometheus metrics

The agent exposes `/metrics` on port **9090**.

| Metric | Type | Description |
|--------|------|-------------|
| `triage_tickets_processed_total` | Counter | Tickets successfully triaged (labels: `type`, `priority`) |
| `triage_tickets_failed_total` | Counter | Failed tickets (labels: `reason`: `invalid_json`, `missing_ids`, `llm_error`, `consumer_error`) |
| `triage_processing_seconds` | Histogram | End-to-end processing time per ticket |
| `triage_llm_latency_seconds` | Histogram | LLM classification latency |
| `triage_tickets_enriched_total` | Counter | Tickets enriched with DynamoDB customer data |

**Scraping**: The deployment has annotations `prometheus.io/scrape`, `prometheus.io/port`, `prometheus.io/path` for annotation-based discovery. Add Prometheus (e.g. kube-prometheus-stack) to scrape pods with these annotations.

**Grafana**: Example queries:
- `rate(triage_tickets_processed_total[5m])` – throughput
- `histogram_quantile(0.95, rate(triage_processing_seconds_bucket[5m]))` – p95 latency
- `rate(triage_tickets_failed_total[5m])` – error rate

## Deploying Prometheus stack

The infra Terraform deploys **kube-prometheus-stack** (Prometheus + Grafana + Alertmanager) when you apply:

```bash
cd support-resolution-system/infra
terraform init && terraform apply
```

This creates the `monitoring` namespace and installs the stack via Helm. Prometheus is configured to scrape pods with `prometheus.io/scrape`, `prometheus.io/port`, `prometheus.io/path` annotations (including the triage agent).

**Access Grafana** (port-forward):
```bash
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Default login: admin / prom-operator (or check the Helm release notes for the chart version)
```

**Access Prometheus**:
```bash
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090, query e.g. triage_tickets_processed_total
```

**If `triage_tickets_processed_total` returns empty**:
1. Check **Status → Targets** in Prometheus: find job `pod-monitor/triage-agent/0` or `pod-annotations`. Targets should be "UP".
2. Verify the triage agent is running: `kubectl get pods -n support-agents -l app=triage-agent`
3. Test the metrics endpoint from inside the cluster: `kubectl exec -n support-agents deploy/triage-agent -- wget -qO- http://localhost:9090/metrics | head -20`
4. If needed, run the e2e script to process a ticket so the counter increments: `./scripts/e2e-triage.sh`

## Next steps

- Add OpenTelemetry for full distributed tracing (Jaeger/Tempo)
