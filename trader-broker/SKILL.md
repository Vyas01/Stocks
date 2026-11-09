---
name: trader-broker
description: >-
  Order Executor. Sends approved orders to your Groww account, never without
  your yes. Groww has no paper mode, so every order is real money. Shows each
  order as a plain ticket (a bracket shows its stop-loss, take-profit and the
  max loss at the stop) plus the exact Groww calls: an intraday (MIS)
  place_order, then an OCO smart order for the stop and the target once the
  entry has filled. Records your yes word for word, then Claude's own Allow
  once / Deny card asks again. Builds the sell ticket that closes a day trade
  by your flat-by time, records fills, and logs each trade's max loss so
  trader-risk can hold the daily limit. Covers connecting Groww's official MCP
  server or the growwapi SDK, and setting order tools to "Needs approval".
  Use when the user says "place the order", "buy it", "execute", "send it to
  Groww", "close my position", "flatten", "get me out", "connect Groww", or
  after /trader-risk passes.
argument-hint: "[order number]"
---

# trader-broker

The Order Executor is the only skill in this pack that can lead to a real
order, so it is the strictest. An order reaches the market only after three
separate gates, every time, for every order:

1. **trader-risk passed this exact order today** (matched by fingerprint).
2. **The user typed an explicit yes for this one order** in the chat.
3. **The user clicked Allow once** on Claude's own permission card, which
   appears because the order tool is set to "Needs approval".

Two yeses from the user, one PASS from the rules. No yes, no order.

**There is no paper mode.** Groww's Trading API documentation shows no paper or
sandbox account. Every order this skill sends is a real order with real money.
To rehearse, run the whole flow and answer no at the yes step.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/ticket.py" show                     # every ticket, READY or not
python3 "${CLAUDE_SKILL_DIR}/ticket.py" approve --index 1 --reply "yes"
python3 "${CLAUDE_SKILL_DIR}/ticket.py" result --index 1 --status placed --broker-id ID --filled-qty 8 --filled-price 364.20
python3 "${CLAUDE_SKILL_DIR}/ticket.py" fill --symbol TATAPOWER.NS --side sell --qty 8 --price 370.04
python3 "${CLAUDE_SKILL_DIR}/ticket.py" flatten --symbol TATAPOWER.NS --qty 8
python3 "${CLAUDE_SKILL_DIR}/ticket.py" log
```

`ticket.py` never talks to a broker. It renders tickets, checks that a reply
is a real yes for that order, builds the flatten ticket, and keeps the log in
`trader/state/broker.json`. `--now "2026-10-19 10:00"` pins the clock (India time).

## What it reads and writes

| file | what |
| --- | --- |
| `trader/orders.json` | the proposed orders (trader-budget writes it; `flatten` replaces it) |
| `trader/state/risk.json` | trader-risk's verdicts; only a PASS from today is READY |
| `trader/state/broker.json` | every yes, no, placed, failed and filled, with each entry's max loss |
| `trader/portfolio.json` | cash and shares, updated by `fill` and by `result --filled-qty` |
| `trader/plan.json` | the flat-by time for `flatten` |

## How an order becomes Groww calls

The pack's order file (`trader/orders.json`) keeps one format for every
skill. `ticket.py` turns it into Groww's calls at the last step. These names
and values are from Groww's Trading API documentation (groww.in/trade-api/docs,
read 2026-11-09):

| the ticket | Groww |
| --- | --- |
| `TATAPOWER.NS` | `trading_symbol` `TATAPOWER` (the `.NS` is Yahoo's, Groww does not take it) |
| every day trade | `exchange` NSE, `segment` CASH, `product` MIS (intraday), `validity` DAY |
| market / limit / stop / stop-limit | `order_type` MARKET / LIMIT / SL_M / SL |
| buy / sell | `transaction_type` BUY / SELL |
| a bracket's stop-loss and take-profit | a second call, `create_smart_order` with `smart_order_type` OCO |
| the order's identity | `order_reference_id` / `reference_id`: `dt-` or `oco-` plus 14 characters of the order's fingerprint. Groww wants 8 to 20 letters and digits with at most two hyphens, and the same order always gets the same id, so a repeated call cannot place it twice |

A bracket is **two calls**, because Groww's OCO can only be set on a position
you already hold:

1. `place_order`: the MIS entry (market, or limit if the ticket says so).
2. `create_smart_order` (OCO): after the entry has filled, a target leg (LIMIT)
   and a stop-loss leg (SL_M, or SL with a limit if the ticket has one) for
   `net_position_quantity` shares. Set `quantity` and `net_position_quantity`
   to the shares that actually filled.

Between the fill and the OCO the position has no stop at Groww. Do step 2 at
once. If it fails, tell the user in the same message and offer to close the
position. The user's yes covers the whole ticket, both calls, because both are
printed on it; each call still gets its own Allow once.

What Groww cannot take here, and the ticket says so in plain words and stays
NOT READY: a symbol that is not `SYMBOL.NS`, a rupee amount instead of shares
(`notional`), part of a share, a good-till-canceled order (MIS orders are day
orders), trailing stops, and a bracket that sells. Never turn an MIS order into
CNC (delivery) to get past a problem: that is a different trade, held overnight
and paid for in full.

## Setup A: Groww's official MCP server (Claude connector)

Groww announced its MCP server on 2025-08-04 (groww.in/updates/groww-mcp). It
is powered by Groww's APIs and the page calls it early-stage technology.

1. In Claude: Settings > Connectors > Add custom connector. Name `GrowwMCP`,
   URL `https://mcp.groww.in/mcp`. Click Connect and sign in on Groww's own
   page. Groww's page says the custom-connector route is for Claude Pro.
