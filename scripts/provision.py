#!/usr/bin/env python3
"""
Provision the entire Support Resolution System.

Runs in order:
  1. (Optional) Kafka platform – terraform-aws-confluent-platform (terraform + manifests + DNS)
  2. Infra – Terraform (DynamoDB, Prometheus, Pod Identity)
  3. Kafka topics – Create ticket.events, ticket.triaged.*, ticket.resolved
  4. Build & push – Docker images for triage, billing, technical, feature
  5. Deploy – Namespace, ConfigMaps, Ollama, secrets, agent deployments

Prerequisites: terraform, aws CLI, kubectl, docker on PATH. AWS credentials configured.

Usage:
  python scripts/provision.py [--cluster-name X] [--kafka-platform-path ../terraform-aws-confluent-platform]
  python scripts/provision.py --kafka-platform-path ../terraform-aws-confluent-platform --auto-approve
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path | None = None, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    kw = {"cwd": cwd or repo_root(), "check": check}
    if capture:
        kw["capture_output"] = True
        kw["text"] = True
    return subprocess.run(cmd, **kw)


def step(msg: str) -> None:
    print(f"\n{'='*60}\n>>> {msg}\n{'='*60}")


AGENTS = ("triage", "billing", "technical", "feature")
KAFKA_TOPICS = [
    "ticket.events",
    "ticket.triaged.billing",
    "ticket.triaged.technical",
    "ticket.triaged.feature_request",
    "ticket.triaged.account",
    "ticket.triaged.other",
    "ticket.triaged.human",  # Fallback: unknown types, low-confidence
    "ticket.resolved",
]


def provision_kafka_platform(path: Path, auto_approve: bool) -> tuple[str, str]:
    """Run terraform-aws-confluent-platform provision; return (cluster_name, region)."""
    provision_script = path / "scripts" / "provision.py"
    if not provision_script.exists():
        raise SystemExit(f"Kafka platform provision script not found: {provision_script}")
    cmd = [sys.executable, str(provision_script), "--auto-approve"] if auto_approve else [sys.executable, str(provision_script)]
    run(cmd, cwd=path)

    result = run(
        ["terraform", "output", "-raw", "cluster_name"],
        cwd=path / "envs" / "dev",
        capture=True,
    )
    cluster_name = result.stdout.strip()
    result = run(
        ["terraform", "output", "-raw", "region"],
        cwd=path / "envs" / "dev",
        capture=True,
    )
    region = result.stdout.strip()
    return cluster_name, region


def update_kubeconfig(cluster_name: str, region: str) -> None:
    step("Updating kubeconfig")
    run(["aws", "eks", "update-kubeconfig", "--name", cluster_name, "--region", region])


def provision_infra(cluster_name: str, region: str, kafka_dns_domain: str, auto_approve: bool) -> None:
    step("Support Resolution System infra (Terraform)")
    infra_dir = repo_root() / "infra"
    tfvars = infra_dir / "terraform.tfvars"
    if not tfvars.exists():
        tfvars.write_text(
            f'region = "{region}"\n'
            f'cluster_name = "{cluster_name}"\n'
            f'kafka_dns_domain = "{kafka_dns_domain}"\n'
        )
        print(f"  Created {tfvars}")
    run(["terraform", "init"], cwd=infra_dir)
    cmd = ["terraform", "apply", f"-var=cluster_name={cluster_name}", f"-var=region={region}"]
    if auto_approve:
        cmd.append("-auto-approve")
    run(cmd, cwd=infra_dir)


def _get_kafka_bootstrap_service(namespace: str = "confluent") -> str:
    """Get in-cluster Kafka bootstrap endpoint (does not require Route 53)."""
    result = subprocess.run(
        ["kubectl", "get", "svc", "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    for item in data.get("items", []):
        name = item.get("metadata", {}).get("name", "")
        # Kafka bootstrap only (exclude controlcenter, schemaregistry, etc.)
        if "kafka" in name.lower() and "bootstrap" in name.lower():
            return f"{name}.{namespace}.svc.cluster.local:9092"
    return "kafka.confluent.local:9092"


def _get_dynamodb_table_from_infra() -> str | None:
    """Get dynamodb_table_name from infra Terraform output."""
    proc = run(
        ["terraform", "output", "-raw", "dynamodb_table_name"],
        cwd=repo_root() / "infra",
        check=False,
        capture=True,
    )
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout.strip()
    return None


def create_kafka_topics(bootstrap: str | None = None, namespace: str = "confluent") -> None:
    step("Creating Kafka topics")
    if bootstrap is None:
        bootstrap = _get_kafka_bootstrap_service(namespace)
    print(f"  Using bootstrap: {bootstrap}")
    image = "confluentinc/cp-kafka:7.9.0"
    topics_arg = " ".join(KAFKA_TOPICS)
    script = (
        f"for t in {topics_arg}; do "
        f"kafka-topics --bootstrap-server {bootstrap} --create --topic $t --partitions 6 --replication-factor 3 2>/dev/null || true; "
        "done; "
        f"kafka-topics --bootstrap-server {bootstrap} --list"
    )
    cmd = [
        "kubectl", "run", "kafka-client", "--rm", "-i", "--restart=Never",
        "--image", image,
        "-n", namespace,
        "--", "bash", "-c", script,
    ]
    run(cmd, cwd=repo_root())


def get_ecr_registry(region: str) -> str:
    result = run(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"], capture=True)
    account = result.stdout.strip()
    return f"{account}.dkr.ecr.{region}.amazonaws.com"


def ensure_ecr_login(registry: str, region: str) -> None:
    proc = subprocess.run(
        ["aws", "ecr", "get-login-password", "--region", region],
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["docker", "login", "--username", "AWS", "--password-stdin", registry],
        input=proc.stdout,
        capture_output=True,
        text=True,
        check=True,
    )


def build_and_push_agent(agent: str, registry: str, region: str) -> None:
    step(f"Build and push {agent} agent")
    repo_name = f"{agent}-agent"
    run(["aws", "ecr", "create-repository", "--repository-name", repo_name, "--region", region], check=False)
    dockerfile = repo_root() / "agents" / agent / "Dockerfile"
    if not dockerfile.exists():
        raise SystemExit(f"Dockerfile not found: {dockerfile}")
    run(["docker", "build", "-f", str(dockerfile), "-t", f"{repo_name}:latest", "."], cwd=repo_root())
    ecr_uri = f"{registry}/{repo_name}:latest"
    run(["docker", "tag", f"{repo_name}:latest", ecr_uri])
    run(["docker", "push", ecr_uri])


def update_deployment_image(agent: str, ecr_uri: str) -> None:
    deployment_path = repo_root() / "agents" / agent / "k8s" / "deployment.yaml"
    text = deployment_path.read_text()
    text = re.sub(r'image:\s*"[^"]*"', f'image: "{ecr_uri}"', text, count=1)
    deployment_path.write_text(text)


def deploy_agent_resources(agent: str, mock_llm: bool) -> None:
    k8s_dir = repo_root() / "agents" / agent / "k8s"
    configmap = k8s_dir / "configmap.yaml"
    if configmap.exists():
        run(["kubectl", "apply", "-f", str(configmap)])
        if mock_llm:
            run([
                "kubectl", "patch", "configmap", f"{agent}-agent-config",
                "-n", "support-agents",
                "-p", '{"data":{"MOCK_LLM":"true"}}',
                "--type=merge",
            ])

    proc = subprocess.run(
        [
            "kubectl", "create", "secret", "generic", f"{agent}-agent-keys",
            "-n", "support-agents",
            "--from-literal=ANTHROPIC_API_KEY=not-used",
            "--dry-run=client", "-o", "yaml",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=proc.stdout,
        capture_output=True,
        text=True,
        check=True,
    )

    deployment = k8s_dir / "deployment.yaml"
    if deployment.exists():
        run(["kubectl", "apply", "-f", str(deployment)])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Provision Support Resolution System (infra, topics, agents)",
        epilog="Prerequisites: terraform, aws CLI, kubectl, docker. AWS credentials configured.",
    )
    parser.add_argument("--cluster-name", help="EKS cluster name (required if not using --kafka-platform-path)")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument(
        "--kafka-platform-path",
        type=Path,
        help="Path to terraform-aws-confluent-platform repo; provisions Kafka first",
    )
    parser.add_argument("--kafka-dns-domain", default="confluent.local", help="Kafka DNS domain")
    parser.add_argument(
        "--agents",
        default="all",
        help="Comma-separated agents to build/deploy (triage,billing,technical,feature) or 'all'",
    )
    parser.add_argument("--mock-llm", action="store_true", help="Set MOCK_LLM=true in agent configmaps")
    parser.add_argument("--auto-approve", action="store_true", help="Skip Terraform apply confirmation")
    parser.add_argument("--skip-kafka-platform", action="store_true", help="Skip Kafka platform (even if path set)")
    parser.add_argument("--skip-infra", action="store_true", help="Skip infra Terraform")
    parser.add_argument("--skip-topics", action="store_true", help="Skip Kafka topic creation")
    parser.add_argument("--skip-build", action="store_true", help="Skip Docker build/push")
    parser.add_argument("--skip-deploy", action="store_true", help="Skip kubectl deploy")
    parser.add_argument("--seed-dynamodb", action="store_true", help="Seed DynamoDB with test customers (after infra)")
    args = parser.parse_args()

    try:
        cluster_name = args.cluster_name
        region = args.region

        if args.kafka_platform_path and not args.skip_kafka_platform:
            step("Kafka platform (terraform-aws-confluent-platform)")
            cluster_name, region = provision_kafka_platform(args.kafka_platform_path, args.auto_approve)
            update_kubeconfig(cluster_name, region)
        elif cluster_name:
            update_kubeconfig(cluster_name, region)
        else:
            raise SystemExit("Provide --cluster-name or --kafka-platform-path")

        if not args.skip_infra:
            provision_infra(cluster_name, region, args.kafka_dns_domain, args.auto_approve)

        if not args.skip_topics:
            create_kafka_topics()

        if args.seed_dynamodb:
            step("Seeding DynamoDB test data")
            table = _get_dynamodb_table_from_infra()
            if table:
                run([sys.executable, str(repo_root() / "scripts" / "seed-dynamodb.py"), "--table", table, "--region", region])
            else:
                print("  Skipped: could not get dynamodb_table_name from infra")

        agents_to_build = [a.strip() for a in args.agents.split(",") if a.strip()] if args.agents != "all" else list(AGENTS)
        agents_to_build = [a for a in agents_to_build if a in AGENTS]

        if not args.skip_build and agents_to_build:
            registry = get_ecr_registry(region)
            ensure_ecr_login(registry, region)
            for agent in agents_to_build:
                build_and_push_agent(agent, registry, region)
                update_deployment_image(agent, f"{registry}/{agent}-agent:latest")

        if not args.skip_deploy:
            step("Deploy namespace and triage base")
            run(["kubectl", "apply", "-f", str(repo_root() / "agents" / "triage" / "k8s" / "namespace.yaml")])
            run(["kubectl", "apply", "-f", str(repo_root() / "agents" / "triage" / "k8s" / "serviceaccount.yaml")])
            run(["kubectl", "apply", "-f", str(repo_root() / "agents" / "triage" / "k8s" / "ollama.yaml")])
            deploy_agent_resources("triage", args.mock_llm)

            for agent in agents_to_build:
                if agent != "triage":
                    deploy_agent_resources(agent, args.mock_llm)

        step("Provisioning complete")
        print(f"  Cluster: {cluster_name} | Region: {region}")
        print("  Kafka bootstrap: kafka.confluent.local:9092")
        print("  kubectl get pods -n support-agents")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\nError: command failed with code {e.returncode}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        return e.returncode
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
