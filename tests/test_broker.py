import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from _load import load, ROOT, FIX

ticket = load("trader-broker", "ticket")
check = load("trader-risk", "check")

CFG_PATH = os.path.join(ROOT, "trader-budget", "config.example.json")
ORDERS_PATH = os.path.join(FIX, "trader-risk", "orders-tsla.json")
PLAN_PATH = os.path.join(FIX, "trader-budget", "plan-tsla.json")
SYM = "TATAPOWER.NS"      # the fixture's prices are made up; only the NSE-style symbol matters here
NOW = "2026-10-19 10:00"
TODAY = "2026-10-19"
AAPL = {"symbol": "AAPL", "side": "buy", "notional": "1250", "type": "market", "time_in_force": "day"}
BATCH = ["AAPL", "AXP", "GOOGL", "KO", "BAC"]
TSLA_CALL = {"symbol": "TATAPOWER.NS", "side": "buy", "qty": "8", "type": "market", "time_in_force": "day",
             "order_class": "bracket", "take_profit_limit_price": "370.04", "stop_loss_stop_price": "358.32"}
TSLA_PLAIN = ("BUY 8 TATAPOWER.NS, market, good for today / stop-loss 358.32 / take-profit 370.04 / max loss about "
              "₹46.88 if the stop fills at 358.32 (it can fill worse in a fast market)")


def tsla(**over):
    with open(ORDERS_PATH) as fh:
        o = json.load(fh)["orders"][0]
    o["symbol"] = SYM
    o.update(over)
    return o


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = ticket.main(argv)
    return code, out.getvalue(), err.getvalue()


class ExplicitYes(unittest.TestCase):
    def yes(self, reply, order=AAPL, batch=BATCH):
        return ticket.parse_yes(reply, order, batch)[0]

    def test_plain_yes_counts(self):
        for r in ("yes", "Yes.", "YES", "y", "yes place it", "Yes, buy it", "yes AAPL", "yes ₹1,250 of AAPL",
                  "yes 1250"):
            self.assertTrue(self.yes(r), r)

    def test_anything_else_does_not(self):
        for r in ("", "sure", "ok", "okay", "go", "do it", "yeah", "yep", "absolutely", "send it",
                  "yes to all", "yes, all of them", "yes to the rest", "yes both",
                  "yes AXP", "yes 1000", "yes but make it 1000", "yes?", "no", "not yes",
                  "yes, wait", "yes if it is under 340"):
            self.assertFalse(self.yes(r), r)

    def test_amount_must_match_this_order(self):
        sell = {"symbol": "KO", "side": "sell", "qty": "3", "type": "market", "time_in_force": "day"}
        self.assertTrue(self.yes("yes sell 3 KO", sell))
        self.assertFalse(self.yes("yes sell 4", sell))

    def test_a_bracket_yes(self):
        o = tsla()
        for r in ("yes", "yes 8 TATAPOWER.NS", "yes 358.32", "yes max loss 46.88", "yes target 370.04"):
            self.assertTrue(self.yes(r, o, ["TATAPOWER.NS"]), r)
        for r in ("yes 9", "yes 10 TATAPOWER.NS", "yes but stop at 357", "yes, stop 358.32", "yes AAPL", "sure"):
            self.assertFalse(self.yes(r, o, ["TATAPOWER.NS", "AAPL"]), r)


