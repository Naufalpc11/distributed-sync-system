from __future__ import annotations

import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env_file(env_path: str | Path | None = None) -> None:
    path = Path(env_path) if env_path is not None else PROJECT_ROOT / ".env"

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    @staticmethod
    def parse_peers(peers_raw: str | None) -> list[str]:
        if not peers_raw:
            return []

        return [peer.strip() for peer in peers_raw.split(",") if peer.strip()]

    @classmethod
    def from_env(cls) -> dict[str, Any]:
        bind_host = os.getenv("HOST", "localhost")
        advertise_host = os.getenv("ADVERTISE_HOST", bind_host)
        peers = cls.parse_peers(os.getenv("PEERS"))

        return {
            "node_id": os.getenv("NODE_ID", "node-1"),
            "bind_host": bind_host,
            "advertise_host": advertise_host,
            "port": int(os.getenv("PORT", "8000")),
            "peers": peers,
        }
