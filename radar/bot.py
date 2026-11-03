"""Comandos do celular (Telegram). `apply()` e funcao pura (testavel): (config, texto) -> (config, resposta)."""
from __future__ import annotations

import copy
import re
from datetime import datetime

from . import config
from .airports import REGIOES, nome, regiao

AJUDA = """<b>Radar de passagens</b> — comandos:
/top — os menores valores encontrados agora (no período)
/periodo 31/12/2026 05/01/2027 — só essa janela (testa TODAS as combinações de ida e volta)
/periodo dez/2026 dez/2027 — janela longa · /periodo hoje dez/2027
/status — como está tudo
/ultimos — últimos avisos
/agora — varrer agora (leva uns minutos)
/pausar · /retomar

<b>Destinos e origens</b>
/regioes — regiões prontas (brasil, america_do_sul, america_central,
   america_norte, europa, asia, africa, oceania, mundo)
/regiao europa — troca TODOS os destinos pela região (aceita várias: /regiao europa asia)
/regiao+ asia — acrescenta uma região
/destinos — lista atual
/add SCL LIM — adiciona destinos
/remover SCL — remove
/origens GRU CGH VCP

<b>Quando e quanto</b>
/intervalo 2 — varre a cada 2 h
/silencio 23 7 — sem avisos das 23h às 7h · /silencio off
/sensibilidade 30 — avisa se ≥30% abaixo do normal
/bagagem mao|despachada — preços só com item pessoal ou já com 1 mala
/autotransferencia on|off — aceitar bilhetes separados combinados (mais barato, mais risco)
/limite SCL 1100 — avisa se ≤ R$ 1.100 · /limite SCL off
/ate 2027-12-31 — data final desejada
/duracoes 5 7 10 — dias de viagem testados (janela longa) · também 3-10
/passo 3 — testa 1 data a cada 3 dias

<b>Escala oculta (zona cinza)</b>
/escala on|off — procura passagem para lugar MAIS LONGE com conexão num hub, mais barata que ir ao hub
/escala+ SCL SYD AKL — hub SCL, destinos além: SYD e AKL · /escala- SCL — remove o hub
/economiaescala 20 — só avisa se ≥ 20% mais barata

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
        if cmd == "/periodo":
            toks = [x for x in a if x.lower() not in ("ate", "até", "a", "-", "ao")]
            if len(toks) != 2:
                return cfg, "Use: /periodo 31/12/2026 05/01/2027 · /periodo dez/2026 dez/2027 · /periodo hoje dez/2027"
            d0 = config.parse_data(toks[0], False)
            d1 = config.parse_data(toks[1], True)
            if d1 < d0:
                return cfg, "A data final é antes da inicial."
            cfg["de"] = "hoje" if toks[0].lower() in ("hoje", "agora") else d0.isoformat()
            cfg["ate"] = d1.isoformat()
            dias = (d1 - d0).days
            modo = ("Janela curta: testo TODAS as combinações de ida e volta dentro dela."
                    if dias <= 21 else f"Janela longa: testo viagens de {cfg['duracoes']} dias (/duracoes muda).")
            return cfg, f"📅 Período: {d0:%d/%m/%Y} → {d1:%d/%m/%Y} ({dias} dias). {modo}"
        if cmd == "/autotransferencia":
            on = a[0].lower() in ("on", "sim", "1")
            cfg["autotransferencia"] = on
            return cfg, ("⚠️ Aceita bilhetes SEPARADOS combinados (mais barato, mas se o 1º voo atrasar a 2ª companhia "
                         "não te realoca)." if on else "🛡️ Só itinerários em um bilhete único (sem autotransferência).")
        if cmd == "/bagagem":
            v = a[0].lower()
            if v not in ("mao", "mão", "despachada"):
                return cfg, "Use: /bagagem mao  ou  /bagagem despachada"
            cfg["bagagem"] = "despachada" if v == "despachada" else "mao"
            return cfg, ("🧳 Preços já com 1 mala despachada." if cfg["bagagem"] == "despachada"
                         else "🎒 Preços só com item pessoal (mais baixos; mala é cobrada à parte).")
        if cmd == "/regioes":
            return cfg, "Regiões: " + ", ".join(f"{k} ({len(v)})" for k, v in REGIOES.items())
        if cmd in ("/regiao", "/regiao+"):
            nomes = [regiao(x) for x in a]
            if not a or None in nomes:
                bad = [x for x, n in zip(a, nomes) if n is None]
                return cfg, f"Região não encontrada: {', '.join(bad) or '?'}. Veja /regioes"
            novos = [c for n in nomes for c in REGIOES[n]]
            if cmd == "/regiao":
                cfg["destinos"] = list(dict.fromkeys(novos))
                cfg["regiao"] = "+".join(nomes)
            else:
                cfg["destinos"] = list(dict.fromkeys(cfg["destinos"] + novos))
                cfg["regiao"] = "+".join(dict.fromkeys(cfg.get("regiao", "").split("+") + nomes)).strip("+")
            return cfg, (f"🌍 Destinos: {len(cfg['destinos'])} ({cfg['regiao']}). Regiões grandes demoram mais para "
                         "completar a volta; use /passo 5 ou /duracoes 7 para acelerar.")
        if cmd == "/escala":
            if a and a[0].lower() in ("on", "off"):
                cfg["escala_oculta"]["ativo"] = a[0].lower() == "on"
                return cfg, f"✅ Escala oculta: {'ligada' if cfg['escala_oculta']['ativo'] else 'desligada'}"
            r = cfg["escala_oculta"]["rotas"]
            return cfg, ("Escala oculta " + ("ligada" if cfg["escala_oculta"]["ativo"] else "desligada")
                         + ":\n" + "\n".join(f"{h} → {', '.join(v) or '-'}" for h, v in r.items()))
        if cmd == "/escala+":
            hub, alems = a[0].upper(), _codes(a[1:])
            if not alems:
                return cfg, "Use: /escala+ SCL SYD AKL"
            cur = cfg["escala_oculta"]["rotas"].setdefault(hub, [])
            cfg["escala_oculta"]["rotas"][hub] = list(dict.fromkeys(cur + alems))
            return cfg, f"✅ Hub {hub} → {', '.join(cfg['escala_oculta']['rotas'][hub])}"
        if cmd == "/escala-":
            cfg["escala_oculta"]["rotas"].pop(a[0].upper(), None)
            return cfg, f"🗑️ Hub {a[0].upper()} removido."
        if cmd == "/economiaescala":
            p = float(a[0])
            if not 5 <= p <= 80:
                return cfg, "Escolha entre 5 e 80 (%)."
            cfg["escala_oculta"]["min_economia_pct"] = p
            return cfg, f"✅ Escala oculta só avisa se ≥ {p:g}% mais barata."
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
            ds = []
            for x in a:
                if "-" in x:
                    lo, hi = x.split("-", 1)
                    ds += [n for n in range(int(lo), int(hi) + 1) if 1 <= n <= 60]
                elif x.isdigit() and 1 <= int(x) <= 60:
                    ds.append(int(x))
            ds = sorted(set(ds))
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
