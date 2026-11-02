"""Preco em dinheiro (ida+volta) via Google Flights (biblioteca fast-flights, sem chave).

Limites medidos em 02/11/2026: nao lista low-cost (Sky, JetSMART, Flybondi) e o preco pode
diferir do site. Por isso o radar compara a fonte COM ELA MESMA (queda relativa) e o aviso
traz link do Skyscanner para voce conferir.
"""
from __future__ import annotations

import random
import time
from datetime import date

from fast_flights import FlightQuery, FlightsNotFound, Passengers, create_query, get_flights


class Result:
    __slots__ = ("price", "airlines", "found")

    def __init__(self, price=None, airlines=None, found=True):
        self.price, self.airlines, self.found = price, airlines or [], found


def fetch(origin: str, dest: str, dep: date, ret: date, retries: int = 2) -> Result:
    """Retorna Result(found=False) se nao ha voos (data nao aberta); levanta erro se a fonte falhou."""
    q = create_query(
        flights=[FlightQuery(date=dep.isoformat(), from_airport=origin, to_airport=dest),
                 FlightQuery(date=ret.isoformat(), from_airport=dest, to_airport=origin)],
        trip="round-trip", seat="economy", passengers=Passengers(adults=1),
        language="pt-BR", currency="BRL")
    last = None
    for _ in range(retries):
        try:
            res = [r for r in get_flights(q) if getattr(r, "price", 0)]
            if not res:
                return Result(found=False)
            best = min(res, key=lambda r: r.price)
            return Result(int(best.price), list(best.airlines))
        except FlightsNotFound:
            return Result(found=False)
        except (IndexError, TypeError, KeyError) as e:
            # Google devolve pagina sem lista (rota sem voo naquele dia, ex.: VCP-SCL). Tratado como
            # "sem voo"; se TUDO virar isso, o scan avisa que a fonte quebrou.
            last = e
            time.sleep(random.uniform(1, 3))
        except Exception as e:  # noqa: BLE001  (rede/bloqueio)
            last = e
            time.sleep(random.uniform(2, 5))
    if isinstance(last, (IndexError, TypeError, KeyError)):
        return Result(found=False)
    raise RuntimeError(f"fonte falhou: {type(last).__name__}")
