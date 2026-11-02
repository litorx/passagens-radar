"""Estado persistente: historico de precos, cursor de varredura, avisos ja enviados."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIST_KEEP_DAYS = 120
MAX_PER_BUCKET = 400


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def add_obs(state: dict, bucket: str, price: int, **extra) -> None:
    obs = state.setdefault("obs", {}).setdefault(bucket, [])
    obs.append({"t": utcnow().isoformat(timespec="minutes"), "p": int(price), **extra})
    del obs[:-MAX_PER_BUCKET]


def sample(state: dict, bucket: str, days: int = 90) -> list[int]:
    cut = (utcnow() - timedelta(days=days)).isoformat()
    return [o["p"] for o in state.get("obs", {}).get(bucket, []) if o["t"] >= cut]


def prune(state: dict) -> None:
    cut = (utcnow() - timedelta(days=HIST_KEEP_DAYS)).isoformat()
    obs = state.get("obs", {})
    for b in list(obs):
        obs[b] = [o for o in obs[b] if o["t"] >= cut]
        if not obs[b]:
            del obs[b]


def should_alert(state: dict, key: str, price: int, drop: float = 0.05) -> bool:
    """Evita repetir o mesmo aviso: so reenvia se caiu mais 5%."""
    last = state.setdefault("alertados", {}).get(key)
    if last is None or price <= last * (1 - drop):
        state["alertados"][key] = int(price)
        return True
    return False


def remember_alert(state: dict, text: str, keep: int = 30) -> None:
    rec = state.setdefault("recentes", [])
    rec.append({"t": utcnow().isoformat(timespec="minutes"), "txt": text})
    del rec[:-keep]
