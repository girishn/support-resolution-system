# Shared libraries

Reusable code for support-resolution-system agents. Prefer shared modules over copying code across agents.

## Layout

- **shared/aws/** – AWS service integrations
  - **dynamodb.py** – `get_customer(customer_id, table_name)` – fetches customer by `customer_id` from a DynamoDB table. Used by the triage agent to enrich ticket payloads.

## Usage

Agents import from `shared` at runtime. The Dockerfile sets `PYTHONPATH=/app` and copies `shared/` into the image:

```python
from shared.aws.dynamodb import get_customer
```

## Adding new integrations

- Add new modules under `shared/aws/` (e.g. `s3.py`, `secrets.py`) or `shared/<domain>/`.
- Keep dependencies in each agent's `requirements.txt` (e.g. `boto3` in triage).
- Document new env vars in the agent README (e.g. `DYNAMODB_TABLE` for the customers table).
