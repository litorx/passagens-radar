"""Radar de DINHEIRO (roda na nuvem, GitHub Actions). `python -m radar.scan_cash [--dry] [--force]`"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone

from . import config, dates, notify, store
from .airports import nome
from .outlier import judge
from .sources import cash_google

STATE = config.DATA / "state.json"


def brl(n: float) -> str:
    return "R$ " + f"{int(round(n)):,}".replace(",", ".")


def fmt_alert(origin, dest, dep, ret, price, airlines, why):
    n = (ret - dep).days
    return (f"✈️ <b>SP → {nome(dest)}: {brl(price)}</b>\n"
            f"{origin}→{dest} · {dep:%d/%m/%Y} → {ret:%d/%m/%Y} ({n} dias)\n"
            f"Cia: {', '.join(airlines) or '?'}\n"
            f"📉 {why}\n"
            f"🔎 Confira (inclui low-cost): {notify.skyscanner_url(origin, dest, dep, ret)}\n"
            f"<i>Preço de ida e volta, só bagagem de mão. Fonte: Google Flights.</i>")


def run(dry: bool = False, force: bool = False, max_minutes: float = 25, limit: int | None = None) -> int:
    cfg = config.load()
    st = store.load(STATE)
    cid = config.chat_id(cfg)
    now = store.utcnow()

    if not cfg["ativo"] and not force:
        print("radar pausado (/retomar para ligar)")
        return 0
    last = st.get("last_run")
    if not force and last and now - datetime.fromisoformat(last) < timedelta(hours=cfg["intervalo_horas"] * 0.9):
        print("ainda nao e hora (intervalo_horas)")
        return 0

    today = date.today()
    horizon = st.setdefault("horizonte", {})
    combos = dates.build_combos(cfg, today, horizon)
    n_run = limit or int(cfg["pares_por_rodada"])
    chunk, st["cursor"] = dates.pick(combos, int(st.get("cursor", 0)), n_run)
    origens = cfg["origens"] or ["GRU"]
    print(f"{len(combos)} combinacoes no total; rodada de {len(chunk)}")

    results, fails, t0 = [], 0, time.time()
    for i, (dest, dep, dur) in enumerate(chunk):
        if time.time() - t0 > max_minutes * 60:
            print("tempo maximo da rodada; continua na proxima")
            break
        origin = origens[(int(st.get("cursor", 0)) + i) % len(origens)]
        ret = dep + timedelta(days=dur)
        time.sleep(random.uniform(2.5, 5.5))
        try:
            r = cash_google.fetch(origin, dest, dep, ret)
        except Exception as e:  # noqa: BLE001
            fails += 1
            print(f"falha {origin}-{dest} {dep}: {e}", file=sys.stderr)
            continue
        if not r.found:
            continue
        bucket = f"{dest}|{dep:%Y-%m}"
        store.add_obs(st, bucket, r.price, d=dep.isoformat(), r=ret.isoformat(), o=origin,
                      a=r.airlines[:2])
        results.append((origin, dest, dep, ret, r, bucket))
        h = horizon.get(dest)
        if h is None or dep.isoformat() > h:
            old = h
            horizon[dest] = dep.isoformat()
            if old and (dep - date.fromisoformat(old)).days >= 7:
                st.setdefault("novidades", []).append(
                    f"🆕 Calendário abriu: {nome(dest)} agora até {dep:%d/%m/%Y}")

    alerts = []
    for origin, dest, dep, ret, r, bucket in results:
        v = judge(r.price, store.sample(st, bucket), cfg["sensibilidade"])
        cap = cfg["limites"].get(dest)
        why = v.reason if v.is_outlier else (f"abaixo do seu limite ({brl(cap)})" if cap and r.price <= cap else "")
        if why and store.should_alert(st, f"{origin}-{dest}-{dep}-{ret}", r.price):
            alerts.append(fmt_alert(origin, dest, dep, ret, r.price, r.airlines, why))

    quiet = config.in_quiet_hours(cfg)
    pend = st.setdefault("pendentes", [])
    if quiet:
        pend += alerts  # guarda para depois do silencio
    else:
        for txt in pend + alerts + st.pop("novidades", []):
            notify.alert(txt, cid, dry=dry)
            store.remember_alert(st, txt[:160])
        st["pendentes"] = []

    # batimento diario: prova de vida
    hoje = config.now_brt().date().isoformat()
    if not quiet and st.get("heartbeat") != hoje and config.now_brt().hour >= 12 and not dry:
        best = {}
        for b, obs in st.get("obs", {}).items():
            if obs:
                best[b.split("|")[0]] = min(best.get(b.split("|")[0], 10**9), min(o["p"] for o in obs[-30:]))
        top = sorted(best.items(), key=lambda x: x[1])[:5]
        linhas = "\n".join(f"• {nome(d)}: {brl(p)}" for d, p in top) or "ainda coletando"
        notify.tg_send(f"🟢 Radar vivo. Menores preços vistos:\n{linhas}", cid, dry)
        st["heartbeat"] = hoje

    st["last_run"] = now.isoformat(timespec="minutes")
    st["ultima_rodada"] = {"consultas": len(chunk), "falhas": fails, "com_preco": len(results)}
    store.prune(st)
    if not dry:
        store.save(STATE, st)
    print(f"ok: {len(results)} precos, {fails} falhas, {len(alerts)} alertas")
    nothing = len(chunk) >= 8 and not results      # nenhum preco em 8+ consultas = fonte quebrada
    if chunk and (fails / len(chunk) > 0.8 or nothing) and not dry:
        notify.tg_send("⚠️ Radar: a fonte (Google Flights) está falhando em quase tudo. "
                       "Pode ter mudado/bloqueado. Veja a aba Actions.", cid)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true", default=os.environ.get("FORCE") == "1")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    raise SystemExit(run(a.dry, a.force, limit=a.limit))
