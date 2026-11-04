"""Radar PRINCIPAL (nuvem, GitHub Actions): Kiwi.com (inclui low-cost), periodo configuravel.

`python -m radar.scan [--dry] [--force] [--limit-dest N]`
Para cada destino: busca os MENORES valores ida+volta dentro do periodo (/periodo), compara com o normal
(amostra mensal do proprio periodo + historico) e avisa quando esta fora da curva. Publica data/top.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import date, datetime, timedelta

from . import config, msg, notify, store
from .airports import nome
from .outlier import judge
from .sources import kiwi

STATE = config.DATA / "state.json"
TOP = config.DATA / "top.json"


def brl(n: float) -> str:
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


def bag_txt(r: dict) -> str:
    b = r.get("bag") or {}
    if b.get("checkedBag"):
        return "com bagagem despachada"
    return "só item pessoal" if not b.get("cabinBag") else "com mala de mão"


def route_txt(r: dict) -> str:
    conn = "direto" if r["stops"] == 0 else f"{r['stops']} conexão(ões): " + "→".join(r["route"])
    return f"{conn} · {', '.join(r['air'])}"


def fmt_deal(dest: str, r: dict, why: str) -> str:
    d0 = date.fromisoformat(r["dep"])
    ret = date.fromisoformat(r["ret"]) if r["ret"] else None
    when = f"{d0:%d/%m/%Y} → {ret:%d/%m/%Y} ({(ret - d0).days} dias)" if ret else f"{d0:%d/%m/%Y} (só ida)"
    return chr(10).join([
        f"✈️ <b>SP → {nome(dest)}: {brl(r['total'])}</b>",
        when,
        route_txt(r) + f" · {bag_txt(r)}",
        f"📉 {why}",
        f"🔗 {r['url']}",
        "<i>Preço do Kiwi.com (inclui low-cost). Confira o total final antes de pagar.</i>"])


def fmt_escala(hub: str, alem: str, far: dict, direct: dict) -> str:
    eco = (direct["total"] - far["total"]) / direct["total"] * 100
    return chr(10).join([
        "🔴 <b>ESCALA OCULTA (zona cinza)</b>",
        f"SP → {nome(alem)} com conexão em {nome(hub)}: <b>{brl(far['total'])}</b> (só ida, {far['dep'][8:]}/{far['dep'][5:7]})",
        f"Ir só até {nome(hub)} custa {brl(direct['total'])} → <b>{eco:.0f}% mais barato</b> ir mais longe",
        f"Rota: {'→'.join(far['route'])} · {', '.join(far['air'])}",
        f"⚠️ Você desce em {hub} e não usa o resto. Só bagagem de mão, só ida (volta à parte), "
        "sem conta de milhas; viola o contrato da companhia e o resto do bilhete pode ser cancelado.",
        f"🔗 {far['url']}"])


def search_window(cfg: dict, dest: str, args_fn, win: dict) -> list[dict]:
    a = args_fn(win, cfg.get("bagagem", "mao"))
    a["allow_self_transfer"] = bool(cfg.get("autotransferencia", False))
    a.update(flyFrom=",".join(cfg["origens"]) if cfg["origens"] != config.DEFAULT["origens"] else "SAO", flyTo=dest)
    return kiwi.rows(kiwi.search(**a))


def run(dry: bool = False, force: bool = False, limit_dest: int | None = None, max_minutes: float = 28) -> int:
    cfg = config.load()
    st = store.load(STATE)
    cid = config.chat_id(cfg)
    now = store.utcnow()
    if not cfg["ativo"] and not force:
        print("radar pausado (/retomar)")
        return 0
    last = st.get("last_run")
    if not force and last and now - datetime.fromisoformat(last) < timedelta(hours=cfg["intervalo_horas"] * 0.9):
        print("ainda nao e hora (intervalo_horas)")
        return 0

    for b in [b for b in st.get("obs", {}) if not b.startswith("K|")]:   # historico antigo (Google) nao serve mais
        del st["obs"][b]
    p = kiwi.plan(cfg)
    if not p:
        notify.tg_send("⚠️ Período inválido: a janela é menor que a estadia mínima. Use /periodo ou /duracoes.", cid, dry)
        return 0
    dests = list(dict.fromkeys(list(cfg["destinos"]) + list(cfg["milhas"].get("destinos", []))))  # + destinos de milhas
    nd = limit_dest or int(cfg["destinos_por_rodada"])
    cur = int(st.get("cursor", 0)) % max(1, len(dests))
    chunk = [dests[(cur + i) % len(dests)] for i in range(min(nd, len(dests)))]
    st["cursor"] = (cur + len(chunk)) % max(1, len(dests))
    off = int(st.get("mes_offset", 0))
    st["mes_offset"] = off + 1
    print(f"periodo {p['ini']} -> {p['fim']} ({p['nmin']}-{p['nmax']} noites); {len(chunk)} destinos")

    res = st.setdefault("resultados", {})
    deals, falhas, t0 = [], 0, time.time()
    for dest in chunk:
        if time.time() - t0 > max_minutes * 60:
            print("tempo maximo; continua na proxima rodada")
            break
        try:
            allrows = search_window(cfg, dest, kiwi.window_args, p)
            if not allrows:
                res.pop(dest, None)
                continue
            best = allrows[0]
            sample = [best["total"]]
            n_meses = int(cfg.get("amostra_meses", 3)) if not p["short"] and (p["fim"] - p["ini"]).days > 45 else 0
            for m in kiwi.month_windows(p, n_meses, off):
                time.sleep(random.uniform(0.6, 1.4))
                mr = search_window(cfg, dest, kiwi.month_args, m)
                if mr:
                    sample.append(mr[0]["total"])
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"  {dest}: falhou ({e})", file=sys.stderr)
            continue
        bucket = f"K|{dest}"
        v_per = judge(best["total"], sample, cfg["sensibilidade"], min_n=4)
        v_his = judge(best["total"], store.sample(st, bucket), cfg["sensibilidade"], min_n=5)
        cap = cfg["limites"].get(dest)
        why = ("Bem mais barata que o normal para esse período" if v_per.is_outlier else
               "Bem mais barata que o histórico dessa rota" if v_his.is_outlier else
               f"Abaixo do seu limite ({brl(cap)})" if cap and best["total"] <= cap else "")
        pct = v_per.drop_pct if v_per.is_outlier else v_his.drop_pct if v_his.is_outlier else None
        store.add_obs(st, bucket, best["total"], d=best["dep"], r=best["ret"])
        res[dest] = {"top": allrows[:3], "t": now.isoformat(timespec="minutes"), "amostra": sample}
        if why and store.should_alert(st, f"{dest}-{best['dep']}-{best['ret']}", best["total"]):
            deals.append(msg.deal_dinheiro(dest, best, why, pct))
        print(f"  {dest}: menor {brl(best['total'])} ({best['dep']}→{best['ret']}) {', '.join(best['air'])}")
        time.sleep(random.uniform(0.6, 1.4))

    # escala oculta (so ida): destino MAIS LONGE com conexao no hub mais barato que ir so ao hub
    esc = cfg.get("escala_oculta", {})
    if esc.get("ativo"):
        ow = dict(p, nmin=p["nmin"])
        for hub, alems in esc.get("rotas", {}).items():
            if hub not in chunk:
                continue
            for alem in alems:
                try:
                    base = {"departureDate": kiwi.dmy(p["ini"]), "departureDateTo": kiwi.dmy(p["fim"] - timedelta(days=p["nmin"])),
                            "currency": "BRL", "locale": "pt", "sort": "price", "flyFrom": "SAO",
                            "allow_self_transfer": False}
                    d_hub = kiwi.rows(kiwi.search(**base, flyTo=hub))
                    d_far = kiwi.rows(kiwi.search(**base, flyTo=alem, stopover_airports=hub, max_sector_stopovers=1))
                    d_far = [r for r in d_far if hub in r["route"][1:-1]]
                    if d_hub and d_far:
                        eco = (d_hub[0]["total"] - d_far[0]["total"]) / d_hub[0]["total"] * 100
                        if eco >= esc.get("min_economia_pct", 20) and store.should_alert(
                                st, f"E-{hub}-{alem}-{d_far[0]['dep']}", d_far[0]["total"]):
                            deals.append(fmt_escala(hub, alem, d_far[0], d_hub[0]))
                except Exception as e:  # noqa: BLE001
                    print(f"  escala {hub}->{alem} falhou ({e})", file=sys.stderr)
                time.sleep(random.uniform(0.6, 1.4))

    quiet = config.in_quiet_hours(cfg)
    pend = st.setdefault("pendentes", [])
    if quiet:
        pend += deals
    else:
        for t in pend + deals:
            notify.alert(t, cid, dry=dry)
            store.remember_alert(st, t[:160])
        st["pendentes"] = []

    rows = []
    for dest, r in res.items():
        if r["top"]:
            rows.append({"dest": dest, **r["top"][0]})
    rows.sort(key=lambda x: x["total"])
    top = {"last_run": now.isoformat(timespec="minutes"), "de": p["ini"].isoformat(), "ate": p["fim"].isoformat(),
           "destinos": len(cfg["destinos"]), "cobertos": len(rows), "bagagem": cfg.get("bagagem", "mao"), "top": rows[:30]}

    hoje = config.now_brt().date().isoformat()
    if cfg.get("resumo_diario") and not quiet and st.get("heartbeat") != hoje and config.now_brt().hour >= 12 and rows and not dry:
        linhas = chr(10).join(f"• {nome(r['dest'])}: {brl(r['total'])}" for r in rows[:5])
        if notify.tg_send(f"🟢 Radar vivo. Menores valores no período:{chr(10)}{linhas}", cid, dry):
            st["heartbeat"] = hoje
    st["last_run"] = now.isoformat(timespec="minutes")
    st["ultima"] = {"destinos": len(chunk), "falhas": falhas, "avisos": len(deals)}
    store.prune(st)
    if not dry:
        store.save(STATE, st)
        TOP.write_text(json.dumps(top, ensure_ascii=False), encoding="utf-8")
    print(f"ok: {len(chunk) - falhas}/{len(chunk)} destinos, {len(deals)} avisos, menor {brl(rows[0]['total']) if rows else '-'}")
    if chunk and falhas / len(chunk) > 0.8 and not dry:
        notify.tg_send("⚠️ Radar: o Kiwi está falhando em quase tudo. Veja a aba Actions.", cid)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit-dest", type=int)
    a = ap.parse_args()
    raise SystemExit(run(a.dry, a.force, a.limit_dest))
