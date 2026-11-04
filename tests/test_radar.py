import unittest
from datetime import date, datetime, timedelta

from radar import bot, config, dates, outlier, store
from radar.sources import kiwi, latam, smiles


class Outlier(unittest.TestCase):
    S = [2000, 2100, 1950, 2050, 2200, 1980, 2020, 2080]

    def test_flags_big_drop(self):
        self.assertTrue(outlier.judge(1347, self.S, 25).is_outlier)

    def test_ignores_normal(self):
        self.assertFalse(outlier.judge(1900, self.S, 25).is_outlier)

    def test_small_sample_never_alerts(self):
        self.assertFalse(outlier.judge(100, [2000, 2100], 25).is_outlier)

    def test_flat_sample_zero_mad(self):
        self.assertTrue(outlier.judge(1000, [2000] * 8, 25).is_outlier)


class Dates(unittest.TestCase):
    cfg = dict(config.DEFAULT, destinos=["SCL", "LIM"], ate="2027-12-31", passo_dias=3, duracoes=[7])

    def test_window_and_steps(self):
        c = dates.build_combos(self.cfg, date(2026, 11, 2), {})
        self.assertEqual(c[0][1], date(2026, 11, 9))
        self.assertTrue(all(x[1] <= date(2026, 11, 2) + timedelta(days=345) for x in c))

    def test_horizon_only_grows_when_calendar_opens(self):
        base = max(x[1] for x in dates.build_combos(self.cfg, date(2026, 11, 2), {}))
        same = max(x[1] for x in dates.build_combos(self.cfg, date(2026, 11, 2), {"SCL": "2027-01-03"}))
        self.assertEqual(base, same)  # amostragem parcial NAO encolhe a grade
        grown = max(x[1] for x in dates.build_combos(self.cfg, date(2026, 11, 2), {"SCL": "2027-11-05"}))
        self.assertGreater(grown, base)  # data alem do horizonte => grade se estende

    def test_cursor_rotates_and_wraps(self):
        a, cur = dates.pick(list(range(10)), 8, 4)
        self.assertEqual(a, [8, 9, 0, 1])
        self.assertEqual(cur, 2)


class Bot(unittest.TestCase):
    def setUp(self):
        self.cfg = config.load(config.DATA / "nao_existe.json")

    def test_add_remove(self):
        c, _ = bot.apply(self.cfg, "/add GYE ccs")
        self.assertIn("GYE", c["destinos"])
        self.assertIn("CCS", c["destinos"])
        c, _ = bot.apply(c, "/remover GYE")
        self.assertNotIn("GYE", c["destinos"])

    def test_silencio_and_off(self):
        c, _ = bot.apply(self.cfg, "/silencio 22 6")
        self.assertEqual(c["silencio"], {"inicio": 22, "fim": 6})
        c, _ = bot.apply(c, "/silencio off")
        self.assertIsNone(c["silencio"])

    def test_limits(self):
        c, _ = bot.apply(self.cfg, "/limite SCL 1100")
        self.assertEqual(c["limites"]["SCL"], 1100)
        c, _ = bot.apply(c, "/limite SCL off")
        self.assertNotIn("SCL", c["limites"])

    def test_bad_input_does_not_crash_or_change(self):
        for t in ["/intervalo abc", "/silencio 99 1", "/sensibilidade 3", "/ate 2027-13-45",
                  "/xyz", "oi", "/limite"]:
            c, _ = bot.apply(self.cfg, t)
            self.assertEqual(c, self.cfg, t)

    def test_bot_username_suffix(self):
        c, _ = bot.apply(self.cfg, "/pausar@meu_bot")
        self.assertFalse(c["ativo"])


class Regioes(unittest.TestCase):
    def setUp(self):
        self.cfg = config.load(config.DATA / "nao_existe.json")

    def test_replace_and_add(self):
        c, r = bot.apply(self.cfg, "/regiao europa")
        self.assertIn("LIS", c["destinos"])
        self.assertNotIn("SCL", c["destinos"])
        c, r = bot.apply(c, "/regiao+ asia")
        self.assertIn("NRT", c["destinos"])
        self.assertIn("LIS", c["destinos"])
        c, r = bot.apply(c, "/regiao america do sul")  # varias palavras = regiao invalida
        self.assertIn("nao encontrada" if False else "não encontrada", r)

    def test_alias_and_unknown(self):
        c, _ = bot.apply(self.cfg, "/regiao todos")
        self.assertGreater(len(c["destinos"]), 100)
        c2, r = bot.apply(self.cfg, "/regiao marte")
        self.assertEqual(c2, self.cfg)

    def test_escala_commands(self):
        c, _ = bot.apply(self.cfg, "/escala+ LIS GRU JFK")
        self.assertIn("JFK", c["escala_oculta"]["rotas"]["LIS"])
        c, _ = bot.apply(c, "/escala off")
        self.assertFalse(c["escala_oculta"]["ativo"])
        c, _ = bot.apply(c, "/escala- LIS")
        self.assertNotIn("LIS", c["escala_oculta"]["rotas"])


