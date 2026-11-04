"""Radar AUTONOMO de milhas (roda no SEU PC): acha sozinho ofertas em milhas / milhas+dinheiro.

`python -m radar.scan_miles [--dry] [--force] [--latam] [--limit N]`

Como funciona (e por que e lento de proposito):
  * Smiles e LATAM Pass nao tem API publica; usamos as proprias paginas num Chrome real, UMA busca por vez,
    com pausa de 25-45 s e orcamento por rodada (`milhas.buscas_por_rodada`). Em ~25 buscas seguidas a Smiles
    comecou a nao responder (testado em 03/11/2026), entao o radar RECUA: 2 falhas seguidas = para a rodada e
    descansa `milhas.descanso_horas` (padrao 3 h). Nao ha tentativa de burlar captcha/bloqueio.
  * Cada combinacao (destino, ida, volta) gasta 2 buscas (ida e volta). A rotacao cobre rotas e datas ao longo do dia.
  * Oferta = (a) milhas valem >= 1,3x o seu custo do milheiro contra o MENOR preco em dinheiro (Kiwi), ou
    (b) fora da curva do proprio historico da rota, ou (c) abaixo do seu limite em milhas (/limitemilhas).
  * Aviso no formato dos grupos (milhas ou R$, datas, total) + valor da milha.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from datetime import date, datetime, timedelta

from . import config, dates, msg, notify, store
from .airports import nome
from .outlier import judge
from .sources import kiwi

STATE = config.LOCAL / "state_miles.json"


def brl(n: float) -> str:
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


def mil(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def cash_reference(dest: str) -> float | None:
    """Menor valor em DINHEIRO ida+volta do periodo (Kiwi, data/top.json): referencia conservadora."""
    try:
        t = json.loads((config.DATA / "top.json").read_text(encoding="utf-8"))
        for r in t.get("top", []):
            if r["dest"] == dest:
                return float(r["total"])
    except Exception:  # noqa: BLE001
        pass
    return None


def cash_for_dates(origin: str, dest: str, dep: date, ret: date) -> float | None:
    """Menor preco em DINHEIRO ida+volta para as MESMAS datas (Kiwi). Cai para o menor do periodo se falhar."""
    try:
        d = kiwi.search(flyFrom=origin, flyTo=dest, departureDate=kiwi.dmy(dep), returnDate=kiwi.dmy(ret),
                        currency="BRL", locale="pt", sort="price", allow_self_transfer=False)
        rows = kiwi.rows(d)
        if rows:
            return rows[0]["total"]
    except Exception:  # noqa: BLE001
        pass
    return cash_reference(dest)


def evaluate(m: dict, hist_sample: list, mc: dict, cash: float | None):
    """(motivo, pct, rotulo) ou ('', None, '') quando NAO e uma oferta realmente boa.
    O custo em milhas INCLUI as taxas de embarque quando conhecidas (LATAM): sem isso uma oferta com
    taxas altas parece melhor do que e (ex.: Medellin 69.285 milhas + R$ 909 de taxas ~ empata com o dinheiro)."""
    custo = mc["custo_milheiro"]
    custo_total = m["milhas"] / 1000 * custo + (m.get("taxas") or 0)
    m["custo_total"] = custo_total
    if cash:
        m["cash"] = cash
        economia = (cash - custo_total) / cash * 100
        if economia >= mc["sensibilidade"]:
            return ("Pagando com milhas (já contando as taxas) sai bem mais barato que em dinheiro", economia,
                    "mais barato que pagar em dinheiro")
    cap = mc["limites_milhas"].get(m["dest"])
    if cap and m["milhas"] <= cap:
        return f"Abaixo do seu limite ({mil(cap)} milhas)", None, ""
    v = judge(m["milhas"], hist_sample, mc["sensibilidade"], min_n=6)
    if v.is_outlier:
        return "Bem abaixo do normal de milhas dessa rota", v.drop_pct, "abaixo do normal"
    return "", None, ""


def run(dry: bool = False, force: bool = False, limit: int | None = None, latam: bool = False) -> int:
    config.load_env()
    cfg = config.load()
    mc = cfg["milhas"]
    if not mc["ativo"] and not force:
        print("milhas desligado (/milhas on)")
        return 0
    st = store.load(STATE)
    now = store.utcnow()
    if not force and st.get("descanso_ate") and now < datetime.fromisoformat(st["descanso_ate"]):
        print("em descanso ate", st["descanso_ate"])
        return 0
    cid = config.chat_id(cfg)
    budget = limit or int(mc.get("buscas_por_rodada", 10))
    # espaco de busca ENXUTO p/ milhas: 1 data a cada `passo_dias`, viagens de `duracoes`; destinos de dinheiro
    # mais CARO primeiro (ali a milha rende mais); sem referencia de dinheiro vao por ultimo.
    cfg_m = dict(cfg, passo_dias=mc.get("passo_dias", 10), duracoes=mc.get("duracoes", [7]))
    cfg_m["destinos"] = sorted(mc.get("destinos") or cfg["destinos"], key=lambda d: -(cash_reference(d) or 0))
    combos = dates.build_combos(cfg_m, date.today(), None)
    random.Random(7).shuffle(combos)   # cobre destinos e datas variados a cada rodada
    n_comb = max(1, budget // 2)
    chunk, st["cursor"] = dates.pick(combos, int(st.get("cursor", 0)), n_comb)
    origens = cfg["origens"] or ["GRU"]
    print(f"{len(chunk)} combinacoes ({len(chunk) * 2} buscas) de {len(combos)}")

    found, fails, blocked = [], 0, False
    from .sources import smiles as S
    with S.Smiles() as sm:
        for i, (dest, dep, dur) in enumerate(chunk):
            origin = origens[(int(st["cursor"]) + i) % len(origens)]
            ret = dep + timedelta(days=dur)
            ida = sm.search(origin, dest, dep)
            time.sleep(random.uniform(25, 45))
            volta = sm.search(dest, origin, ret) if ida else None
            time.sleep(random.uniform(25, 45))
            if not ida or not volta:
                fails += 1
                print(f"  sem resposta {origin}<->{dest} {dep} (falhas seguidas: {fails})")
                if fails >= 2:   # recuo: nao insiste quando a Smiles para de responder
                    blocked = True
                    break
                continue
            fails = 0
            a = ida.get("milhas_direto") or ida.get("milhas_min")
            b = volta.get("milhas_direto") or volta.get("milhas_min")
            if not a or not b:
                continue
            bucket = f"M|{dest}"
            m = {"origin": origin, "dest": dest, "dep": dep, "ret": ret, "ida": a, "volta": b, "milhas": a + b,
                 "mm": ida.get("milhas_mais_dinheiro"), "programa": "Smiles", "bucket": bucket}
            why, pct, lab = evaluate(m, store.sample(st, bucket), mc, cash_for_dates(origin, dest, dep, ret))
            store.add_obs(st, bucket, m["milhas"], d=dep.isoformat(), r=ret.isoformat(), o=origin)
            print(f"  Smiles {dest} {dep}->{ret}: {mil(m['milhas'])} milhas" + (f" | OFERTA: {why}" if why else ""))
            if why and store.should_alert(st, f"M-{origin}-{dest}-{dep}-{ret}", m["milhas"]):
                found.append((m, why, pct, lab))

    if (latam or mc.get("latam")) and not blocked:
        from .sources import latam as L
        with L.Latam() as lt:
            for i, (dest, dep, dur) in enumerate(chunk[:max(1, n_comb // 2)]):
                origin = origens[i % len(origens)]
                ret = dep + timedelta(days=dur)
                ida = lt.search(origin, dest, dep, back=ret)
                time.sleep(random.uniform(25, 45))
                volta = lt.search(dest, origin, ret, back=ret + timedelta(days=dur)) if ida else None
                time.sleep(random.uniform(25, 45))
                if not ida or not volta:
                    continue
                m = {"origin": origin, "dest": dest, "dep": dep, "ret": ret, "ida": ida["milhas"],
                     "volta": volta["milhas"], "milhas": ida["milhas"] + volta["milhas"],
                     "taxas": ida["taxas"] + volta["taxas"], "programa": "LATAM Pass", "bucket": f"M|{dest}|latam"}
                why, pct, lab = evaluate(m, store.sample(st, m["bucket"]), mc, cash_for_dates(origin, dest, dep, ret))
                store.add_obs(st, m["bucket"], m["milhas"], d=dep.isoformat(), r=ret.isoformat(), o=origin)
                print(f"  LATAM {dest} {dep}->{ret}: {mil(m['milhas'])} milhas" + (f" | OFERTA: {why}" if why else ""))
                if why and store.should_alert(st, f"L-{origin}-{dest}-{dep}-{ret}", m["milhas"]):
                    found.append((m, why, pct, lab))

    quiet = config.in_quiet_hours(cfg)
    texts = [msg.deal_milhas(m, w, mc["custo_milheiro"], pct, lab or "abaixo do normal") for m, w, pct, lab in found]
    if quiet:
        st.setdefault("pendentes", []).extend(texts)
    else:
        for t in st.pop("pendentes", []) + texts:
            notify.alert(t, cid, title="Milhas: oferta", dry=dry)
    if blocked:
        st["descanso_ate"] = (now + timedelta(hours=float(mc.get("descanso_horas", 3)))).isoformat(timespec="minutes")
        print("Smiles parou de responder: descansando", mc.get("descanso_horas", 3), "h (sem insistir)")
    st["last_run"] = now.isoformat(timespec="minutes")
    store.prune(st)
    if not dry:
        store.save(STATE, st)
    print(f"ok: {len(found)} ofertas nesta rodada")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--latam", action="store_true")
    a = ap.parse_args()
    raise SystemExit(run(a.dry, a.force, a.limit, a.latam))
