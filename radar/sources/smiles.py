"""Smiles (GOL) em milhas, via Chrome REAL + Playwright, so no seu PC.

Por que assim (verificado em 02/11/2026):
  - A API direta (api-air-flightsearch-prd.smiles.com.br) devolve HTTP 406 ate do IP residencial.
  - O projeto aberto 'GAHLicita/Buscador-de-passagens' avisa que a Smiles bloqueia o GitHub Actions.
  - Chrome real + janela VISIVEL (jogada para fora da tela) funciona; modo headless e bloqueado.
A janela abre fora da tela (-32000,-32000), nao atrapalha seu uso do PC.

Aviso: usa o mesmo endpoint que o site chama; leitura de precos publicos, em baixo volume.
Pode quebrar se a Smiles mudar o site. Respeite os termos do site; nao aumente a frequencia.
"""
from __future__ import annotations

import json
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone

SITE = "https://www.smiles.com.br/mfe/emissao-passagem/"


def _url(origin: str, dest: str, day: date) -> str:
    noon = datetime(day.year, day.month, day.day, 12, tzinfo=timezone(timedelta(hours=-3)))
    p = {"adults": 1, "cabin": "ALL", "children": 0, "departureDate": int(noon.timestamp() * 1000),
         "infants": 0, "isElegible": "false", "isFlexibleDateChecked": "false", "returnDate": "",
         "searchType": "congenere", "segments": 1, "tripType": 2, "originAirport": origin,
         "originAirportIsAny": "false", "destinationAirport": dest, "destinAirportIsAny": "false",
         "novo-resultado-voos": "true"}
    return SITE + "?" + urllib.parse.urlencode(p)


def summarize(payload: dict) -> dict:
    """Do JSON da Smiles: menor milhas (qualquer), menor direto, e menor 'milhas+dinheiro'."""
    flights = []
    for seg in payload.get("requestedFlightSegmentList", []):
        flights += seg.get("flightList", [])
    best_any = best_direct = None
    mm = None  # (milhas, dinheiro R$)
    for f in flights:
        stops = f.get("stops", 9)
        for fare in f.get("fareList", []):
            t, miles, money = fare.get("type"), fare.get("miles"), fare.get("money") or 0
            if not miles:
                continue
            if t == "SMILES":  # tarifa de qualquer cliente (sem clube)
                best_any = miles if best_any is None else min(best_any, miles)
                if stops == 0:
                    best_direct = miles if best_direct is None else min(best_direct, miles)
            if t == "SMILES_MONEY_CLUB" and money:
                if mm is None or (miles + money * 60) < (mm[0] + mm[1] * 60):  # 1 R$ ~ 60 milhas (so p/ ordenar)
                    mm = (miles, money)
    return {"n_voos": len(flights), "milhas_min": best_any, "milhas_direto": best_direct,
            "milhas_mais_dinheiro": mm}


class Smiles:
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._b = self._pw.chromium.launch(
            channel="chrome", headless=False,
            args=["--disable-blink-features=AutomationControlled", "--window-position=-32000,-32000"])
        ctx = self._b.new_context(locale="pt-BR", timezone_id="America/Sao_Paulo",
                                  viewport={"width": 1366, "height": 850})
        self._page = ctx.new_page()
        self._page.goto("https://www.smiles.com.br/home", wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(3000)
        return self

    def __exit__(self, *a):
        try:
            self._b.close()
            self._pw.stop()
        except Exception:  # noqa: BLE001
            pass

    def search(self, origin: str, dest: str, day: date) -> dict | None:
        """Uma busca so-ida. Retorna resumo ou None (sem voos/erro)."""
        def match(r):
            return ("/v1/airlines/search" in r.url and f"originAirportCode={origin}" in r.url
                    and f"destinationAirportCode={dest}" in r.url)
        try:
            with self._page.expect_response(match, timeout=70000) as info:
                self._page.goto(_url(origin, dest, day), wait_until="domcontentloaded", timeout=60000)
            r = info.value
            if r.status != 200:
                return None
            return summarize(r.json())
        except Exception:  # noqa: BLE001
            return None
        finally:
            time.sleep(1.5)