class TicketShape(unittest.TestCase):
    def test_a_bracket_is_an_intraday_entry_then_an_oco(self):
        calls = ticket.groww_calls(tsla())
        self.assertEqual([c["method"] for c in calls], ["place_order", "create_smart_order"])
        entry = dict(calls[0]["args"])
        ref = entry.pop("order_reference_id")
        self.assertEqual(entry, {"trading_symbol": "TATAPOWER", "quantity": 8, "validity": "DAY", "exchange": "NSE",
                                 "segment": "CASH", "product": "MIS", "order_type": "MARKET",
                                 "transaction_type": "BUY"})
        oco = dict(calls[1]["args"])
        oco_ref = oco.pop("reference_id")
        self.assertEqual(oco, {"smart_order_type": "OCO", "segment": "CASH", "trading_symbol": "TATAPOWER",
                               "quantity": 8, "product_type": "MIS", "exchange": "NSE", "duration": "DAY",
                               "net_position_quantity": 8, "transaction_type": "SELL",
                               "target": {"trigger_price": "370.04", "order_type": "LIMIT", "price": "370.04"},
                               "stop_loss": {"trigger_price": "358.32", "order_type": "SL_M", "price": None}})
        self.assertIn("only after the entry has filled", calls[1]["when"])
        for r in (ref, oco_ref):                       # Groww: 8 to 20 letters, digits and at most two hyphens
            self.assertRegex(r, r"^[A-Za-z0-9-]{8,20}$")
            self.assertLessEqual(r.count("-"), 2)
        self.assertEqual(ticket.groww_calls(tsla()), calls)             # the same order, the same ids
        self.assertNotEqual(ticket.groww_calls(tsla(qty="9"))[0]["args"]["order_reference_id"], ref)
        blob = json.dumps(calls)
        self.assertNotIn("why", blob)
        self.assertNotIn("plan", blob)

    def test_the_bracket_call_leaves_out_why_and_plan(self):
        self.assertEqual(ticket.fingerprint(tsla()), ticket.fingerprint(TSLA_CALL))

    def test_other_order_types_and_a_stop_limit_leg(self):
        lim = ticket.groww_calls(tsla(type="limit", limit_price="364.00"))[0]["args"]
        self.assertEqual((lim["order_type"], lim["price"]), ("LIMIT", 364.0))
        sl = ticket.groww_calls(tsla(stop_loss_limit_price="358.00"))[1]["args"]["stop_loss"]
        self.assertEqual(sl, {"trigger_price": "358.32", "order_type": "SL", "price": "358.00"})
        sell = ticket.groww_calls({"symbol": "RELIANCE.NS", "side": "sell", "qty": "3", "type": "market",
                                   "time_in_force": "day"})
        self.assertEqual(len(sell), 1)
        self.assertEqual((sell[0]["args"]["trading_symbol"], sell[0]["args"]["transaction_type"],
                          sell[0]["args"]["product"]), ("RELIANCE", "SELL", "MIS"))
        stp = ticket.groww_calls({"symbol": "RELIANCE.NS", "side": "sell", "qty": 3, "type": "stop",
                                  "stop_price": "2900", "time_in_force": "day"})[0]["args"]
        self.assertEqual((stp["order_type"], stp["trigger_price"]), ("SL_M", 2900.0))

    def test_what_groww_cannot_take_is_refused_in_plain_words(self):
        bad = {"a US ticker": dict(symbol="TSLA"), "a rupee amount": dict(qty=None, notional="5000"),
               "a fractional share": dict(qty="2.5"), "a good-till-canceled order": dict(time_in_force="gtc"),
               "a trailing stop": dict(type="trailing_stop"), "a limit order with no price": dict(type="limit",
                                                                                                    limit_price=None),
               "a bracket that sells": dict(side="sell")}
        for what, over in bad.items():
            o = tsla(**over)
            if over.get("qty", 1) is None:
                o.pop("qty")
            with self.assertRaises(ticket.TicketError, msg=what):
                ticket.groww_calls(o)
            self.assertIsNotNone(ticket.calls_error(o), what)
        self.assertIsNone(ticket.calls_error(tsla()))
        self.assertIn("SYMBOL.NS", ticket.calls_error(tsla(symbol="TSLA")))

    def test_plain_english(self):
        self.assertEqual(ticket.plain(AAPL), "BUY ₹1,250 of AAPL, market order, good for today")
        self.assertEqual(ticket.plain({"symbol": "KO", "side": "sell", "qty": "1", "type": "limit",
                                       "limit_price": "95", "time_in_force": "gtc"}),
                         "SELL 1 share of KO, limit order at ₹95, good until canceled")
        self.assertEqual(ticket.plain(tsla()), TSLA_PLAIN)
        lim = tsla(type="limit", limit_price="364.00")
        self.assertEqual(ticket.plain(lim).split(" / ")[0], "BUY 8 TATAPOWER.NS, limit 364.00, good for today")
        self.assertEqual(ticket.max_loss(lim), (45.44, 358.32))
        no_plan = dict(TSLA_CALL)
        self.assertEqual(ticket.max_loss(no_plan), (None, 358.32))


class McpConfig(unittest.TestCase):
    def test_the_groww_mcp_example_has_no_keys_in_it(self):
        with open(os.path.join(ROOT, "trader-broker", "groww_mcp.example.json")) as fh:
            raw = fh.read()
        server = json.loads(raw)["mcpServers"]["growwmcp"]
        self.assertEqual(server["command"], "npx")
        self.assertIn("https://mcp.groww.in/mcp", server["args"])
        for word in ("key", "secret", "token", "password", "totp"):
            self.assertNotIn(word, raw.lower())          # the login happens in Groww's own browser page
        self.assertFalse(os.path.exists(os.path.join(ROOT, "trader-broker", "claude_desktop_config.example.json")))


