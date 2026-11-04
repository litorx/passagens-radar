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


def em_pico(d: date, picos: list) -> bool:
    md = (d.month, d.day)
    for m1, d1, m2, d2 in picos:
        ini, fim = (m1, d1), (m2, d2)
        if (ini <= md <= fim) if ini <= fim else (md >= ini or md <= fim):
            return True
    return False


def montar_combos(cfg: dict, mc: dict, today: date) -> list:
    """(destino, ida, estadia) usando os PADROES: estadia tipica por destino, sem sabado, sem pico de fim de ano."""
    ini, fim = config.janela(cfg, today)
    end = min(fim, today + timedelta(days=dates.SALE_HORIZON_DAYS))
    step = max(1, int(mc.get("passo_dias", 10)))
    dests = sorted(mc.get("destinos") or cfg["destinos"], key=lambda d: -(cash_reference(d) or 0))
    out = []
    for dest in dests:
        stays = mc.get("estadias", {}).get(dest) or mc.get("estadia_padrao", [7])
        d, k = ini, 0
        quentes = mc.get("janelas_quentes", {}).get(dest, [])
        while d <= end:
            if not (mc.get("evitar_sabado", True) and d.weekday() == 5) and not em_pico(d, mc.get("evitar_pico", [])):
                out.append((dest, d, int(stays[k % len(stays)])))
            d += timedelta(days=int(mc.get("passo_quente", 4)) if quentes and em_pico(d, quentes) else step)
            k += 1
    return out


def _melhor_do_ciclo(st: dict, m: dict) -> None:
    """Guarda a melhor leitura de cada destino no ciclo (para o resumo/tier list)."""
    if not m.get("cash") or not m.get("custo_total"):
        return
    eco = (m["cash"] - m["custo_total"]) / m["cash"] * 100
    cur = st.setdefault("ciclo", {}).get(m["dest"])
    if cur is None or eco > cur["pct"]:
        st["ciclo"][m["dest"]] = {"pct": eco, "milhas": m["milhas"], "cash": m["cash"], "programa": m["programa"],
                                  "dep": m["dep"].isoformat(), "ret": m["ret"].isoformat()}


def agrupar(st: dict, found: list) -> list:
    """Um aviso por (programa, destino): o melhor + 'datas parecidas'. Repetidos viram um so (cooldown 14 dias)."""
    grupos = {}
    for m, why, pct, lab in found:
        grupos.setdefault((m["programa"], m["dest"]), []).append((m, why, pct, lab))
    out = []
    for (prog, dest), itens in grupos.items():
        itens.sort(key=lambda x: x[0]["milhas"])
        m, why, pct, lab = itens[0]
        if not store.should_alert_dest(st, f"MD-{prog}-{dest}", m["milhas"]):
            continue
        extras = [(x[0]["dep"], x[0]["ret"], x[0]["milhas"]) for x in itens[1:]]
        out.append((m, why, pct, lab, extras))
    return out


