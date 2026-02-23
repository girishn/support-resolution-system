# Event schemas

JSON Schema definitions for Kafka events used by the Support Resolution System.

## Topics and events

| Topic            | Event            | Producer        | Consumer(s)                    |
|------------------|------------------|-----------------|--------------------------------|
| `ticket.events`  | `ticket.created` | Portal / API    | Triage Agent                   |
| `ticket.events`  | `ticket.triaged` | Triage Agent    | Billing, Technical, Feature Guide agents |
| (later)          | `ticket.resolved`| Specialized agents | QA, Analytics               |
| (later)          | `ticket.escalated` | Any agent    | Escalation Agent               |

Events can be keyed by `ticket_id` for partitioning. On a single topic (`ticket.events`), each message **must** include an **`event_type`** field so consumers can route and validate correctly:

- `event_type: "ticket.created"` — payload matches `ticket.created` schema.
- `event_type: "ticket.triaged"` — payload matches `ticket.triaged` schema.

Example envelope: `{"event_type": "ticket.created", "ticket_id": "...", "customer_id": "...", "subject": "...", "body": "...", "created_at": "...", "channel": "portal"}`.

## Files

- `ticket.created.schema.json` – New ticket submitted by customer
- `ticket.triaged.schema.json` – Triage Agent output (type, priority, reasoning)

## Usage

Use these schemas to validate producer payloads, generate client types, or configure a schema registry (e.g. Confluent Schema Registry) if you adopt Avro/Protobuf later.
