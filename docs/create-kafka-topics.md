# Exact steps to create Kafka topics

Kafka runs in the **terraform-aws-confluent-platform** EKS cluster (namespace `confluent`), with bootstrap **`kafka.confluent.local:9092`** after the DNS script. The Support Resolution System expects at least **`ticket.events`** (see [events/README.md](../events/README.md)).

---

## Prerequisites

- **kubectl** context set to the EKS cluster where Confluent Kafka runs (the cluster from terraform-aws-confluent-platform, e.g. `confluent-dev-eks`).
- **DNS**: The Kafka platform's DNS script has been run so `kafka.confluent.local` (and broker hostnames) resolve inside the VPC. If not, run from the Kafka platform repo:
  ```bash
  ZONE_ID=$(terraform -chdir=envs/dev output -raw kafka_dns_zone_id)
  ZONE_ID=$ZONE_ID ./scripts/create-kafka-dns.sh
  ```

---

## Step 1: Run a Kafka CLI pod in the same cluster

Use a pod that can reach `kafka.confluent.local:9092` and has `kafka-topics`. From the **terraform-aws-confluent-platform** repo (or any machine with kubectl pointed at that cluster):

```bash
kubectl run kafka-client --rm -it --restart=Never \
  --image=confluentinc/cp-kafka:7.9.0 \
  -n confluent \
  -- bash
```

- Use the **confluent** namespace so the pod uses the same network/DNS as Kafka.
- If your Kafka is in another namespace, change `-n confluent` to that namespace.

---

## Step 2: Create the topic(s) inside the pod

At the shell inside the pod:

**Option A – Single topic `ticket.events` (matches events/README.md)**

```bash
kafka-topics --bootstrap-server kafka.confluent.local:9092 \
  --create \
  --topic ticket.events \
  --partitions 6 \
  --replication-factor 3
```

- **`--replication-factor 3`** matches 3 Kafka brokers in the platform's `manifests/base/kafka.yaml`.
- **`--partitions 6`** gives parallelism for consumers; adjust if you prefer fewer or more.

**Option B – Separate topics per event type**

```bash
kafka-topics --bootstrap-server kafka.confluent.local:9092 --create --topic ticket.created  --partitions 6 --replication-factor 3
kafka-topics --bootstrap-server kafka.confluent.local:9092 --create --topic ticket.triaged  --partitions 6 --replication-factor 3
```

If you use Option B, your producers/consumers and event docs must use these topic names instead of a single `ticket.events` topic with an `event_type` field.

---

## Step 3: Verify

Inside the same pod:

```bash
kafka-topics --bootstrap-server kafka.confluent.local:9092 --list
```

You should see `ticket.events` (or `ticket.created` and `ticket.triaged`). Optional:

```bash
kafka-topics --bootstrap-server kafka.confluent.local:9092 --describe --topic ticket.events
```

---

## Step 4: Exit the pod

Type `exit`. With `--rm`, the pod is removed.

---

## Summary

| Step | Action |
|------|--------|
| 1 | Run `kubectl run kafka-client ...` in namespace `confluent` with image `confluentinc/cp-kafka:7.9.0` and get a shell. |
| 2 | Run `kafka-topics --bootstrap-server kafka.confluent.local:9092 --create --topic ticket.events --partitions 6 --replication-factor 3` (or create separate topics). |
| 3 | Run `kafka-topics ... --list` to verify. |
| 4 | Exit the pod. |

---

## Automated script (Option A only)

From this repo you can run [../scripts/create-kafka-topics.sh](../scripts/create-kafka-topics.sh) to create `ticket.events` and list topics in one shot (no interactive shell). Requires `kubectl` and cluster access as above.

---

## Alternative: KafkaTopic CR (optional, more setup)

Confluent for Kubernetes supports a **KafkaTopic** custom resource, but it requires a **Kafka Admin REST Class** (Kafka REST / Admin API) to be configured. The current platform only has Zookeeper + Kafka (cp-server); there is no Kafka REST. To use KafkaTopic CRs you would need to:

1. Deploy and configure Kafka REST (or Confluent Admin REST) and a KafkaRestClass in the Kafka platform.
2. Then add KafkaTopic manifests and apply them with `kubectl apply -f ...`.

For a one-off or small set of topics, the CLI approach above is the simplest and does not require any platform changes.
