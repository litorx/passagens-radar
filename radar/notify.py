"""Envio de avisos: Telegram (principal) e ntfy (opcional)."""
from __future__ import annotations

import os
import sys

import requests


def _token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


def tg_send(text: str, chat_id: str, dry: bool = False) -> bool:
    print(f"[telegram -> {chat_id or '?'}] {text[:400]}")
    if dry or not chat_id or not _token():
        return False
    ok = True
    for i in range(0, len(text), 3800):  # limite do Telegram: 4096
        r = requests.post(
            f"https://api.telegram.org/bot{_token()}/sendMessage",
            data={"chat_id": chat_id, "text": text[i:i + 3800], "parse_mode": "HTML",
                  "disable_web_page_preview": "true"},
            timeout=25,
        )
        if r.status_code != 200:
            print("telegram erro", r.status_code, r.text[:200], file=sys.stderr)
            ok = False
    return ok


def ntfy_send(title: str, text: str, url: str = "", dry: bool = False) -> None:
    topic = os.environ.get("NTFY_TOPIC")
    if dry or not topic:
        return
    h = {"Title": title.encode("ascii", "ignore").decode(), "Priority": "high", "Tags": "airplane"}
    if url:
        h["Click"] = url
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=text.encode(), headers=h, timeout=20)
    except requests.RequestException as e:
        print("ntfy erro", e, file=sys.stderr)


def alert(text: str, chat_id: str, title: str = "Passagem fora da curva", url: str = "",
          dry: bool = False) -> None:
    tg_send(text, chat_id, dry)
    ntfy_send(title, text, url, dry)


def skyscanner_url(origin: str, dest: str, dep, ret) -> str:
    f = lambda d: d.strftime("%y%m%d")  # noqa: E731
    return (f"https://www.skyscanner.com.br/transporte/passagens-aereas/{origin.lower()}/"
            f"{dest.lower()}/{f(dep)}/{f(ret)}/?adultsv2=1&cabinclass=economy&rtn=1")


def google_url(origin: str, dest: str, dep, ret) -> str:
    return ("https://www.google.com/travel/flights?hl=pt-BR&gl=BR&curr=BRL&q="
            f"Voos de {origin} para {dest} em {dep:%Y-%m-%d} até {ret:%Y-%m-%d}").replace(" ", "%20")
