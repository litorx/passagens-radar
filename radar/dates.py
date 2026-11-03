"""Gera a grade de (destino, ida, duracao) e escolhe a fatia da rodada (cursor rotativo)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

SALE_HORIZON_DAYS = 345  # medido em 02/11/2026: ha preco ate ~330 dias, nenhum voo a partir de ~347


def _d(s) -> date:
    return s if isinstance(s, date) else datetime.strptime(s, "%Y-%m-%d").date()


def build_combos(cfg: dict, today: date, horizon: dict | None = None):
    """Grade (destino, ida, duracao). O horizonte de vendas (~345 dias, medido) so cresce quando
    alguma data alem dele passa a ter preco (calendario abriu); nunca encolhe por amostragem parcial."""
    horizon = horizon or {}
    lim = SALE_HORIZON_DAYS
    for h in horizon.values():
        lim = max(lim, (_d(h) - today).days + 14)
    end = min(_d(cfg["ate"]), today + timedelta(days=lim))
    start = today + timedelta(days=int(cfg["antecedencia_min_dias"]))
    step = max(1, int(cfg["passo_dias"]))
    combos = []
    for dest in cfg["destinos"]:
        d = start
        while d <= end:
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


def build_escala(cfg: dict, today: date):
    """(hub, alem, ida) para a busca de escala oculta. Datas mais espacadas (2x o passo)."""
    e = cfg.get("escala_oculta", {})
    if not e.get("ativo"):
        return []
    end = min(_d(cfg["ate"]), today + timedelta(days=SALE_HORIZON_DAYS))
    step = max(1, int(cfg["passo_dias"])) * 2
    out = []
    for hub, alems in e.get("rotas", {}).items():
        for alem in alems:
            d = today + timedelta(days=int(cfg["antecedencia_min_dias"]))
            while d <= end:
                out.append((hub, alem, d))
                d += timedelta(days=step)
    return out
