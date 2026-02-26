"""
Integration: Agent + Kafka

Does the agent actually consume and produce real Kafka messages?
Runs producer and consumer inside the cluster (via kubectl run) so Kafka is reachable.
Requires: kubectl context set to EKS cluster; triage agent running in support-agents.
"""
import base64
import json
import os
import subprocess
import time

import pytest

pytestmark = pytest.mark.integration


def _get_kafka_bootstrap_in_cluster(namespace: str = "confluent") -> str | None:
    """Get in-cluster Kafka bootstrap from K8s services."""
    try:
        proc = subprocess.run(
            ["kubectl", "get", "svc", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        for item in data.get("items", []):
            name = item.get("metadata", {}).get("name", "")
            if "kafka" in name.lower() and "bootstrap" in name.lower():
                return f"{name}.{namespace}.svc.cluster.local:9092"
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        pass
    return None


def _cluster_ready() -> bool:
    """kubectl reachable and Kafka bootstrap service exists."""
    try:
        subprocess.run(["kubectl", "cluster-info"], capture_output=True, check=True)
        return _get_kafka_bootstrap_in_cluster() is not None
    except subprocess.CalledProcessError:
        return False


@pytest.mark.skipif(not _cluster_ready(), reason="kubectl not configured or Kafka not in cluster")
def test_agent_consumes_and_produces_kafka_messages():
    """Agent consumes ticket.created and produces ticket.triaged. Producer/consumer run in-cluster."""
    bootstrap = _get_kafka_bootstrap_in_cluster()
    namespace = os.environ.get("KAFKA_NAMESPACE", "confluent")
    image = os.environ.get("KAFKA_CLIENT_IMAGE", "confluentinc/cp-kafka:7.9.0")
    ticket_id = f"int-{int(time.time())}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    trace_id = f"int-trace-{int(time.time())}"

    payload = {
        "event_type": "ticket.created",
        "ticket_id": ticket_id,
        "customer_id": "int-cust",
        "trace_id": trace_id,
        "subject": "Billing question",
        "body": "Why was I charged twice?",
        "created_at": created_at,
        "channel": "portal",
    }
    payload_b64 = base64.b64encode(json.dumps(payload).encode()).decode()

    subprocess.run(
        [
            "kubectl", "run", "int-producer", "--rm", "-i", "--restart=Never",
            "--image", image,
            "-n", namespace,
            "--", "bash", "-c",
            f"echo '{payload_b64}' | base64 -d | kafka-console-producer --bootstrap-server {bootstrap} --topic ticket.events",
        ],
        check=True,
        capture_output=True,
    )

    time.sleep(35)

    proc = subprocess.run(
        [
            "kubectl", "run", "int-consumer", "--rm", "-i", "--restart=Never",
            "--image", image,
            "-n", namespace,
            "--", "kafka-console-consumer",
            "--bootstrap-server", bootstrap,
            "--topic", "ticket.triaged.billing",
            "--from-beginning",
            "--timeout-ms", "60000",
        ],
        capture_output=True,
        text=True,
    )

    output = (proc.stdout or "") + (proc.stderr or "")
    found = None
    for line in output.splitlines():
        if ticket_id in line and "ticket.triaged" in line:
            try:
                found = json.loads(line.strip())
                break
            except json.JSONDecodeError:
                continue

    assert found is not None, f"No ticket.triaged for ticket_id={ticket_id}. Output: {output[-500:]}"
    assert found.get("event_type") == "ticket.triaged"
    assert found.get("type") == "billing"
    assert "priority" in found
    assert "reasoning" in found