class EscalaGrid(unittest.TestCase):
    def test_grid_only_when_active(self):
        cfg = config.load(config.DATA / "nao_existe.json")
        self.assertTrue(dates.build_escala(cfg, date(2026, 11, 2)))
        cfg["escala_oculta"]["ativo"] = False
        self.assertEqual(dates.build_escala(cfg, date(2026, 11, 2)), [])


class Periodo(unittest.TestCase):
    T = date(2026, 11, 3)

    def cfg(self, **kw):
        return dict(config.DEFAULT, **kw)

    def test_parse_formats(self):
        self.assertEqual(config.parse_data("31/12/2026"), date(2026, 12, 31))
        self.assertEqual(config.parse_data("dez/2026", False), date(2026, 12, 1))
        self.assertEqual(config.parse_data("dez/2027", True), date(2027, 12, 31))
        self.assertEqual(config.parse_data("12/2027", True), date(2027, 12, 31))
        with self.assertRaises(ValueError):
            config.parse_data("abc")

    def test_command_short_window(self):
        c, r = bot.apply(config.load(config.DATA / "x.json"), "/periodo 31/12/2026 05/01/2027")
        self.assertEqual((c["de"], c["ate"]), ("2026-12-31", "2027-01-05"))
        self.assertIn("TODAS", r)

    def test_command_long_window_and_hoje(self):
        c, r = bot.apply(config.load(config.DATA / "x.json"), "/periodo hoje dez/2027")
        self.assertEqual((c["de"], c["ate"]), ("hoje", "2027-12-31"))
        c, r = bot.apply(c, "/periodo dez/2026 ate dez/2027")
        self.assertEqual((c["de"], c["ate"]), ("2026-12-01", "2027-12-31"))

    def test_command_bad_period(self):
        base = config.load(config.DATA / "x.json")
        for t in ["/periodo", "/periodo 05/01/2027 31/12/2026", "/periodo foo bar"]:
            c, _ = bot.apply(base, t)
            self.assertEqual(c, base, t)

    def test_kiwi_plan_short_and_long(self):
        p = kiwi.plan(self.cfg(de="2026-12-31", ate="2027-01-05"), self.T)
        self.assertTrue(p["short"])
        self.assertEqual((p["nmin"], p["nmax"]), (2, 5))
        a = kiwi.window_args(p)
        self.assertEqual((a["departureDate"], a["departureDateTo"]), ("31/12/2026", "03/01/2027"))
        self.assertEqual((a["returnDate"], a["returnDateTo"]), ("02/01/2027", "05/01/2027"))
        p = kiwi.plan(self.cfg(de="hoje", ate="2027-12-31"), self.T)
        self.assertFalse(p["short"])
        self.assertEqual((p["nmin"], p["nmax"]), (5, 10))

    def test_kiwi_plan_impossible(self):
        self.assertIsNone(kiwi.plan(self.cfg(de="2027-01-01", ate="2027-01-01", estadia_min=3), self.T))

    def test_bagagem_param(self):
        p = kiwi.plan(self.cfg(), self.T)
        self.assertEqual(kiwi.window_args(p, "despachada")["adults_hold_bags"], [1])
        self.assertNotIn("adults_hold_bags", kiwi.window_args(p, "mao"))

    def test_month_windows_rotate(self):
        p = kiwi.plan(self.cfg(de="2026-12-01", ate="2027-03-31"), self.T)
        w0 = kiwi.month_windows(p, 2, 0)
        w1 = kiwi.month_windows(p, 2, 1)
        self.assertEqual(len(w0), 2)
        self.assertNotEqual(w0[0]["ini"], w1[0]["ini"])

    def test_kiwi_rows_sorted_and_baggage(self):
        data = {"itineraries": [
            {"price": 1500, "bookingUrl": "u2", "baggage": {"checkedBag": 1},
             "outbound": {"from": "GRU", "to": "LIM", "departureTime": "2027-02-20T19:25:00", "stops": 0, "route": ["GRU", "LIM"],
                          "segments": [{"carrierName": "Sky Airline"}]},
             "inbound": {"departureTime": "2027-03-01T11:20:00", "stops": 0, "segments": [{"carrierName": "Sky Airline"}]}},
            {"price": 1402, "bookingUrl": "u1", "baggage": {"personalItem": 1},
             "outbound": {"from": "GRU", "to": "LIM", "departureTime": "2027-02-21T19:25:00", "stops": 0, "route": ["GRU", "LIM"],
                          "segments": [{"carrierName": "Sky Airline"}]},
             "inbound": {"departureTime": "2027-03-01T11:20:00", "stops": 0, "segments": []}}]}
        r = kiwi.rows(data)
        self.assertEqual([x["total"] for x in r], [1402.0, 1500.0])
        self.assertEqual(r[0]["dep"], "2027-02-21")
        self.assertEqual(r[0]["url"], "u1")