2. In Claude Desktop, Cursor or VS Code with Node.js installed, the same server
   can be added with the block in `groww_mcp.example.json` here. Check the
   `args` against the line on Groww's page, which is the source of truth. The
   first run opens a browser tab to sign in.
3. **Set the tool permissions.** Customize > Connectors, open Groww, and for
   each tool pick Always allow, Needs approval or Blocked. Read the connector's
   own tool list; do not guess names:
   - every tool that places, modifies or cancels anything (orders, smart
     orders, GTT, OCO): **Needs approval**. Never Always allow.
   - read-only tools (positions, holdings, margin, quotes, order status):
     Always allow is fine.
4. **Check before the first real day.** Groww's page lists what the server
   can do in general terms (stocks and F&O, "smart order management", stop-loss
   orders) but not its tools or products. Ask Claude to list the connector's
   tools, and confirm in plain words that it can: (a) place a NSE cash order
   with product MIS, (b) create an OCO with a target and a stop-loss, (c) cancel
   that OCO. If any of the three is missing, do not improvise. Use Setup B for
   the missing piece, or have the user place that call in the Groww app by hand
   from the ticket.
5. Groww's page says selling through the MCP server needs DDPI authorisation
   on the demat account. Closing a long position is a sell, so the user needs
   it for the exit too. Say so before the first day, not at 3:15 PM.

## Setup B: the Groww Trading API (growwapi SDK)

For the calls the connector cannot make. It needs an active Trading API
subscription on the user's Groww account (the docs say so) and Python 3.9 or
newer: `pip install growwapi`. Groww offers two logins: an API key and secret
that need daily approval on the Groww Cloud API keys page, or a TOTP token that
does not expire (`pip install pyotp`). The user types them into their own
environment variables. **Keys, secrets and TOTP codes never go in the chat.**
Never ask for them, never read the user's environment back, and if the user
pastes one anyway, tell them to delete the message and make a new key.

The `args` on each ticket call are the SDK's keyword arguments, with the
values Groww's constants hold (`PRODUCT_MIS` is "MIS", `EXCHANGE_NSE` is
"NSE", and so on):

```python
import os
from growwapi import GrowwAPI

token = GrowwAPI.get_access_token(api_key=os.environ["GROWW_API_KEY"],
                                  secret=os.environ["GROWW_API_SECRET"])
groww = GrowwAPI(token)
groww.place_order(**entry_args)          # step 1: "args" of the first call on the ticket
groww.create_smart_order(**oco_args)     # step 2, after the fill: "args" of the second call
```

Groww's API limits Orders (create, modify, cancel) to 10 requests a second and
250 a minute, shared across those calls. A day trade is far below that.
Community projects report that Groww asks for a static IP address to place
orders. The documentation I read did not say so; if an order is rejected for
that reason, it is the user's account setting to fix, not something to work
around.

In Claude Code, keep the order tools on ask in `.claude/settings.json`, and
never put an order tool in `allow`.

## Steps: the entry

