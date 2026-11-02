"""Detector de 'fora da curva' robusto (mediana + MAD), sem dependencias."""
from __future__ import annotations

import statistics
from dataclasses import dataclass


@dataclass
class Verdict:
    is_outlier: bool
    median: float = 0.0
    drop_pct: float = 0.0
    z: float = 0.0
    n: int = 0
    reason: str = ""


def judge(price: float, sample: list[float], sens_pct: float = 25.0,
          min_n: int = 6, z_min: float = 2.0) -> Verdict:
    """True quando `price` esta pelo menos `sens_pct`% abaixo da mediana E e um desvio
    estatistico forte (z robusto >= z_min). Com poucas amostras (< min_n) nao avisa."""
    vals = [float(v) for v in sample if v and v > 0]
    n = len(vals)
    if n < min_n:
        return Verdict(False, n=n, reason=f"amostra pequena ({n}<{min_n})")
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    drop = (med - price) / med * 100 if med else 0.0
    z = (med - price) / (1.4826 * mad) if mad > 0 else (99.0 if price < med else 0.0)
    ok = drop >= sens_pct and z >= z_min
    why = f"{drop:.0f}% abaixo do normal (mediana {med:.0f})" if ok else ""
    return Verdict(ok, med, drop, z, n, why)
