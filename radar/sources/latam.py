"""LATAM Pass (milhas + dinheiro) via Chrome com PERFIL PERSISTENTE (voce faz login uma vez).

Status: EXPERIMENTAL. A extracao de texto ("34.824 milhas + BRL 68,61") foi validada ao vivo em
02/11/2026 numa sessao logada; o loop automatico com perfil persistente ainda nao foi exercitado.

Primeiro uso (uma vez):  python -m radar.sources.latam --login
  -> abre o Chrome, voce entra na sua conta LATAM Pass, fecha a janela. O login fica salvo em
     data_local/latam_profile (so no seu PC; nunca vai para o GitHub).
"""
from __future__ import annotations

import re
import sys
import time
from datetime import date

from ..config import LOCAL

PROFILE = LOCAL / "latam_profile"
RX = re.compile(r"([\d\.]+)\s*milhas\s*\+\s*BRL\s*([\d\.,]+)")


def parse_offers(text: str) -> list[tuple[int, float]]:
    out = []
    for m in RX.finditer(text):
        miles = int(m.group(1).replace(".", ""))
        money = float(m.group(2).replace(".", "").replace(",", "."))
        out.append((miles, money))
    return out


def best(text: str) -> dict | None:
    offers = parse_offers(text)
    if not offers:
        return None
    mn = min(offers)  # menor milhas, desempate pelo menor dinheiro
    return {"milhas": mn[0], "taxas": mn[1], "n": len(offers)}


def url(origin: str, dest: str, day: date) -> str:
    return ("https://www.latamairlines.com/br/pt/oferta-voos?origin=%s&outbound=%sT00%%3A00%%3A00.000Z"
            "&destination=%s&adt=1&chd=0&inf=0&trip=OW&cabin=Economy&redemption=true&sort=RECOMMENDED"
            % (origin, day.isoformat(), dest))


class Latam:
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        PROFILE.mkdir(parents=True, exist_ok=True)
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            str(PROFILE), channel="chrome", headless=False, locale="pt-BR",
            args=["--disable-blink-features=AutomationControlled", "--window-position=-32000,-32000"])
        self._page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        return self

    def __exit__(self, *a):
        try:
            self._ctx.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001
            pass

    def search(self, origin: str, dest: str, day: date) -> dict | None:
        try:
            self._page.goto(url(origin, dest, day), wait_until="domcontentloaded", timeout=60000)
            for _ in range(12):  # espera a lista de voos renderizar
                self._page.wait_for_timeout(2500)
                txt = self._page.inner_text("body")
                if "milhas" in txt and RX.search(txt):
                    return best(txt)
            return None
        except Exception:  # noqa: BLE001
            return None
        finally:
            time.sleep(2)


def login_flow() -> None:
    from playwright.sync_api import sync_playwright
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=False,
                                                   locale="pt-BR")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.latamairlines.com/br/pt")
        print("Entre na sua conta LATAM Pass na janela aberta e depois FECHE a janela.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:  # noqa: BLE001
            pass
        ctx.close()


if __name__ == "__main__":
    if "--login" in sys.argv:
        login_flow()
    else:
        print(__doc__)