class Quiet(unittest.TestCase):
    def test_overnight(self):
        cfg = dict(config.DEFAULT, silencio={"inicio": 23, "fim": 7})

        def mk(h):
            return datetime(2026, 11, 2, h, tzinfo=config.BRT)
        self.assertTrue(config.in_quiet_hours(cfg, mk(23)))
        self.assertTrue(config.in_quiet_hours(cfg, mk(3)))
        self.assertFalse(config.in_quiet_hours(cfg, mk(7)))
        self.assertFalse(config.in_quiet_hours(cfg, mk(15)))


class Parsers(unittest.TestCase):
    def test_latam_text(self):
        t = "Por pessoa a partir de\n34.824 milhas\n+ BRL 68,61\n  e 36.518 milhas + BRL 99,34"
        self.assertIsNone(latam.best("sem milhas aqui"))
        t2 = "34.824 milhas + BRL 68,61  36.518 milhas + BRL 99,34"
        self.assertEqual(latam.best(t2)["milhas"], 34824)
        self.assertAlmostEqual(latam.best(t2)["taxas"], 68.61)

    def test_smiles_summary(self):
        payload = {"requestedFlightSegmentList": [{"flightList": [
            {"stops": 0, "fareList": [{"type": "SMILES", "miles": 47000, "money": 0},
                                      {"type": "SMILES_CLUB", "miles": 44000, "money": 0},
                                      {"type": "SMILES_MONEY_CLUB", "miles": 2200, "money": 880}]},
            {"stops": 1, "fareList": [{"type": "SMILES", "miles": 118000, "money": 0}]}]}]}
        r = smiles.summarize(payload)
        self.assertEqual(r["milhas_direto"], 47000)
        self.assertEqual(r["milhas_min"], 47000)
        self.assertEqual(r["milhas_mais_dinheiro"], (2200, 880))


class Store(unittest.TestCase):
    def test_dedup(self):
        st = {}
        self.assertTrue(store.should_alert(st, "k", 1000))
        self.assertFalse(store.should_alert(st, "k", 990))
        self.assertTrue(store.should_alert(st, "k", 900))


class MilhasAvalia(unittest.TestCase):
    MC = {"custo_milheiro": 16.0, "sensibilidade": 35, "limites_milhas": {}}

    def test_taxas_altas_derrubam_a_falsa_oferta(self):
        from radar import scan_miles
        # Medellin real: 69.285 milhas + R$ 909 de taxas vs R$ 2.087 em dinheiro => quase empate, NAO e oferta
        m = {"dest": "MDE", "milhas": 69285, "taxas": 909}
        self.assertEqual(scan_miles.evaluate(m, [], self.MC, 2087)[0], "")

    def test_oferta_real_passa(self):
        from radar import scan_miles
        m = {"dest": "FRA", "milhas": 100000, "taxas": 300}   # R$ 1.900 em milhas vs R$ 5.000 em dinheiro
        why, pct, _ = scan_miles.evaluate(m, [], self.MC, 5000)
        self.assertTrue(why)
        self.assertGreater(pct, 60)


class MilhasPadroes(unittest.TestCase):
    def test_combos_respeitam_filtros(self):
        from radar import scan_miles
        cfg = config.load(config.DATA / "x.json")
        mc = cfg["milhas"]
        c = scan_miles.montar_combos(cfg, mc, date(2026, 11, 3))
        self.assertTrue(c)
        self.assertFalse(any(d.weekday() == 5 for _, d, _ in c))                       # sem sabado
        self.assertFalse(any(scan_miles.em_pico(d, mc["evitar_pico"]) for _, d, _ in c))  # sem pico
        self.assertTrue(all(n in (14, 16, 21) for dest, _, n in c if dest == "FRA"))   # estadia tipica Europa

    def test_pico_virada_de_ano(self):
        from radar import scan_miles
        pk = [[12, 18, 1, 8]]
        self.assertTrue(scan_miles.em_pico(date(2026, 12, 31), pk))
        self.assertTrue(scan_miles.em_pico(date(2027, 1, 5), pk))
        self.assertFalse(scan_miles.em_pico(date(2027, 3, 10), pk))

    def test_regiao_nordeste(self):
        c, r = bot.apply(config.load(config.DATA / "x.json"), "/milhasdestinos nordeste FRA AUA")
        self.assertEqual(c["milhas"]["destinos"][:2], ["SSA", "REC"])
        self.assertIn("AUA", c["milhas"]["destinos"])


if __name__ == "__main__":
    unittest.main()