1. `ticket.py show`. Only READY tickets go to the user. A ticket that is NOT
   READY or BLOCKED goes back to `/trader-risk` (or, for "cannot build the
   Groww call", back to `/trader-budget`).
2. Show ONE ticket and ask: "Place this order? Reply yes or no." One order
   per question. Never offer "yes to all". Remind the user it is real money.
3. Run `ticket.py approve --index N --reply "<the user's reply, word for word>"`.
   If it prints "Not recorded", the reply was not an explicit yes for this
   order (for example "sure", "yes to all", or a yes that names a different
   stock or amount). Ask again. Never turn a reply into a yes yourself.
4. Only after "Recorded your yes", send step 1 with exactly the values the
   command printed. Claude's card appears: Allow once or Deny. If a Groww tool
   cannot take a field (the product MIS, a trigger price), stop and tell the
   user. Never drop a field or change a value to make a call work.
5. Record what happened: `ticket.py result --index N --status placed
   --broker-id <Groww order id> --filled-qty Q --filled-price P` (the fill from
   `get_order_status`, `get_trade_list_for_order` or the positions), or
   `--status denied`, or `--status failed` with `--note`. A failed order is not
   retried without a new check and a new yes. The log keeps the entry's max
   loss for trader-risk's daily limit.
6. When the entry has filled, send step 2 (the OCO) with the filled quantity.
   Allow once again. Tell the user the stop and the target are now live.

## Steps: while it is open, and out by the close

- trader-alerts watches the stop, the target and the flat-by time
  (`alerts.py add --from-plan`). Groww's OCO does the stopping and the selling.
- When the stop-loss or the target fills, record it:
  `ticket.py fill --symbol TATAPOWER.NS --side sell --qty 8 --price 358.32`.
- By `flat_by` (15:15 India), anything still open gets closed. Groww's own
  description of MIS is that it "must close by day end", so 15:15 leaves time:
  1. Ask Groww how many shares are held: `get_positions_for_user` or
     `get_position_for_trading_symbol` (read only).
  2. `ticket.py flatten --symbol TATAPOWER.NS --qty 8` writes a market sell
     (MIS) for those shares to `trader/orders.json`.
  3. `/trader-risk`. A sell that only closes what the user holds is never
     blocked by the daily limits or the entry window.
  4. `ticket.py show`, then the user's yes for that one order, as above.
  5. Cancel the OCO first, so it cannot also sell: `cancel_smart_order` with
     `segment` CASH, `smart_order_type` OCO and the `smart_order_id` from
     `get_smart_order` or the smart-order list (Needs approval). Then send the
     sell with `place_order`, then `ticket.py result`.

## Example: the reel

The shared example trade on a made-up NSE symbol (prices are illustrative):

```
ORDER 1 of 1, LIVE ACCOUNT, REAL MONEY, Groww (NSE, intraday MIS)
  BUY 8 TATAPOWER.NS, market, good for today
  stop-loss 358.32
  take-profit 370.04
  max loss about ₹46.88 if the stop fills at 358.32 (it can fill worse in a fast market)
  READY: trader-risk PASS, waiting for your yes
  Step 1 of 2, place_order (now), with exactly:
    {"trading_symbol": "TATAPOWER", "quantity": 8, "validity": "DAY", "exchange": "NSE",
     "segment": "CASH", "product": "MIS", "order_type": "MARKET", "transaction_type": "BUY",
     "order_reference_id": "dt-d7f1c1828131c7"}
  Step 2 of 2, create_smart_order (only after the entry has filled; ...), with exactly:
    {"smart_order_type": "OCO", "reference_id": "oco-d7f1c1828131c7", "segment": "CASH",
     "trading_symbol": "TATAPOWER", "quantity": 8, "product_type": "MIS", "exchange": "NSE",
     "duration": "DAY", "net_position_quantity": 8, "transaction_type": "SELL",
     "target": {"trigger_price": "370.04", "order_type": "LIMIT", "price": "370.04"},
     "stop_loss": {"trigger_price": "358.32", "order_type": "SL_M", "price": null}}
  Groww has no paper mode: this is a real order with real money.
  Reply "yes" to place this one order, or "no" to skip it.
```

(The tool prints each JSON object indented; it is shortened here.) The user
replies "yes". Claude records it and sends step 1; the card reads "Claude wants
to use" the Groww order tool with those values and two buttons: Allow once,
Deny. When the entry fills, Claude sends step 2 the same way. The `why` and the
plan stay in the file; they are never sent.

## What it never does

- Never places an order without all three gates, and never two orders on one yes. A bracket is one ticket:
  its entry and its OCO, both shown before the yes.
- Never places orders from a scheduled or background task: nobody is there to say yes.
- Never asks for, reads, stores or repeats Groww logins, API keys, secrets or TOTP codes.
- Never changes a value to get a call through, never swaps MIS for CNC, never sends a non-NSE symbol.
- Never calls bulk or "all" tools (cancel all, close all) or options and F&O tools on its own.
- Never promises a fill price: a market order and a stop fill at whatever the market gives.

## Safety

- Education and tooling, not financial advice. A PASS is a rules check, not a recommendation.
- Groww has no paper mode: every order this pack sends is a real order with real money. To rehearse, run the
  whole flow and answer no at the yes step.
- Nothing in this pack places an order except trader-broker, and only when all three hold: trader-risk
  passed that exact order today, the user typed an explicit yes for that one order in the chat, and the
  user clicked Allow once on Claude's own card because the order tool is set to "Needs approval"
  (Customize > Connectors > tool permissions). Never set an order tool to "Always allow".
- No options, margin, short selling or leverage unless the config allows it and the user confirms.
- Groww logins, API keys and TOTP secrets stay in Groww's own sign-in page or the user's own environment,
  never in the chat.
