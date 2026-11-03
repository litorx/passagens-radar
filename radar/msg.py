"""Mensagens do Telegram: curtas, humanas, com milhas e reais na cara (HTML do Telegram)."""
from __future__ import annotations

from datetime import date

from .airports import nome

MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
NL = chr(10)


def brl(n: float) -> str:
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


def mil(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def dia(d: date) -> str:
    return f"{d.day:02d} {MES[d.month - 1]} {d.year}"


def noites(a: date, b: date) -> str:
    return f"{(b - a).days} dias"


def barra(pct: float) -> str:
    """Barrinha visual de 'quanto mais barato que o normal'."""
    n = max(1, min(10, round(pct / 10)))
    return "🟩" * n + "⬜" * (10 - n)


def deal_milhas(m: dict, motivo: str, custo_milheiro: float, ref_pct: float | None, label: str = "abaixo do normal") -> str:
    """m: dest, origin, dep, ret, ida, volta, milhas, programa, cash(opt), mm(opt), taxas(opt), url(opt)."""
    custo_milhas = m["milhas"] / 1000 * custo_milheiro
    L = [f"🔥 <b>OFERTA EM MILHAS</b> · {m['programa']}", "",
         f"🛫 <b>São Paulo → {nome(m['dest'])}</b>",
         f"📅 {dia(m['dep'])}  →  {dia(m['ret'])}  ({noites(m['dep'], m['ret'])})", "",
         f"✈️ <b>{mil(m['milhas'])} milhas</b> ida e volta",
         f"      ida {mil(m['ida'])} · volta {mil(m['volta'])}"]
    if m.get("cash"):
        L += [f"💵 ou <b>{brl(m['cash'])}</b> no menor preço em dinheiro",
              f"🧾 Pagando com milhas você gasta ≈ <b>{brl(custo_milhas)}</b> (a R$ {custo_milheiro:g} o milheiro) + taxas",
              f"💡 Cada mil milhas rendem <b>{brl(m['cash'] / m['milhas'] * 1000)}</b>"]
    else:
        L.append(f"🧾 ≈ <b>{brl(custo_milhas)}</b> em milhas (a R$ {custo_milheiro:g} o milheiro) + taxas")
    if m.get("taxas"):
        L.append(f"🏷️ Taxas de embarque: ≈ {brl(m['taxas'])}")
    if m.get("mm"):
        L.append(f"➕ Milhas+dinheiro (ida): {mil(m['mm'][0])} milhas + {brl(m['mm'][1])}")
    L.append("")
    if ref_pct:
        L.append(f"{barra(ref_pct)} <b>{ref_pct:.0f}% {label}</b>")
    L.append(f"✅ {motivo}")
    if m.get("url"):
        L.append(f"🔗 {m['url']}")
    L.append("<i>Preços mudam a qualquer momento. Confirme no site antes de emitir.</i>")
    return NL.join(L)


def deal_dinheiro(dest: str, r: dict, motivo: str, pct: float | None) -> str:
    """r: total, dep, ret, route, stops, air, bag, url."""
    d0 = date.fromisoformat(r["dep"])
    ret = date.fromisoformat(r["ret"]) if r.get("ret") else None
    b = r.get("bag") or {}
    mala = "com mala despachada" if b.get("checkedBag") else ("com mala de mão" if b.get("cabinBag") else "só item pessoal (mala é à parte)")
    paradas = "voo direto" if r["stops"] == 0 else f"{r['stops']} conexão: " + " → ".join(r["route"])
    L = ["💸 <b>PASSAGEM EM DINHEIRO</b>", "",
         f"🛫 <b>São Paulo → {nome(dest)}</b>",
         f"📅 {dia(d0)}" + (f"  →  {dia(ret)}  ({noites(d0, ret)})" if ret else "  (só ida)"), "",
         f"💵 <b>{brl(r['total'])}</b> ida e volta",
         f"✈️ {', '.join(r['air'])} · {paradas}",
         f"🧳 {mala}", ""]
    if pct:
        L.append(f"{barra(pct)} <b>{pct:.0f}% abaixo do normal</b>")
    L.append(f"✅ {motivo}")
    if r.get("url"):
        L.append(f"🔗 {r['url']}")
    L.append("<i>Preço do Kiwi.com. Confira o total final antes de pagar.</i>")
    return NL.join(L)
