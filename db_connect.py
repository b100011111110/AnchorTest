"""
db_connect.py
Loads credentials from .env → connections.json and verifies
connectivity to PostgreSQL, Neo4j, InfluxDB, and ChromaDB.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# ── resolve project root ──────────────────────────────────────────────────────
ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env.example"
CONN_FILE = ROOT / "connections.json"

# ── load environment variables ────────────────────────────────────────────────
load_dotenv(ENV_FILE)


def _resolve(value: str) -> str:
    """Replace ${VAR} placeholders with actual env values."""
    return re.sub(
        r"\$\{(\w+)\}",
        lambda m: os.environ.get(m.group(1), ""),
        value,
    )


def load_connections() -> dict:
    with open(CONN_FILE) as f:
        raw = json.load(f)
    return {
        db: {k: _resolve(v) for k, v in cfg.items()}
        for db, cfg in raw.items()
    }


# ── individual connectors ─────────────────────────────────────────────────────

def connect_postgresql(cfg: dict):
    import psycopg2
    conn = psycopg2.connect(
        dsn=cfg["url"],
        user=cfg["userid"],
        password=cfg["password"],
        connect_timeout=5,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
    conn.close()
    return version


def connect_neo4j(cfg: dict):
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(
        cfg["url"],
        auth=(cfg["userid"], cfg["password"]),
        connection_timeout=5,
    )
    with driver.session() as session:
        result = session.run("RETURN 'Neo4j connected' AS msg")
        msg = result.single()["msg"]
    driver.close()
    return msg


def connect_influxdb(cfg: dict):
    from influxdb_client import InfluxDBClient
    client = InfluxDBClient(
        url=cfg["url"],
        token=cfg["password"],   # password field holds the API token
        org=cfg["userid"],       # userid field holds the org name
        timeout=5_000,
    )
    health = client.health()
    client.close()
    return f"status={health.status}, version={health.version}"


def connect_chromadb(cfg: dict):
    import chromadb
    host, port = cfg["url"].replace("http://", "").split(":")
    client = chromadb.HttpClient(host=host, port=int(port))
    heartbeat = client.heartbeat()
    return f"heartbeat={heartbeat}"


# ── runner ────────────────────────────────────────────────────────────────────

CONNECTORS = {
    "postgresql": connect_postgresql,
    "neo4j":      connect_neo4j,
    "influxdb":   connect_influxdb,
    "chromadb":   connect_chromadb,
}

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def main():
    print(f"\n{BOLD}⚓  AnchorTest — Database Connection Check{RESET}\n")

    try:
        connections = load_connections()
    except FileNotFoundError as e:
        print(f"{RED}✗  Could not load config: {e}{RESET}")
        sys.exit(1)

    results = {}
    for name, fn in CONNECTORS.items():
        cfg = connections.get(name, {})
        # skip only if the URL itself is missing — auth fields may be intentionally empty
        if not cfg.get("url"):
            print(f"  {YELLOW}⚠  {name:<12}{RESET} skipped — no URL configured")
            results[name] = "skipped"
            continue

        try:
            info = fn(cfg)
            print(f"  {GREEN}✔  {name:<12}{RESET} {info}")
            results[name] = "ok"
        except Exception as exc:
            print(f"  {RED}✗  {name:<12}{RESET} {exc}")
            results[name] = "failed"

    print()
    ok      = sum(1 for s in results.values() if s == "ok")
    skipped = sum(1 for s in results.values() if s == "skipped")
    failed  = sum(1 for s in results.values() if s == "failed")
    print(f"{BOLD}Summary:{RESET}  "
          f"{GREEN}{ok} connected{RESET}  "
          f"{YELLOW}{skipped} skipped{RESET}  "
          f"{RED}{failed} failed{RESET}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