class Flow(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.orders = os.path.join(self.d, "orders.json")
        shutil.copy(ORDERS_PATH, self.orders)
        self.set_symbol(SYM)
        self.cfg = os.path.join(self.d, "config.json")
        shutil.copy(CFG_PATH, self.cfg)
        self.risk = os.path.join(self.d, "state", "risk.json")
        self.state = os.path.join(self.d, "state", "broker.json")
        self.pf = os.path.join(self.d, "portfolio.json")
        self.none = os.path.join(self.d, "none")

    def tearDown(self):
        shutil.rmtree(self.d)

    def set_symbol(self, sym):
        with open(self.orders) as fh:
            doc = json.load(fh)
        doc["orders"][0]["symbol"] = sym
        with open(self.orders, "w") as fh:
            json.dump(doc, fh)

    def args(self, *extra, **kw):
        return list(extra) + ["--orders", self.orders, "--config", self.cfg, "--risk", self.risk,
                              "--state", self.state, "--now", kw.get("now", NOW)]

    def run_risk(self, now=NOW):
        with redirect_stdout(io.StringIO()):
            return check.main(["--orders", self.orders, "--config", self.cfg, "--portfolio", self.pf,
                               "--prices", self.none, "--state", self.state, "--now", now, "--out", self.risk])

    def state_doc(self):
        with open(self.state) as fh:
            return json.load(fh)

    def test_nothing_is_ready_before_the_risk_check(self):
        code, text, _ = run(self.args("show"))
        self.assertEqual(code, 1)
        self.assertIn("NOT READY", text)
        self.assertNotIn("Reply \"yes\"", text)
        code, _, err = run(self.args("approve", "--index", "1", "--reply", "yes"))
        self.assertEqual(code, 1)
        self.assertIn("not ready", err)

    def test_the_full_two_yes_flow(self):
        self.assertEqual(self.run_risk(), 0)
        code, text, _ = run(self.args("show", "--index", "1"))
        self.assertEqual(code, 0)
        self.assertIn("ORDER 1 of 1, LIVE ACCOUNT, REAL MONEY, Groww (NSE, intraday MIS)", text)
        for part in TSLA_PLAIN.split(" / "):
            self.assertIn("  " + part + "\n", text)
        self.assertIn("READY: trader-risk PASS", text)
        self.assertIn("Step 1 of 2, place_order (now), with exactly:", text)
        self.assertIn("Step 2 of 2, create_smart_order (only after the entry has filled", text)
        self.assertIn('"product": "MIS"', text)
        self.assertIn('"trading_symbol": "TATAPOWER"', text)
        self.assertIn('"smart_order_type": "OCO"', text)
        self.assertIn('"trigger_price": "358.32"', text)
        self.assertIn("Groww has no paper mode", text)
        self.assertNotIn('"plan"', text)
        self.assertNotIn('"why"', text)
        self.assertIn("Allow once", text)

        code, text, _ = run(self.args("approve", "--index", "1", "--reply", "sure"))
        self.assertEqual(code, 1)
        self.assertIn("Not recorded", text)
        self.assertFalse(os.path.exists(self.state))

        code, text, _ = run(self.args("approve", "--index", "1", "--reply", "yes"))
        self.assertEqual(code, 0)
        self.assertIn("place_order", text)
        self.assertIn("create_smart_order", text)
        first, _ = json.JSONDecoder().raw_decode(text[text.index("{"):])
        self.assertEqual(first, ticket.groww_calls(tsla())[0]["args"])
        self.assertIn("never drop a field", text.lower())
        code, _, err = run(self.args("approve", "--index", "1", "--reply", "yes"))
        self.assertEqual(code, 1)
        self.assertIn("APPROVED", err)

        code, text, _ = run(self.args("result", "--index", "1", "--status", "placed", "--broker-id", "abc123",
                                      "--filled-qty", "8", "--filled-price", "364.20", "--portfolio", self.pf,
                                      now="2026-10-19 10:01"))
        self.assertEqual(code, 0)
        self.assertIn("step 2: once the entry has filled, call create_smart_order", text)
        self.assertIn("quantity and net_position_quantity set to 8", text)
        st = self.state_doc()
        self.assertEqual([r["status"] for r in st["orders"]], ["approved", "placed", "filled"])
        appr, plc = st["orders"][0], st["orders"][1]
        self.assertEqual((appr["reply"], appr["kind"], appr["max_loss"], appr["date"]), ("yes", "entry", 46.88, TODAY))
        self.assertEqual(appr["at"], "2026-10-19T10:00:00+05:30")
        self.assertEqual((plc["broker_order_id"], plc["max_loss"], plc["kind"]), ("abc123", 46.88, "entry"))
        with open(self.pf) as fh:
            pf = json.load(fh)
        self.assertEqual(pf["cash"], 2086.4)
        self.assertEqual(pf["positions"][0]["shares"], 8)

        code, text, _ = run(self.args("show", "--index", "1"))
        self.assertIn("DONE: placed", text)
        code, text, _ = run(["log", "--state", self.state, "--now", NOW])
        self.assertIn("1 placed today", text)
        self.assertIn("max loss ₹46.88", text)

        # trader-risk now counts it: a second TATAPOWER.NS buy today is a duplicate, and ₹46.88 is used
        res = check.check([tsla()], {"budget": 5000}, state=st, now=check.parse_now("2026-10-19 10:15"))
        self.assertIn("already placed today", " ".join(res["results"][0]["reasons"]))
        self.assertEqual((res["today"]["entries_placed"], res["today"]["loss_at_risk"]), (1, 46.88))

    def test_flatten_by_the_close(self):
        self.run_risk()
        run(self.args("approve", "--index", "1", "--reply", "yes"))
        run(self.args("result", "--index", "1", "--status", "placed", "--broker-id", "abc",
                      "--filled-qty", "8", "--filled-price", "364.20", "--portfolio", self.pf))
        late = "2026-10-19 15:00"
        code, text, _ = run(["flatten", "--symbol", "TATAPOWER.NS", "--orders", self.orders, "--portfolio", self.pf,
                             "--plan", PLAN_PATH, "--config", self.cfg, "--now", late])
        self.assertEqual(code, 0)
        self.assertIn("SELL 8 shares of TATAPOWER.NS, market order, good for today (flat by 15:15 India)", text)
        self.assertIn("replaced 1 earlier proposal", text)
        self.assertIn("cancel_smart_order(segment=CASH, smart_order_type=OCO", text)
        with open(self.orders) as fh:
            doc = json.load(fh)
        sell = ticket.groww_calls(doc["orders"][0])
        self.assertEqual(len(sell), 1)
        self.assertEqual({k: v for k, v in sell[0]["args"].items() if k != "order_reference_id"},
                         {"trading_symbol": "TATAPOWER", "quantity": 8, "validity": "DAY", "exchange": "NSE",
                          "segment": "CASH", "product": "MIS", "order_type": "MARKET", "transaction_type": "SELL"})
        self.assertEqual(self.run_risk(now=late), 0)       # after the 14:45 entry cutoff: an exit still passes
        with open(self.risk) as fh:
            self.assertEqual(json.load(fh)["results"][0]["kind"], "exit")
        code, text, _ = run(self.args("show", now=late))
        self.assertEqual(code, 0)
        self.assertIn("READY", text)
        self.assertEqual(run(self.args("approve", "--index", "1", "--reply", "yes sell 8 TATAPOWER.NS", now=late))[0], 0)
        code, _, _ = run(self.args("result", "--index", "1", "--status", "placed", "--filled-qty", "8",
                                   "--filled-price", "366.10", "--portfolio", self.pf, now="2026-10-19 15:41"))
        self.assertEqual(code, 0)
        with open(self.pf) as fh:
            pf = json.load(fh)
        self.assertEqual((pf["cash"], pf["positions"]), (5015.2, []))
        self.assertEqual(check.day_trades(self.state_doc(), TODAY), (1, ["2026-10-19 TATAPOWER.NS"]))
        code, _, err = run(["flatten", "--symbol", "TATAPOWER.NS", "--orders", self.orders, "--portfolio", self.pf,
                            "--now", late])
        self.assertEqual(code, 1)
        self.assertIn("nothing to flatten", err)

    def test_flatten_with_the_broker_qty(self):
        code, text, _ = run(["flatten", "--symbol", "tsla", "--qty", "8", "--orders", self.orders,
                             "--portfolio", self.none, "--plan", self.none, "--config", self.cfg, "--now", NOW])
        self.assertEqual(code, 0)
        self.assertNotIn("Check it against Groww", text)
        self.assertEqual(run(["flatten", "--symbol", "TATAPOWER.NS", "--qty", "0", "--orders", self.orders])[0], 1)

    def test_an_edited_order_is_not_ready(self):
        self.run_risk()
        with open(self.orders) as fh:
            doc = json.load(fh)
        doc["orders"][0]["qty"] = "9"
        with open(self.orders, "w") as fh:
            json.dump(doc, fh)
        code, text, _ = run(self.args("show", "--index", "1"))
        self.assertEqual(code, 1)
        self.assertIn("was not in the last risk check", text)

    def test_yesterdays_check_does_not_count(self):
        self.run_risk(now="2026-10-16 10:00")
        code, text, _ = run(self.args("show", "--index", "1"))
        self.assertIn("not today", text)

    def test_blocked_orders_are_never_ready(self):
        self.assertEqual(self.run_risk(now="2026-10-19 09:25"), 1)
        code, text, _ = run(self.args("show", "--index", "1", now="2026-10-19 09:25"))
        self.assertIn("BLOCKED by trader-risk: window: no new entries before 09:30", text)
        code, _, _ = run(self.args("approve", "--index", "1", "--reply", "yes", now="2026-10-19 09:25"))
        self.assertEqual(code, 1)

    def test_result_needs_an_approval_and_decline_is_logged(self):
        self.run_risk()
        code, _, err = run(self.args("result", "--index", "1", "--status", "placed"))
        self.assertEqual(code, 1)
        self.assertIn("no yes recorded", err)
        code, text, _ = run(self.args("decline", "--index", "1", "--reply", "no thanks"))
        self.assertEqual(code, 0)
        code, text, _ = run(self.args("show", "--index", "1"))
        self.assertIn("DONE: declined", text)

    def test_a_non_nse_symbol_is_never_ready(self):
        self.set_symbol("TSLA")
        self.run_risk()
        code, text, _ = run(self.args("show", "--index", "1"))
        self.assertIn("NOT READY: cannot build the Groww call", text)
        self.assertNotIn("Reply \"yes\"", text)
        code, _, err = run(self.args("approve", "--index", "1", "--reply", "yes"))
        self.assertEqual(code, 1)
        self.assertIn("not ready", err)
        code, text, _ = run(self.args("show", "--index", "1", "--json"))
        doc = json.loads(text)[0] if text.lstrip().startswith("[") else json.loads(text)
        self.assertEqual((doc["ready"], doc["calls"], doc["broker"], doc["paper"]), (False, None, "groww", False))
        self.assertIn("SYMBOL.NS", doc["calls_error"])

    def test_the_json_ticket_carries_the_groww_calls(self):
        self.run_risk()
        code, text, _ = run(self.args("show", "--index", "1", "--json"))
        doc = json.loads(text)[0] if text.lstrip().startswith("[") else json.loads(text)
        self.assertEqual((doc["ready"], doc["broker"], doc["paper"], doc["calls_error"]), (True, "groww", False, None))
        self.assertEqual([c["method"] for c in doc["calls"]], ["place_order", "create_smart_order"])
        self.assertNotIn("tool_input", doc)

    def test_fill_sell_relieves_the_oldest_lot(self):
        pf = {"cash": 0, "positions": [{"ticker": "KO", "shares": 3, "lots": [
            {"id": "KO-1", "date": "2025-01-02", "shares": 2, "cost": 120.0},
            {"id": "KO-2", "date": "2026-01-02", "shares": 1, "cost": 70.0}]}]}
        with open(self.pf, "w") as fh:
            json.dump(pf, fh)
        code, text, _ = run(["fill", "--symbol", "KO", "--side", "sell", "--qty", "2.5", "--price", "90",
                             "--date", TODAY, "--portfolio", self.pf, "--config", self.cfg, "--state", self.state])
        self.assertEqual(code, 0)
        with open(self.pf) as fh:
            pf = json.load(fh)
        self.assertEqual(pf["cash"], 225.0)
        lots = pf["positions"][0]["lots"]
        self.assertEqual([l["id"] for l in lots], ["KO-2"])
        self.assertEqual(lots[0]["shares"], 0.5)
        self.assertEqual(lots[0]["cost"], 35.0)
        self.assertEqual(self.state_doc()["orders"][-1]["status"], "filled")
        code, _, err = run(["fill", "--symbol", "KO", "--side", "sell", "--qty", "5", "--price", "90",
                            "--portfolio", self.pf, "--config", self.cfg, "--state", self.state])
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", err)



class DotNs(unittest.TestCase):
    def test_a_yes_that_names_another_dot_ns_order_is_refused(self):
        order = {"symbol": "TCS.NS", "side": "sell", "qty": "3", "type": "market", "time_in_force": "day"}
        batch = ["TCS.NS", "RELIANCE.NS", "M&M.NS"]
        self.assertTrue(ticket.parse_yes("yes sell 3 TCS.NS", order, batch)[0])
        for reply in ("yes sell 3 RELIANCE.NS", "yes sell 3 M&M.NS"):
            ok, why = ticket.parse_yes(reply, order, batch)
            self.assertFalse(ok, reply)
            self.assertIn("this order is for TCS.NS", why)


if __name__ == "__main__":
    unittest.main()
