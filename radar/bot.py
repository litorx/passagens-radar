"""Comandos do celular (Telegram). `apply()` e funcao pura (testavel): (config, texto) -> (config, resposta)."""
from __future__ import annotations

import copy
import re
from datetime import datetime

from .airports import nome

AJUDA = """<b>Radar de passagens</b> — comandos:
/status — como está tudo
/ultimos — últimos avisos
/agora — rodar uma varredura agora
/pausar · /retomar

<b>Destinos e origens</b>
/destinos — lista atual
/add SCL LIM — adiciona destinos
/remover SCL — remove
/origens GRU CGH VCP

<b>Quando e quanto</b>
/intervalo 2 — varre a cada 2 h
/silencio 23 7 — sem avisos das 23h às 7h · /silencio off
/sensibilidade 30 — avisa se ≥30% abaixo do normal
/limite SCL 1100 — avisa se ≤ R$ 1.100 · /limite SCL off
/ate 2027-12-31 — data final desejada
/duracoes 5 7 10 — dias de viagem testados
/passo 3 — testa 1 data a cada 3 dias

<b>Milhas (no seu PC)</b>
/milhas on|off
/milheiro 16 — quanto você paga por 1.000 milhas
/limitemilhas SCL 90000 — avisa se ida e volta ≤ 90.000 milhas"""

IATA = re.compile(r"^[A-Za-z]{3}$")


def _codes(args):
    return [a.upper() for a in args if IATA.match(a)]


def apply(cfg: dict, text: str) -> tuple[dict, str]:
    cfg = copy.deepcopy(cfg)
    t = (text or "").strip()
    if not t.startswith("/"):
        return cfg, "Mande /ajuda para ver os comandos."
    parts = t.split()
    cmd = parts[0].split("@")[0].lower()
    a = parts[1:]

    try:
        if cmd in ("/ajuda", "/help"):
            return cfg, AJUDA
        if cmd == "/pausar":
            cfg["ativo"] = False
            return cfg, "⏸️ Radar pausado. /retomar para ligar."
        if cmd == "/retomar":
            cfg["ativo"] = True
            return cfg, "▶️ Radar ligado."
        if cmd == "/destinos":
            return cfg, "Destinos: " + ", ".join(f"{d} ({nome(d)})" for d in cfg["destinos"])
        if cmd == "/add":
            c = _codes(a)
            if not c:
                return cfg, "Use: /add SCL LIM"
            for d in c:
                if d not in cfg["destinos"]:
                    cfg["destinos"].append(d)
            return cfg, f"✅ Destinos agora: {len(cfg['destinos'])}. Adicionados: {', '.join(c)}"
        if cmd in ("/remover", "/del", "/delete"):
            c = _codes(a)
            cfg["destinos"] = [d for d in cfg["destinos"] if d not in c]
            return cfg, f"🗑️ Removidos: {', '.join(c) or 'nenhum'}. Restam {len(cfg['destinos'])}."
        if cmd == "/origens":
            c = _codes(a)
            if not c:
                return cfg, "Use: /origens GRU CGH VCP"
            cfg["origens"] = c
            return cfg, f"✅ Origens: {', '.join(c)}"
        if cmd == "/intervalo":
            h = float(a[0].replace(",", "."))
            if not 0.5 <= h <= 48:
                return cfg, "Escolha entre 0,5 e 48 horas."
            cfg["intervalo_horas"] = h
            return cfg, f"✅ Varredura a cada {h:g} h (o relógio do GitHub tem precisão de ~1 h)."
        if cmd == "/silencio":
            if a and a[0].lower() in ("off", "nao", "não"):
                cfg["silencio"] = None
                return cfg, "🔔 Sem horário de silêncio."
            i, f = int(a[0]), int(a[1])
            if not (0 <= i <= 23 and 0 <= f <= 23):
                return cfg, "Horas de 0 a 23."
            cfg["silencio"] = {"inicio": i, "fim": f}
            return cfg, f"🌙 Silêncio das {i}h às {f}h (Brasília). Avisos ficam guardados e saem depois."
        if cmd == "/sensibilidade":
            p = float(a[0])
            if not 5 <= p <= 80:
                return cfg, "Escolha entre 5 e 80 (%)."
            cfg["sensibilidade"] = p
            return cfg, f"✅ Avisa quando estiver ≥ {p:g}% abaixo do normal."
        if cmd == "/limite":
            d = a[0].upper()
            if a[1].lower() == "off":
                cfg["limites"].pop(d, None)
                return cfg, f"✅ Limite de {d} removido."
            cfg["limites"][d] = int(a[1])
            return cfg, f"✅ Aviso para {nome(d)} se ≤ R$ {int(a[1]):,}".replace(",", ".")
        if cmd == "/ate":
            datetime.strptime(a[0], "%Y-%m-%d")
            cfg["ate"] = a[0]
            return cfg, (f"✅ Janela até {a[0]}. As companhias só vendem ~11 meses à frente; "
                         "o radar descobre o limite sozinho e avisa quando novas datas abrem.")
        if cmd == "/duracoes":
            ds = [int(x) for x in a if x.isdigit() and 1 <= int(x) <= 60]
            if not ds:
                return cfg, "Use: /duracoes 5 7 10"
            cfg["duracoes"] = ds
            return cfg, f"✅ Durações: {ds} dias"
        if cmd == "/passo":
            n = int(a[0])
            if not 1 <= n <= 14:
                return cfg, "Escolha de 1 a 14 dias."
            cfg["passo_dias"] = n
            return cfg, f"✅ Testa 1 data a cada {n} dias."
        if cmd == "/milhas":
            cfg["milhas"]["ativo"] = a[0].lower() in ("on", "sim", "1")
            return cfg, f"✅ Milhas: {'ligado' if cfg['milhas']['ativo'] else 'desligado'}"
        if cmd == "/milheiro":
            cfg["milhas"]["custo_milheiro"] = float(a[0].replace(",", "."))
            return cfg, f"✅ Custo do milheiro: R$ {cfg['milhas']['custo_milheiro']:g}"
        if cmd == "/limitemilhas":
            d = a[0].upper()
            if a[1].lower() == "off":
                cfg["milhas"]["limites_milhas"].pop(d, None)
                return cfg, f"✅ Limite de milhas de {d} removido."
            cfg["milhas"]["limites_milhas"][d] = int(a[1])
            return cfg, f"✅ Milhas: aviso para {nome(d)} se ≤ {int(a[1]):,} milhas".replace(",", ".")
    except (IndexError, ValueError):
        return cfg, f"Não entendi. Exemplo: veja /ajuda ({cmd})"
    return cfg, "Comando desconhecido. /ajuda"
