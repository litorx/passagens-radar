"""Configuracao (data/config.json). Tudo aqui pode ser mudado pelo celular via bot."""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOCAL = ROOT / "data_local"          # so no seu PC (milhas); ignorado pelo git
BRT = timezone(timedelta(hours=-3))  # Brasil nao tem horario de verao

DEFAULT = {
    "ativo": True,
    "origens": ["GRU", "CGH", "VCP"],
    "destinos": ["SCL", "EZE", "AEP", "MVD", "LIM", "ASU", "COR", "MDZ", "BOG", "MDE",
                 "CTG", "UIO", "CUZ", "LPB", "VVI", "PTY", "BRC", "USH", "FTE", "PUQ"],
    "ate": "2027-12-31",            # data final desejada (o radar ve ate onde as cias vendem)
    "antecedencia_min_dias": 7,
    "passo_dias": 3,                # testa 1 data a cada N dias
    "duracoes": [5, 7, 10],
    "intervalo_horas": 3,           # de quanto em quanto tempo o radar de dinheiro roda
    "pares_por_rodada": 60,
    "silencio": {"inicio": 23, "fim": 7},   # sem avisos entre 23h e 7h (horario de Brasilia); null = desliga
    "sensibilidade": 25,            # % abaixo do normal para avisar
    "limites": {},                  # ex.: {"SCL": 1100}  (aviso se <= valor, em R$)
    "milhas": {"ativo": True, "custo_milheiro": 16.0, "limites_milhas": {}, "sensibilidade": 25},
    "regiao": "america_do_sul",
    # Escala "oculta": passagem ate um destino MAIS LONGE com conexao no hub, mais barata que ir ao hub.
    # Zona cinza: viola o contrato da companhia (so ida, so bagagem de mao). Desligue com /escala off.
    "escala_oculta": {
        "ativo": True, "min_economia_pct": 20, "por_rodada": 6,
        "rotas": {"SCL": ["SYD", "AKL"], "LIM": ["CUZ", "MIA"], "BOG": ["CUN", "MEX", "MIA"],
                  "PTY": ["MIA", "MEX", "SJO", "CUN"], "EZE": ["MAD", "FCO", "MIA"],
                  "MVD": ["MAD"], "GRU": []},
    },
    "bot": {"chat_id": ""},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path | None = None) -> dict:
    path = path or DATA / "config.json"
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        user = {}
    return _merge(DEFAULT, user)


def save(cfg: dict, path: Path | None = None) -> None:
    path = path or DATA / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_env() -> None:
    """Carrega segredos locais (data_local/.env ou .env.local) para o PC; ignorados pelo git."""
    for f in (LOCAL / ".env", ROOT / ".env.local"):
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))
        except FileNotFoundError:
            pass


def now_brt() -> datetime:
    return datetime.now(BRT)


def in_quiet_hours(cfg: dict, now: datetime | None = None) -> bool:
    s = cfg.get("silencio")
    if not s:
        return False
    h = (now or now_brt()).hour
    a, b = int(s["inicio"]), int(s["fim"])
    return (a <= h or h < b) if a > b else (a <= h < b)


def chat_id(cfg: dict) -> str:
    return os.environ.get("TELEGRAM_CHAT_ID") or str(cfg.get("bot", {}).get("chat_id") or "")
