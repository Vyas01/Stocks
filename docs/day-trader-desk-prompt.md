# Prompt for a new Claude Code chat: build "Day Trader Desk"

Copy everything below the words START OF PROMPT into a new Claude Code chat opened on the day-trader-skill repository.

START OF PROMPT

You are a senior product designer and engineer. I want you to build a proper app with a screen I can look at, on top of a tool I already have. Work in plain words with me: I am not a technical person. Be honest and direct. If my idea has a weak spot, say so and suggest a better one.

## 1. What I want

A local app called "Day Trader Desk" for the Indian stock market (NSE). One screen where I can see the market clock, scan for stocks, look at charts, plan a trade, check it against my own rules, and keep a simple journal. Money is shown in rupees. Time is always India time (IST).

## 2. Decisions I have already made

- It runs only on my own computer and opens in my browser. It must not be reachable from the internet.
- It is view and plan only. It must NOT place orders. I place orders myself in the Groww app. A later phase may add ordering, but only if I ask for it in writing.
- One user: me.
- Prices come from free Yahoo Finance data. This data is delayed, unofficial and can fail, so the app must always show how old the data is and say plainly when something is missing.
- I also want to be able to start it with a single easy step.

## 3. What already exists

The code is in the day-trader-skill repository (branch groww-inr). It is a set of 11 Claude skills. Each skill is a folder with a SKILL.md and a small Python program that uses only the standard library. There are 331 passing tests in the tests folder. Run them first and tell me the result.

The programs and their jobs:
- trader-scanner (scan.py): daily scan of closing prices for setups (20 day closing high breakout, bull flag, reclaim of the 20 day average, oversold, oversold bounce) and an opening range breakout scan on 5 minute bars. Writes trader/watchlist.json.
- trader-news (news.py): headlines per stock from Yahoo, and the day move. Its SEC filing part only works for US companies, so for Indian stocks show Yahoo headlines only.
- trader-entry (entry.py): watches the opening range and says waiting, triggered or expired. Writes trader/entry.json.
- trader-exit (exit.py): sets the stop and target before the entry. Writes trader/plan.json.
- trader-timemachine (timemachine.py): replays the rest of the day 10,000 times from the stock's own 5 minute bars and gives odds, a verdict and a fan chart. Needs 20 full past sessions, so it cannot run on very new listings.
- trader-budget (size.py): works out whole shares from my capital and my maximum loss per trade. Writes trader/orders.json in the pack's own order format.
- trader-risk (check.py): checks the order against my rules. Says PASS or BLOCK with reasons. Writes trader/state/risk.json.
- trader-broker (ticket.py): turns an approved order into Groww calls and keeps a decision log. In this app I only want its plain English ticket and the Groww values shown for copying. No send button.
- trader-alerts (alerts.py): the NSE clock, quotes and alert rules.
- trader-analyst and trader-pelosi are US only. Leave them out of the app.

India rules already built in: session 9:15 to 15:30 IST, NSE 2026 holiday list (the 2027 list is not published yet, so warn when a date is outside the covered year), no early closes, every trade closed by 15:15, entries allowed from 9:30 to 14:45, stock names written like RELIANCE.NS. Settings live in trader/config.json (see trader-budget/config.example.json). The example amounts are placeholders and I will set my own.

Read the README and each SKILL.md before you plan.

## 4. How you must work

1. Start in plan mode. Do not write code yet.
2. First reply: (a) the test result, (b) anything in the existing code that blocks an app, (c) your questions for me, (d) a written plan with folder layout, technology choices and reasons, risks, and the phases below with a done check for each.
3. Wait for me to type "approved" before you build anything.
4. Build one phase at a time. After each phase: run all tests, add tests for new code, run the app and check it with a real browser (Chromium and Playwright are already installed), and give me a short list of steps to try it myself, in simple words.
5. Reuse the existing programs by importing their functions. Do not copy their logic into new code, so the 331 tests keep protecting it. If something needs changing in them, tell me first and keep the old tests passing.
6. Keep the technology simple. One command to start, and one browser address. No cloud accounts. Bind the server to 127.0.0.1 only.
7. Commit locally after each phase with a clear message. Do not push anything, and never push to the original author's repository (the remote named origin). My own repository is the remote named mine, and only push there when I tell you to.
8. Never ask me for passwords, API keys or tokens, and never store any. The app does not need any.
9. Do not invent data. If a number is missing, show "no data" and say why.
10. Ask me before any choice that I would not understand. Explain choices in one or two plain sentences.

## 5. The screens

Today: market open or closed, the time in IST, next open, and any holiday. Last scan summary, how many stocks are at 20 day highs (a sign the whole market moved), my risk used today against my limits, and the state of any planned trade.

Scanner: run the daily scan on my watchlist and show a sortable, filterable table (stock, price in rupees, RSI, setup, volume). Show progress for slow scans. Say "partial result" when some charts failed. Mark stretched stocks (RSI above 70) clearly. A separate tab runs the opening range scan after 9:35 AM. Let me edit the watchlist, import the NSE equity list file if I have one, and include a sensible built in starter list.

Stock page: candlestick chart (5 minute and daily) with the opening range, the entry level, the stop and the target drawn on it. Yahoo headlines. The entry status in words (waiting, triggered, expired). A clear warning for new listings with fewer than 30 days of history.

Trade planner: a step by step screen that follows the real order of the tools. Entry, then stop and target, then the Time Machine odds (fan chart, histogram, verdict in words), then share size from my capital and maximum loss, then the risk check with every reason shown. It ends in a ticket in plain English with the exact Groww values and a copy button. No send button. Anything that fails a check stays visibly blocked.

Journal: decisions, fills that I type in by hand, the maximum loss used today, and a simple history. This is for learning, not for tax advice.

Settings: capital, maximum loss per trade, daily loss limit, trades per day, entry window and flat by time. Check the numbers for mistakes before saving and save to trader/config.json. Show a note that Groww has no practice mode.

Help: a short glossary in plain words (RSI, stop, target, opening range, R, bull flag) and a "how to use this each day" guide.

## 6. Design direction

Calm, clear and trustworthy, like a good finance tool and not a casino. Large readable numbers, rupee formatting everywhere, India time everywhere. Do not use colour alone to show meaning: use words and icons too. Real, useful text on every screen including empty states, no placeholder text. Plain language at about a sixth grade level. One main action per screen. Always show data age. Never use words like "sure thing", "guaranteed" or "buy now". Include a visible "Not financial advice, most day traders lose money" line. Offer a light and a dark look. Tell me your design choices and why before you build them, and keep it honest if a screen feels cluttered.

## 7. Things to handle on purpose

- Yahoo may rate limit or return errors. Be polite with request pauses, cache results with timestamps, and show friendly messages.
- Long scans must run in the background without freezing the screen.
- The programs read and write files in the trader folder. Avoid two writers corrupting a file.
- The Time Machine and the scanner need enough history. Explain this on screen when a stock has too little.
- Breadth matters: if most stocks break out on the same day, say it is a market wide move, not many separate signals.

## 8. Phases

Phase 0: plan only (no code). Wait for "approved".
Phase 1: project skeleton, one command start, Today screen, Settings, tests.
Phase 2: Scanner screens with the watchlist and progress.
Phase 3: Stock page with charts, news and entry status.
Phase 4: Trade planner and the read only ticket.
Phase 5: Journal, Help, polish, accessibility check, and a final "how to use it every day" page.
Phase 6: only if I ask in writing, a design for the Groww order step, with the same safety gates as the skill: a passing risk check, my typed yes for that one order, and a confirm click.

Start now with Phase 0.
