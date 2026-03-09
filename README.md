# OptionsCLI

A CLI tool for scanning options contracts that match pre-configured trading strategies, powered by [Massive.com](https://massive.com) market data and Alpha Vantage earnings data. Candidates are automatically saved to a local SQLite database, tracked with live price updates, AI-analyzed with Claude, and resolved post-earnings to build a live win/loss track record.

---

## Supported Strategies

### Pre-Earnings Long Straddle (`longStraddleEarnings`)

Buy both a call and put **ATM** 15–50 days before earnings to capture IV expansion — sell 1 day before earnings to avoid IV crush.

- Best when IV rank is **50–80** (elevated but not overpriced)
- Wins if IV expands from entry to exit, regardless of stock direction
- Ideal for: ORCL, ADBE, CRM, NOW — steady earnings movers with reliable IV expansion

**Filters:** DTE 15–50 · IV Rank 30–80 · Delta 0.35–0.65 · Volume ≥ 50 · OI ≥ 250 · Spread ≤ 15%

---

### Pre-Earnings Long Strangle (`longStrangleEarnings`)

Buy a slightly **OTM** call and put 15–50 days before earnings. Cheaper entry than the straddle, but requires a larger move to be profitable.

- Best for high-beta names where earnings moves are often violent (TSLA, COIN, NVDA)
- Lower cost = better risk/reward if the stock explodes in either direction
- Target delta: **0.20–0.40** on both legs (1–12% OTM)

**Filters:** Same as straddle but targets OTM strikes outside the ATM zone

---

### Event-Driven Long Straddle (`longStraddleEvent`)

Same thesis as the earnings straddle but the catalyst is discovered by Claude via web search rather than a fixed earnings calendar. Claude searches for upcoming dated events — Congressional votes, FDA decisions, Fed meetings, product launches, geopolitical flashpoints — maps them to affected tickers, then scans the options chain for exact contracts.

- Enter before the event, sell at peak IV just before the event resolves
- Best for binary events with a specific known date and uncertain outcome
- Claude re-discovers events on every scan so the list is always current

**Examples of events Claude finds:**
- Senate votes on energy/defense/pharma legislation → XOM, LMT, MRNA
- FDA PDUFA approval dates → biotech names
- Fed rate decisions → bank/REIT sector ETFs
- OPEC meeting dates → XOM, CVX, SLB
- Major product launches or investor days → AAPL, NVDA

**Requires:** `ANTHROPIC_API_KEY` in secrets.yaml (uses Claude Sonnet + web search, ~$0.05 per scan)

---

### Event-Driven Long Strangle (`longStrangleEvent`)

Same as `longStraddleEvent` but with OTM legs. Better for high-expected-move events where a large directional move is likely.

---

### IV Rank Screen (`ivRankScreen`)

A fast, lightweight scan of the full watchlist showing **current IV rank** for every ticker — no earnings required, no options chain fetched. Uses only historical price aggregates.

| IV Rank | Interpretation | Action |
|---|---|---|
| 80–100 | IV at yearly highs — very expensive options | Consider *selling* premium (short straddle) |
| 50–80 | Elevated — sweet spot for long straddle/strangle entry | Look for upcoming earnings catalyst |
| 30–50 | Moderate — options fairly priced | Monitor, wait for elevation |
| 0–30 | IV near yearly lows — cheap options | Calendar spreads, not straddles |

---

## Trade Lifecycle

### Workflow
```
1. findAll / findOne   ->  scan for candidates, auto-saved to DB as "pending"
2. pending             ->  view all open trades with tickers, strategies, option symbols
3. analyze             ->  quick AI check on all pending trades (fast, free)
4. analyze deep        ->  full AI research with live web search before entering a trade
5. sync                ->  update current stock prices + resolve post-earnings trades
6. history             ->  view full track record with IV move, P&L, win/loss
7. backtest            ->  win rate and avg P&L summary across resolved trades
```

### Status Lifecycle
| Status | Meaning |
|---|---|
| `pending` | Candidate found, event not yet passed — price updated on every `sync` |
| `resolved_win` | IV expanded from entry to exit |
| `resolved_loss` | IV contracted or flat from entry to exit |
| `unresolvable` | No IV or cost data available |
| `expired` | Options expired with no resolution |

### Win/Loss Logic

The strategy exits **1 day before the event/earnings date**. P&L is measured as % change in realized volatility from scan date to exit date:

```
pnl = (iv_at_exit - iv_at_entry) / iv_at_entry * 100
```

> **Note:** On the $29 Massive plan, bid/ask quotes are not returned — `Est. Cost` shows as `n/a`. Upgrade to Stocks Advanced ($199) for exact P&L calculation.

---

## AI Analysis

### `analyze` — Fast (Haiku, training knowledge)
- Model: Claude Haiku · No web search · ~10s/ticker · fraction of a cent
- Use daily as a routine check on pending trades

### `analyze deep` — Deep (Sonnet + live web search)
- Model: Claude Sonnet · Live web search · ~60s/ticker · ~$0.02/ticker
- Use the day before you're considering entering a trade

**Example output:**
```
  ORCL  earnings 2026-03-10 (3d)
  Signal: Strong  Confidence: 78%  Action: Enter  IV expansion likely
  Oracle reports Monday. Strong guidance expectations after AWS/Azure beat.

  Catalysts:
    + Cloud revenue acceleration expected (OCI gaining share)
    + Analyst upgrades from MS and GS in past 2 weeks
  Risks:
    - Dollar strength compresses international revenue
    - IV rank already elevated, limited further expansion room
```

---

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create a secrets YAML file**
```yaml
MASSIVE_API_KEY:    your_massive_api_key_here
ALPHA_API_KEY:      your_alphavantage_key_here
ANTHROPIC_API_KEY:  sk-ant-...                    # required for analyze, analyze deep, and event strategies
TRADE_DB_PATH:      /path/to/your/trades.db       # optional, defaults to app/data/history/trades.db
```

**3. Set the environment variable**
```bash
export SECRETS_FILE_PATH=/path/to/secrets.yaml
```

Add to `~/.zshrc` to make it permanent:
```bash
echo 'export SECRETS_FILE_PATH="/path/to/secrets.yaml"' >> ~/.zshrc
source ~/.zshrc
```

**4. Run the CLI**
```bash
python3 -m app.cli
```

**5. Keep sensitive files out of git**
```bash
echo "app/data/history/trades.db" >> .gitignore
echo "**/secrets.yaml" >> .gitignore
git rm --cached app/data/history/trades.db 2>/dev/null || true
git rm --cached secrets.yaml 2>/dev/null || true
git commit -m "untrack sensitive files"
```

---

## Commands

| Command | Description |
|---|---|
| `findAll longStraddleEarnings` | Scan full watchlist — ATM straddle, earnings-driven |
| `findAll longStrangleEarnings` | Scan full watchlist — OTM strangle, earnings-driven |
| `findAll longStraddleEvent` | Claude discovers events + scans ATM straddle contracts |
| `findAll longStrangleEvent` | Claude discovers events + scans OTM strangle contracts |
| `findAll ivRankScreen` | IV rank sweep across full watchlist |
| `findOne longStraddleEarnings AAPL` | Scan a single ticker with any strategy |
| `pending` | Show all open trades — ticker, strategy, earnings date, option symbols |
| `analyze` | Quick AI analysis — Haiku, training knowledge (~10s/ticker) |
| `analyze deep` | Full AI research — Sonnet + live web search (~60s/ticker, ~$0.02/ticker) |
| `sync` | Update current prices + resolve post-event/earnings trades |
| `history` | Show all saved trades and win/loss stats |
| `backtest longStraddleEarnings` | Win rate and P&L summary from resolved trades |
| `watchlist` | Show configured watchlist tickers |
| `help` | Show all commands |
| `exit` | Quit |

---

## Data Sources & API Keys

| Data | Source | Key | Cost |
|---|---|---|---|
| Stock prices + options chain | Massive.com | `MASSIVE_API_KEY` | $29/mo |
| Live bid/ask quotes | Massive.com | `MASSIVE_API_KEY` | $199/mo |
| Earnings calendar | Alpha Vantage | `ALPHA_API_KEY` | Free |
| AI analysis (fast) | Claude Haiku | `ANTHROPIC_API_KEY` | ~$0.0003/ticker |
| AI analysis (deep) | Claude Sonnet + web search | `ANTHROPIC_API_KEY` | ~$0.02/ticker |
| Event discovery | Claude Sonnet + web search | `ANTHROPIC_API_KEY` | ~$0.05/scan |

Get your Anthropic API key at **console.anthropic.com**. The $5 starter credit is a one-time prepaid balance — API calls stop if you run out unless you manually top up or enable auto-reload in the console.

---

## Project Structure

```
app/
├── cli.py                  Entry point and command router
├── config/
│   └── config.py           Strategy parameters and watchlist
├── core/
│   └── app.py              App orchestration and strategy map
├── analysis/
│   ├── analyzer.py         AI trade analysis (Haiku fast / Sonnet deep)
│   └── event_scanner.py    Claude-powered event discovery (Sonnet + web search)
├── data/
│   ├── provider.py         Abstract base provider
│   ├── massive.py          Massive.com market data
│   ├── alpha_vantage.py    Earnings calendar (12hr cache)
│   ├── trade_store.py      SQLite trade history DB
│   └── cache/
│       └── earnings_cache.csv
├── models/
│   └── models.py           Pydantic data models
├── strategy/
│   ├── strategy.py         Abstract base strategy
│   ├── iv_straddle.py      Earnings straddle (ATM)
│   ├── iv_strangle.py      Earnings strangle (OTM)
│   ├── event_straddle.py   Event-driven straddle (ATM)
│   ├── event_strangle.py   Event-driven strangle (OTM)
│   └── iv_rank_screen.py   IV rank watchlist screen
└── util/
    └── display.py          Terminal output and history formatting
```

---

## Notes

- Earnings data is cached locally for 12 hours — re-fetched automatically when stale
- Historical IV uses annualized realized volatility (20-day rolling log returns) — same scale as options IV
- `ivRankScreen` does not fetch options chains — fast and cheap on API calls
- All DB schema changes are auto-migrated on startup — existing databases update silently
- `trades.db` and `secrets.yaml` should both be in `.gitignore`
- Up/down arrow key history is supported at the `options>` prompt (macOS/Linux)
- Anthropic API rate limits improve automatically as your account accumulates spend
- This tool is for research and screening purposes only, not financial advice