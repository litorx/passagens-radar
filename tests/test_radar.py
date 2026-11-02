import unittest
from datetime import date, datetime

from radar import bot, config, dates, outlier, store
from radar.sources import latam, smiles


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
        self.assertTrue(all(x[1] <= date(2027, 10, 28) for x in c))  # teto de 360 dias

    def test_horizon_limits_probe(self):
        c = dates.build_combos(self.cfg, date(2026, 11, 2), {"SCL": "2027-09-20"})
        scl = [x for x in c if x[0] == "SCL"]
        self.assertLessEqual(max(x[1] for x in scl), date(2027, 9, 26))

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


if __name__ == "__main__":
    unittest.main()
