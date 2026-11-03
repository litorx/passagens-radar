"""Kiwi.com via servidor MCP OFICIAL (https://mcp.kiwi.com): feito para agentes, sem chave, sem captcha.

Medido em 03/11/2026: inclui low-cost (Sky Airline, o mesmo voo que o Skyscanner mostra), aceita INTERVALO
de datas de ida e de volta, noites de estadia, ordena por preco, filtra conexoes/bagagem. ~3 s por busca,
ate 15 resultados mais baratos por busca.
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

import requests

URL = "https://mcp.kiwi.com"
HEAD = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def dmy(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _parse_sse(text: str) -> dict:
    last = None
    for line in text.splitlines():
        if line.startswith("data:"):
            try:
                last = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                pass
    if last is None:
        try:
            last = json.loads(text)
        except json.JSONDecodeError:
            raise RuntimeError("resposta invalida do Kiwi")
    return last


def search(retries: int = 3, **args) -> dict:
    """Chama search-flight. Retorna o dict {itineraries, resultsCount, ...}; levanta RuntimeError se falhar."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
               "params": {"name": "search-flight", "arguments": args}}
    last = "?"
    for i in range(retries):
        try:
            r = requests.post(URL, headers=HEAD, json=payload, timeout=120)
            if r.status_code == 200:
                res = _parse_sse(r.text).get("result", {})
                content = res.get("content") or []
                data = json.loads(content[0]["text"]) if content else res.get("structuredContent") or {}
                if data.get("error") and not data.get("itineraries"):
                    return {"itineraries": [], "resultsCount": 0, "error": data["error"]}
                return data
            last = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError, KeyError) as e:
            last = type(e).__name__
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"Kiwi falhou: {last}")


def rows(data: dict) -> list[dict]:
    """Itinerarios -> linhas simples, mais baratas primeiro."""
    out = []
    for it in data.get("itineraries") or []:
        o, i = it.get("outbound") or {}, it.get("inbound") or {}
        segs = (o.get("segments") or []) + (i.get("segments") or [])
        out.append({
            "total": float(it["price"]),
            "dep": (o.get("departureTime") or "")[:10],
            "ret": (i.get("departureTime") or "")[:10] or None,
            "from": o.get("from"), "to": o.get("to"),
            "stops": o.get("stops", 0), "stops_ret": i.get("stops") if i else None,
            "route": o.get("route") or [],
            "air": sorted({sg.get("carrierName", "?") for sg in segs}),
            "bag": it.get("baggage") or {},
            "url": it.get("bookingUrl") or "",
        })
    return sorted(out, key=lambda r: r["total"])


def plan(cfg: dict, today: date | None = None) -> dict | None:
    """Traduz o periodo (/periodo) em parametros do Kiwi. None se a janela for impossivel."""
    from .. import config
    ini, fim = config.janela(cfg, today)
    span = (fim - ini).days
    if span <= 21:   # janela curta: TODAS as estadias possiveis dentro dela
        nmin, nmax = max(1, int(cfg.get("estadia_min", 2))), max(1, span)
    else:
        ds = sorted(int(n) for n in cfg["duracoes"])
        nmin, nmax = ds[0], ds[-1]
    if ini + timedelta(days=nmin) > fim:
        return None
    return {"ini": ini, "fim": fim, "nmin": nmin, "nmax": nmax, "short": span <= 21}


def window_args(p: dict, bag: str = "mao") -> dict:
    a = {"departureDate": dmy(p["ini"]), "departureDateTo": dmy(p["fim"] - timedelta(days=p["nmin"])),
         "returnDate": dmy(p["ini"] + timedelta(days=p["nmin"])), "returnDateTo": dmy(p["fim"]),
         "nights_in_dst_from": p["nmin"], "nights_in_dst_to": p["nmax"],
         "currency": "BRL", "locale": "pt", "sort": "price"}
    if bag == "despachada":
        a["adults_hold_bags"] = [1]
    return a


def month_windows(p: dict, n: int, offset: int = 0) -> list[dict]:
    """Ate n sub-janelas mensais (rotativas) para formar a distribuicao de precos do periodo."""
    ini, fim, nmin, nmax = p["ini"], p["fim"], p["nmin"], p["nmax"]
    ms, d = [], date(ini.year, ini.month, 1)
    while d <= fim:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        a, b = max(ini, d), min(fim - timedelta(days=nmin), nxt - timedelta(days=1))
        if a <= b:
            ms.append({"ini": a, "fim": min(fim, b + timedelta(days=nmax)), "nmin": nmin, "nmax": nmax,
                       "dep_to": b})
        d = nxt
    if not ms:
        return []
    k = min(n, len(ms))
    return [ms[(offset + i) % len(ms)] for i in range(k)]


def month_args(m: dict, bag: str = "mao") -> dict:
    a = {"departureDate": dmy(m["ini"]), "departureDateTo": dmy(m["dep_to"]),
         "returnDate": dmy(m["ini"] + timedelta(days=m["nmin"])), "returnDateTo": dmy(m["fim"]),
         "nights_in_dst_from": m["nmin"], "nights_in_dst_to": m["nmax"],
         "currency": "BRL", "locale": "pt", "sort": "price"}
    if bag == "despachada":
        a["adults_hold_bags"] = [1]
    return a
