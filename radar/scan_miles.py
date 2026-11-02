"""Radar de MILHAS (roda no SEU PC: Smiles/LATAM bloqueiam servidores de nuvem).

`python -m radar.scan_miles [--dry] [--force] [--limit N] [--latam]`
Le a config do repositorio (CONFIG_URL = link 'raw' do data/config.json) ou do arquivo local,
entao os comandos do celular valem aqui tambem. Avisa pelo mesmo bot do Telegram.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import date, datetime, timedelta

import requests

from . import config, dates, notify, store
from .airports import nome
from .outlier import judge

STATE = config.LOCAL / "state_miles.json"
CASH_STATE = config.DATA / "state.json"


def load_cfg() -> dict:
    url = os.environ.get("CONFIG_URL")
    if url:
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            tmp = config.LOCAL / "config_remote.json"
            config.LOCAL.mkdir(exist_ok=True)
            tmp.write_text(r.text, encoding="utf-8")
            return config.load(tmp)
        except Exception as e:  # noqa: BLE001
            print("config remota falhou, usando local:", e)
    return config.load()


def cash_reference(dest: str, month: str) -> float | None:
    """Mediana de dinheiro (do radar de nuvem, se estiver baixado) para comparar o valor da milha."""
    try:
        st = json.loads(CASH_STATE.read_text(encoding="utf-8"))
        vals = [o["p"] for o in st.get("obs", {}).get(f"{dest}|{month}", [])]
        return sorted(vals)[len(vals) // 2] if len(vals) >= 5 else None
    except Exception:  # noqa: BLE001
        return None


def fmt(m: dict, rec: dict) -> str:
    dest, dep, ret = m["dest"], m["dep"], m["ret"]
    lines = [f"🏷️ <b>MILHAS · SP → {nome(dest)}: {m['milhas']:,} milhas ida+volta</b>".replace(",", "."),
             f"{m['origin']}→{dest} · {dep:%d/%m/%Y} → {ret:%d/%m/%Y} · {m['fonte']}"]
    if m.get("mm"):
        lines.append(f"Milhas+dinheiro (ida): {m['mm'][0]:,} milhas + R$ {m['mm'][1]:,.0f}".replace(",", "."))
    if rec.get("valor"):
        lines.append(f"💡 Valor da milha ≈ R$ {rec['valor']:.1f}/milheiro "
                     f"(você paga R$ {rec['custo']:g}) vs dinheiro mediano R$ {rec['cash']:,.0f}".replace(",", "."))
    lines.append(f"📉 {rec['why']}")
    lines.append("<i>Antes das taxas. Confira e emita no site oficial.</i>")
    return "\n".join(lines)


def run(dry=False, force=False, limit=None, latam=False) -> int:
    cfg = load_cfg()
    mc = cfg["milhas"]
    if not mc["ativo"] and not force:
        print("milhas desligado (/milhas on)")
        return 0
    st = store.load(STATE)
    cid = config.chat_id(cfg)
    combos = dates.build_combos(cfg, date.today(), None)
    chunk, st["cursor"] = dates.pick(combos, int(st.get("cursor", 0)), limit or 10)
    origens = cfg["origens"] or ["GRU"]
    found = []

    from .sources import smiles as S
    with S.Smiles() as sm:
        for i, (dest, dep, dur) in enumerate(chunk):
            origin = origens[(int(st["cursor"]) + i) % len(origens)]
            ret = dep + timedelta(days=dur)
            ida = sm.search(origin, dest, dep)
            volta = sm.search(dest, origin, ret)
            time.sleep(random.uniform(3, 6))
            if not ida or not volta:
                continue
            a, b = ida.get("milhas_direto") or ida.get("milhas_min"), volta.get("milhas_direto") or volta.get("milhas_min")
            if not a or not b:
                continue
            tot = a + b
            bucket = f"{dest}|{dep:%Y-%m}"
            store.add_obs(st, bucket, tot, d=dep.isoformat(), r=ret.isoformat(), o=origin, s="smiles")
            found.append({"origin": origin, "dest": dest, "dep": dep, "ret": ret, "milhas": tot,
                          "mm": ida.get("milhas_mais_dinheiro"), "fonte": "Smiles", "bucket": bucket})

    if latam:
        from .sources import latam as L
        with L.Latam() as lt:
            for i, (dest, dep, dur) in enumerate(chunk[:4]):
                origin = origens[i % len(origens)]
                ret = dep + timedelta(days=dur)
                ida, volta = lt.search(origin, dest, dep), lt.search(dest, origin, ret)
                if ida and volta:
                    tot = ida["milhas"] + volta["milhas"]
                    bucket = f"{dest}|{dep:%Y-%m}|latam"
                    store.add_obs(st, bucket, tot, d=dep.isoformat(), r=ret.isoformat(), o=origin, s="latam")
                    found.append({"origin": origin, "dest": dest, "dep": dep, "ret": ret, "milhas": tot,
                                  "mm": None, "fonte": f"LATAM Pass (+ R$ {ida['taxas'] + volta['taxas']:.0f} taxas)",
                                  "bucket": bucket})

    for m in found:
        v = judge(m["milhas"], store.sample(st, m["bucket"]), mc["sensibilidade"])
        cap = mc["limites_milhas"].get(m["dest"])
        why = v.reason if v.is_outlier else (f"abaixo do seu limite ({cap:,} milhas)".replace(",", ".") if cap and m["milhas"] <= cap else "")
        rec = {"why": why}
        cash = cash_reference(m["dest"], f"{m['dep']:%Y-%m}")
        if cash:
            rec.update(cash=cash, custo=mc["custo_milheiro"], valor=cash / m["milhas"] * 1000)
            if rec["valor"] >= mc["custo_milheiro"] * 1.3 and not why:
                rec["why"] = why = "milhas valem mais que dinheiro nesta rota/data"
        if why and store.should_alert(st, f"M-{m['origin']}-{m['dest']}-{m['dep']}-{m['ret']}", m["milhas"]):
            txt = fmt(m, rec)
            if config.in_quiet_hours(cfg):
                st.setdefault("pendentes", []).append(txt)
            else:
                notify.alert(txt, cid, title="Milhas fora da curva", dry=dry)
    if not config.in_quiet_hours(cfg):
        for txt in st.pop("pendentes", []):
            notify.alert(txt, cid, dry=dry)
    st["last_run"] = store.utcnow().isoformat(timespec="minutes")
    store.prune(st)
    if not dry:
        store.save(STATE, st)
    print(f"ok: {len(found)} leituras de milhas")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--latam", action="store_true")
    a = ap.parse_args()
    raise SystemExit(run(a.dry, a.force, a.limit, a.latam))
