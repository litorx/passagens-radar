"""Configuracao (data/config.json). Tudo aqui pode ser mudado pelo celular via bot."""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOCAL = ROOT / "data_local"          # so no seu PC (milhas); ignorado pelo git
BRT = timezone(timedelta(hours=-3))  # Brasil nao tem horario de verao

DEFAULT = {
    "ativo": True,
    "origens": ["GRU", "CGH", "VCP"],
    "destinos": ["SCL", "EZE", "AEP", "MVD", "LIM", "ASU", "COR", "MDZ", "BOG", "MDE",
                 "CTG", "UIO", "CUZ", "LPB", "VVI", "PTY", "BRC", "USH", "FTE", "PUQ"],
    "de": "hoje",                   # inicio do periodo ("hoje" ou data)
    "ate": "2027-12-31",            # fim do periodo (o radar ve ate onde as cias vendem)
    "estadia_min": 2,               # minimo de dias de viagem (janelas curtas testam TODAS as combinacoes)
    "antecedencia_min_dias": 7,     # so vale quando "de" = "hoje"
    "destinos_por_rodada": 20,
    "bagagem": "mao",               # mao (so item pessoal) | despachada (preco ja com 1 mala)
    "autotransferencia": False,     # True = aceita bilhetes SEPARADOS combinados (mais barato, risco de perder conexao)
    "amostra_meses": 3,             # meses sorteados por destino p/ medir o normal do periodo
    "passo_dias": 3,                # testa 1 data a cada N dias
    "duracoes": [5, 7, 10],
    "intervalo_horas": 3,           # de quanto em quanto tempo o radar de dinheiro roda
    "pares_por_rodada": 60,
    "silencio": {"inicio": 23, "fim": 7},   # sem avisos entre 23h e 7h (horario de Brasilia); null = desliga
    "sensibilidade": 35,            # % abaixo do normal para avisar (so ofertas MUITO boas)
    "limites": {},                  # ex.: {"SCL": 1100}  (aviso se <= valor, em R$)
    "milhas": {"ativo": True, "custo_milheiro": 16.0, "limites_milhas": {}, "sensibilidade": 35, "exigencia": 1.5, "latam": True,
               "buscas_por_rodada": 16, "descanso_horas": 3,
               "passo_dias": 10, "duracoes": [7]},
    "regiao": "america_do_sul",
    # Escala "oculta": passagem ate um destino MAIS LONGE com conexao no hub, mais barata que ir ao hub.
    # Zona cinza: viola o contrato da companhia (so ida, so bagagem de mao). Desligue com /escala off.
    "escala_oculta": {
        "ativo": True, "min_economia_pct": 20, "por_rodada": 6,
        "rotas": {"SCL": ["SYD", "AKL"], "LIM": ["CUZ", "MIA"], "BOG": ["CUN", "MEX", "MIA"],
                  "PTY": ["MIA", "MEX", "SJO", "CUN"], "EZE": ["MAD", "FCO", "MIA"],
                  "MVD": ["MAD"], "GRU": []},
    },
    "resumo_diario": False,         # True = 1 mensagem por dia com os menores valores (padrao: so ofertas realmente boas)
    "bot": {"chat_id": ""},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: Path | None = None) -> dict:
    path = path or DATA / "config.json"
    try:
        user = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        user = {}
    return _merge(DEFAULT, user)


def save(cfg: dict, path: Path | None = None) -> None:
    path = path or DATA / "config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def load_env() -> None:
    """Carrega segredos locais (data_local/.env ou .env.local) para o PC; ignorados pelo git."""
    for f in (LOCAL / ".env", ROOT / ".env.local"):
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))
        except FileNotFoundError:
            pass


_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9,
          "out": 10, "nov": 11, "dez": 12}


def parse_data(txt: str, fim: bool = False, today=None):
    """'hoje', 2026-12-31, 31/12/2026, 12/2026, dez/2026, dez2026 -> date (mes sozinho: 1o ou ultimo dia)."""
    import calendar
    import re
    from datetime import date
    t = (txt or "").strip().lower()
    today = today or date.today()
    if t in ("hoje", "agora"):
        return today
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    mo = ye = None
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", t)
    if m:
        mo, ye = int(m[1]), int(m[2])
    m = re.fullmatch(r"([a-zç]{3})[a-z]*[/\- ]?(\d{4})", t)
    if m and m[1] in _MESES:
        mo, ye = _MESES[m[1]], int(m[2])
    if mo and 1 <= mo <= 12:
        return date(ye, mo, calendar.monthrange(ye, mo)[1] if fim else 1)
    raise ValueError(f"data invalida: {txt}")


def janela(cfg: dict, today=None):
    """(inicio, fim) do periodo. 'hoje' respeita a antecedencia minima; data explicita vale como esta."""
    from datetime import date, timedelta
    today = today or date.today()
    de_txt = str(cfg.get("de", "hoje"))
    if de_txt.strip().lower() in ("hoje", "agora", ""):
        ini = today + timedelta(days=int(cfg.get("antecedencia_min_dias", 7)))
    else:
        ini = max(parse_data(de_txt, False, today), today + timedelta(days=1))
    fim = parse_data(str(cfg["ate"]), True, today)
    return ini, fim


def now_brt() -> datetime:
    return datetime.now(BRT)


def in_quiet_hours(cfg: dict, now: datetime | None = None) -> bool:
    s = cfg.get("silencio")
    if not s:
        return False
    h = (now or now_brt()).hour
    a, b = int(s["inicio"]), int(s["fim"])
    return (a <= h or h < b) if a > b else (a <= h < b)


def chat_id(cfg: dict) -> str:
    return os.environ.get("TELEGRAM_CHAT_ID") or str(cfg.get("bot", {}).get("chat_id") or "")