def tier_milhas(st: dict, cfg: dict) -> str | None:
    ciclo = st.get("ciclo", {})
    if not ciclo:
        return None
    rows = [{"dest": d, "pct": max(0.0, v["pct"]), **v} for d, v in ciclo.items()]

    def linha(r):
        a, b = date.fromisoformat(r["dep"]), date.fromisoformat(r["ret"])
        return (f"{nome(r['dest'])}: <b>{mil(r['milhas'])} milhas</b> vs {brl(r['cash'])} "
                f"(−{r['pct']:.0f}%) · {a:%d/%m}→{b:%d/%m/%y} · {r['programa']}")
    return msg.tierlist("TIER LIST DO CICLO · milhas",
                        "Fim do ciclo · melhor economia de cada destino pagando com milhas (já com taxas, vs dinheiro das mesmas datas)",
                        rows, msg.TIERS_MILHAS, linha)


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
    n_comb = max(1, budget // 2)
    combos = montar_combos(cfg, mc, date.today())
    random.Random(7).shuffle(combos)   # cobre destinos e datas variados a cada rodada
    # 1o as datas VIZINHAS de leituras boas (ofertas vem em blocos de datas), depois a rotacao normal
    fila = [(d, date.fromisoformat(x), int(n)) for d, x, n in st.get("explorar", [])]
    prio, fila = fila[: max(0, n_comb // 2)], fila[max(0, n_comb // 2):]
    old_cursor = int(st.get("cursor", 0))
    resto, st["cursor"] = dates.pick(combos, old_cursor, n_comb - len(prio))
    chunk = prio + resto
    st["explorar"] = [[d, x.isoformat(), n] for d, x, n in fila]
    vistos = set(st.get("vistos", []))
    origens = cfg["origens"] or ["GRU"]
    print(f"{len(chunk)} combinacoes ({len(chunk) * 2} buscas); {len(prio)} vizinhas; {len(combos)} no espaco de busca")

    def vizinhas(dest, dep, dur):
        k_ = int(mc.get("explorar_vizinhas", 2))
        for dd in range(-k_, k_ + 1):
            nd = dep + timedelta(days=dd)
            item = [dest, nd.isoformat(), dur]
            if dd and nd > date.today() + timedelta(days=7) and f"{dest}|{nd}|{dur}" not in vistos and item not in st["explorar"]:
                st["explorar"].append(item)

    found, fails, blocked = [], 0, False
    from .sources import smiles as S
    with S.Smiles() as sm:
        for i, (dest, dep, dur) in enumerate(chunk):
            origin = origens[(int(st["cursor"]) + i) % len(origens)]
            ret = dep + timedelta(days=dur)
            vistos.add(f"{dest}|{dep}|{dur}")
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
                 "mm": ida.get("milhas_mais_dinheiro"), "programa": "Smiles", "bucket": bucket,
                 "url": S._url(origin, dest, dep)}
            why, pct, lab = evaluate(m, store.sample(st, bucket), mc, cash_for_dates(origin, dest, dep, ret))
            store.add_obs(st, bucket, m["milhas"], d=dep.isoformat(), r=ret.isoformat(), o=origin)
            cash_txt = brl(m["cash"]) if m.get("cash") else "?"
            print(f"  Smiles {dest} {dep}->{ret}: {mil(m['milhas'])} milhas, dinheiro {cash_txt}"
                  + (f" | OFERTA: {why}" if why else ""))
            promissor = m.get("cash") and m.get("custo_total") and (m["cash"] - m["custo_total"]) / m["cash"] * 100 >= 0.7 * mc["sensibilidade"]
            if why or promissor:
                vizinhas(dest, dep, dur)
            _melhor_do_ciclo(st, m)
            if why:
                found.append((m, why, pct, lab))

    latam_ok = not st.get("latam_descanso_ate") or now >= datetime.fromisoformat(st["latam_descanso_ate"])
    if (latam or mc.get("latam")) and not blocked and latam_ok:
        from .sources import latam as L
        with L.Latam() as lt:
            for i, (dest, dep, dur) in enumerate(chunk[:max(1, n_comb // 2)]):
                origin = origens[i % len(origens)]
                ret = dep + timedelta(days=dur)
                ida = lt.search(origin, dest, dep, back=ret)
                time.sleep(random.uniform(25, 45))
                if not ida:   # LATAM respondeu 403/vazio (visto em 03/11/2026): NAO insiste
                    st["latam_descanso_ate"] = (now + timedelta(hours=float(mc.get("latam_descanso_horas", 6)))).isoformat(timespec="minutes")
                    print("LATAM sem resposta (provavel bloqueio anti-robo): descansando", mc.get("latam_descanso_horas", 6), "h")
                    break
                volta = lt.search(dest, origin, ret, back=ret + timedelta(days=dur))
                time.sleep(random.uniform(25, 45))
                if not volta:
                    continue
                m = {"origin": origin, "dest": dest, "dep": dep, "ret": ret, "ida": ida["milhas"],
                     "volta": volta["milhas"], "milhas": ida["milhas"] + volta["milhas"],
                     "taxas": ida["taxas"] + volta["taxas"], "programa": "LATAM Pass", "bucket": f"M|{dest}|latam",
                     "url": L.url(origin, dest, dep, ret)}
                why, pct, lab = evaluate(m, store.sample(st, m["bucket"]), mc, cash_for_dates(origin, dest, dep, ret))
                store.add_obs(st, m["bucket"], m["milhas"], d=dep.isoformat(), r=ret.isoformat(), o=origin)
                print(f"  LATAM {dest} {dep}->{ret}: {mil(m['milhas'])} milhas + {brl(m['taxas'])} taxas"
                      + (f" | OFERTA: {why}" if why else ""))
                if why:
                    vizinhas(dest, dep, dur)
                _melhor_do_ciclo(st, m)
                if why:
                    found.append((m, why, pct, lab))
    elif (latam or mc.get("latam")) and not latam_ok:
        print("LATAM em descanso ate", st["latam_descanso_ate"])

    st["vistos"] = sorted(vistos)[-3000:]
    quiet = config.in_quiet_hours(cfg)
    texts = [msg.deal_milhas(m, w, mc["custo_milheiro"], pct, lab or "abaixo do normal", extras)
             for m, w, pct, lab, extras in agrupar(st, found)]
    if old_cursor + len(resto) >= len(combos):          # FIM DE CICLO: resumo com tier list
        t = tier_milhas(st, cfg)
        if t:
            texts.append(t)
        st["ciclo"] = {}
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
    print(f"ok: {len(found)} ofertas nesta rodada; fila de vizinhas: {len(st['explorar'])}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--latam", action="store_true")
    a = ap.parse_args()
    raise SystemExit(run(a.dry, a.force, a.limit, a.latam))
