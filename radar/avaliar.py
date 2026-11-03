"""Avalia um alerta de milhas colado (grupos de passagem): vale mais milhas ou dinheiro?

Entrada (texto do grupo):
    SÃO PAULO ✈️ FRANKFURT / Cia: LATAM / Programa: LATAM Pass
    Ida: ✅ 70.024 milhas ou R$ 1.996 + datas   Volta: ✅ 63.059 milhas ou R$ 1.797 + datas
    Valor total: R$ 3.793 + txs
Saída: milhas totais, menor preço em DINHEIRO achado no Kiwi para as mesmas datas, valor da milha (R$/milheiro)
e veredito contra o seu custo de milheiro (`/milheiro`).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

from . import config
from .airports import NOMES
from .sources import kiwi


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


EXTRA = {"sao paulo": "SAO", "rio de janeiro": "RIO", "rio": "RIO", "campinas": "VCP", "guarulhos": "GRU",
         "brasilia": "BSB", "belo horizonte": "CNF", "nova york": "NYC", "new york": "NYC", "londres": "LON",
         "paris": "PAR", "roma": "ROM", "milao": "MIL", "madri": "MAD", "madrid": "MAD", "frankfurt": "FRA",
         "buenos aires": "BUE", "lisboa": "LIS", "orlando": "MCO", "miami": "MIA", "aruba": "AUA",
         "maceio": "MCZ", "vitoria": "VIX", "santiago": "SCL", "lima": "LIM"}


def iata(name: str) -> str | None:
    n = _norm(name)
    if n in EXTRA:
        return EXTRA[n]
    for code, nm in NOMES.items():
        if _norm(nm.split("(")[0]) == n:
            return code
    if re.fullmatch(r"[a-z]{3}", n):
        return n.upper()
    return None


RX_LEG = re.compile(r"(Ida|Volta)\s*:?[^\n]*\n\s*[✅✔]?\s*([\d\.]+)\s*milhas\s*ou\s*R\$\s*([\d\.,]+)(.*?)(?=\n\s*(?:Volta|Valor|Obs)|\Z)",
                    re.S | re.I)
RX_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def parse(text: str) -> dict | None:
    m = re.search(r"([^\n✈]+?)\s*✈️?\s*([^\n]+)", text)
    if not m or "milhas" not in text.lower():
        return None
    out = {"origem": m.group(1).strip(), "destino": m.group(2).strip(), "legs": {}}
    cia = re.search(r"Cia:\s*([^\n]+)", text)
    prog = re.search(r"Programa:\s*([^\n]+)", text)
    out["cia"], out["programa"] = (cia.group(1).strip() if cia else "?"), (prog.group(1).strip() if prog else "?")
    for leg in RX_LEG.finditer(text):
        ds = []
        for d, mo, y in RX_DATE.findall(leg.group(4)):
            y = int(y) + (2000 if int(y) < 100 else 0)
            ds.append(date(y, int(mo), int(d)))
        out["legs"][leg.group(1).lower()] = {"milhas": int(leg.group(2).replace(".", "")),
                                             "dinheiro": _num(leg.group(3)), "datas": sorted(ds)}
    tot = re.search(r"Valor total:\s*R\$\s*([\d\.,]+)", text)
    out["total_dinheiro_grupo"] = _num(tot.group(1)) if tot else None
    out["o"], out["d"] = iata(out["origem"]), iata(out["destino"])
    return out if "ida" in out["legs"] else None


def kiwi_cash(o: str, d: str, ida: date, volta: date | None) -> dict | None:
    a = {"flyFrom": o, "flyTo": d, "departureDate": kiwi.dmy(ida), "currency": "BRL", "locale": "pt", "sort": "price",
         "allow_self_transfer": False}
    if volta:
        a.update(returnDate=kiwi.dmy(volta))
    rows = kiwi.rows(kiwi.search(**a))
    return rows[0] if rows else None


def par_valido(ida: list, volta: list):
    """Primeira ida com alguma volta posterior (as listas do grupo nao vem pareadas)."""
    for d in ida:
        for v in volta:
            if v > d:
                return d, v
    return (ida[0], None) if ida else (None, None)


def avaliar(text: str, custo_milheiro: float = 16.0) -> str:
    p = parse(text)
    if not p:
        return "Não consegui ler esse alerta. Cole o texto inteiro do grupo (com Ida, Volta e Valor total)."
    ida, volta = p["legs"]["ida"], p["legs"].get("volta")
    milhas = ida["milhas"] + (volta["milhas"] if volta else 0)
    L = [f"🧮 <b>{p['origem']} → {p['destino']}</b> · {p['cia']} · {p['programa']}",
         f"Milhas ida+volta: <b>{milhas:,}</b>".replace(",", ".")]
    cash_g = p.get("total_dinheiro_grupo") or (ida["dinheiro"] + (volta["dinheiro"] if volta else 0))
    L.append(f"Dinheiro (preço da própria cia, segundo o grupo): R$ {cash_g:,.0f}".replace(",", "."))
    ref, ref_nome = cash_g, "da cia (grupo)"
    d_i, d_v = par_valido(ida["datas"], volta["datas"] if volta else [])
    if p["o"] and p["d"] and d_i:
        try:
            k = kiwi_cash(p["o"], p["d"], d_i, d_v)
        except Exception:  # noqa: BLE001
            k = None
        if k:
            L.append(f"Menor em dinheiro no Kiwi ({d_i:%d/%m}" + (f" → {d_v:%d/%m}" if d_v else " só ida") +
                     f"): <b>R$ {k['total']:,.0f}</b> ({', '.join(k['air'])})".replace(",", "."))
            if k["total"] < ref:
                ref, ref_nome = k["total"], "do Kiwi"
    vm = ref / milhas * 1000
    custo_total = milhas / 1000 * custo_milheiro
    L.append(f"💡 Valor da milha: <b>R$ {vm:.1f}/milheiro</b> (referência {ref_nome}). Você paga R$ {custo_milheiro:g}/milheiro "
             f"→ pagar com milhas custa ≈ R$ {custo_total:,.0f} + taxas".replace(",", "."))
    if vm >= custo_milheiro * 1.3:
        L.append("✅ <b>Vale a pena em milhas</b> (o valor da milha passa 30% do seu custo).")
    elif vm >= custo_milheiro:
        L.append("🟡 Empate técnico: só compensa se você já tem as milhas ou o saldo expira.")
    else:
        L.append("❌ <b>Melhor pagar em dinheiro</b> nesta rota/data.")
    L.append("<i>Taxas de embarque das milhas ficam de fora. Confirme no site da LATAM/Smiles.</i>")
    return chr(10).join(L)
