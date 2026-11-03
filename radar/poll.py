"""Le comandos do Telegram (roda a cada ~5 min no GitHub Actions) e aplica na config."""
from __future__ import annotations

import json
import os
import sys

import requests

from . import bot, config, store
from .airports import nome

OFFSET = config.DATA / "bot_offset.json"
STATE = config.DATA / "state.json"


def api(method: str, **params):
    tok = os.environ["TELEGRAM_BOT_TOKEN"]
    r = requests.post(f"https://api.telegram.org/bot{tok}/{method}", data=params, timeout=30)
    r.raise_for_status()
    return r.json()


def status_text(cfg: dict) -> str:
    st = store.load(STATE)
    obs = st.get("obs", {})
    best = {}
    for b, lst in obs.items():
        if lst:
            d = b.split("|")[0]
            best[d] = min(best.get(d, 10**9), min(o["p"] for o in lst[-30:]))
    top = sorted(best.items(), key=lambda x: x[1])[:6]
    hz = st.get("horizonte", {})
    ur = st.get("ultima_rodada", {})
    linhas = [
        f"{'🟢 ligado' if cfg['ativo'] else '⏸️ pausado'} · a cada {cfg['intervalo_horas']:g} h · "
        f"sensibilidade {cfg['sensibilidade']:g}%",
        f"Origens: {', '.join(cfg['origens'])} · {len(cfg['destinos'])} destinos",
        f"Silêncio: {cfg['silencio']['inicio']}h-{cfg['silencio']['fim']}h" if cfg.get("silencio") else "Silêncio: desligado",
        f"Última varredura: {st.get('last_run', 'nunca')} UTC · {ur.get('com_preco', 0)}/{ur.get('consultas', 0)} com preço",
        f"Janela pedida até {cfg['ate']}; vendas abertas até ~{max(hz.values()) if hz else '?'}",
    ]
    if top:
        linhas.append("Menores preços vistos:\n" + "\n".join(f"• {nome(d)}: R$ {p:,}".replace(",", ".") for d, p in top))
    return "\n".join(linhas)


TOPF = config.DATA / "top.json"


def top_text(n: int = 10) -> str:
    try:
        t = json.loads(TOPF.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "Ainda sem resultados. Mande /agora para varrer."
    rows = t.get("top", [])[:n]
    if not rows:
        return "Nenhuma combinação no período atual."
    from datetime import date as _d
    f = lambda x: f"R$ {int(x):,}".replace(",", ".")  # noqa: E731
    L = [f"🏆 Menores valores ({_d.fromisoformat(t['de']):%d/%m/%Y} → {_d.fromisoformat(t['ate']):%d/%m/%Y}), "
         f"{t['cobertos']}/{t['destinos']} destinos cobertos, bagagem: {t.get('bagagem', 'mao')}:"]
    for r in rows:
        a = _d.fromisoformat(r["dep"])
        b = _d.fromisoformat(r["ret"]) if r.get("ret") else None
        quando = f"{a:%d/%m}→{b:%d/%m}" if b else f"{a:%d/%m}"
        con = "direto" if r.get("stops", 0) == 0 else f"{r['stops']} conexão"
        L.append(f"• {nome(r['dest'])}: <b>{f(r['total'])}</b> · {quando} · {con} · {', '.join(r.get('air', []))}")
    L.append(f"Atualizado em {t['last_run']} UTC (Kiwi.com). /top 20 mostra mais.")
    return chr(10).join(L)


def dispatch_scan() -> str:
    repo, tok = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if repo and tok:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/scan.yml/dispatches",
                          headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                          json={"ref": "main", "inputs": {"force": "true"}}, timeout=20)
        ok = r.status_code in (201, 204)
    else:  # rodando no PC: usa o gh ja autenticado
        import subprocess
        try:
            ok = subprocess.run(["gh", "workflow", "run", "scan.yml", "-f", "force=true"], cwd=config.ROOT,
                                capture_output=True, timeout=60,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
        except Exception:  # noqa: BLE001
            ok = False
    return "🔎 Varredura disparada. Leva uns 5 minutos." if ok else "Não consegui disparar; rode a Action 'scan' manualmente."


def main() -> int:
    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("sem TELEGRAM_BOT_TOKEN")
        return 1
    cfg = config.load()
    try:
        off = json.loads(OFFSET.read_text())["offset"]
    except Exception:  # noqa: BLE001
        off = 0
    data = api("getUpdates", offset=off, timeout=0)
    cid_cfg = config.chat_id(cfg)
    changed = False
    for u in data.get("result", []):
        off = u["update_id"] + 1
        m = u.get("message") or {}
        text, chat = m.get("text", ""), str(m.get("chat", {}).get("id", ""))
        if not text or not chat:
            continue
        if not cid_cfg:  # pareamento: so o /start responde, mostrando o id
            if text.startswith("/start"):
                api("sendMessage", chat_id=chat, parse_mode="HTML",
                    text=f"Seu chat id é <code>{chat}</code>. Salve como Secret TELEGRAM_CHAT_ID no GitHub.")
            continue
        if chat != cid_cfg:
            continue
        cmd = text.split()[0].split("@")[0].lower()
        if cmd == "/start":
            reply = bot.AJUDA
        elif cmd == "/status":
            reply = status_text(cfg)
        elif cmd == "/ultimos":
            rec = store.load(STATE).get("recentes", [])[-8:]
            reply = "\n\n".join(r["txt"] for r in rec) or "Nenhum aviso ainda."
        elif cmd == "/top":
            nn = int(text.split()[1]) if len(text.split()) > 1 and text.split()[1].isdigit() else 10
            reply = top_text(min(nn, 25))
        elif cmd == "/agora":
            reply = dispatch_scan()
        else:
            new, reply = bot.apply(cfg, text)
            if new != cfg:
                cfg, changed = new, True
        api("sendMessage", chat_id=chat, text=reply, parse_mode="HTML", disable_web_page_preview="true")
    if changed:
        config.save(cfg)
    OFFSET.write_text(json.dumps({"offset": off}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
