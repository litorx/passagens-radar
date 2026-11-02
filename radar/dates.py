"""Gera a grade de (destino, ida, duracao) e escolhe a fatia da rodada (cursor rotativo)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

SALE_HORIZON_DAYS = 360  # teto de seguranca; o horizonte real e descoberto por destino


def _d(s) -> date:
    return s if isinstance(s, date) else datetime.strptime(s, "%Y-%m-%d").date()


def build_combos(cfg: dict, today: date, horizon: dict | None = None):
    horizon = horizon or {}
    end = min(_d(cfg["ate"]), today + timedelta(days=SALE_HORIZON_DAYS))
    start = today + timedelta(days=int(cfg["antecedencia_min_dias"]))
    step = max(1, int(cfg["passo_dias"]))
    combos = []
    for dest in cfg["destinos"]:
        h = horizon.get(dest)
        # alem do horizonte conhecido so sonda 2 passos (para detectar abertura de datas novas)
        limit = min(end, _d(h) + timedelta(days=step * 2)) if h else end
        d = start
        while d <= limit:
            for n in cfg["duracoes"]:
                combos.append((dest, d, int(n)))
            d += timedelta(days=step)
    return combos


def pick(combos: list, cursor: int, n: int):
    """Fatia circular de n combos a partir do cursor. Devolve (fatia, novo_cursor)."""
    if not combos:
        return [], 0
    cursor %= len(combos)
    idx = [(cursor + i) % len(combos) for i in range(min(n, len(combos)))]
    return [combos[i] for i in idx], (cursor + len(idx)) % len(combos)
