# OptionsCLI

A CLI tool for scanning options contracts that match pre-configured trading strategies, powered by [Massive.com](https://massive.com) market data and Alpha Vantage earnings data. Candidates are automatically saved to a local SQLite database, tracked with live price updates, AI-analyzed with Claude, and resolved post-earnings to build a live win/loss track record.

---

## Supported Strategies

### Pre-Earnings Long Straddle (`longStraddleIV`)

Buy both a call and put **ATM** 15–50 days before earnings to capture IV expansion — sell 1 day before earnings to avoid IV crush.

- Best when IV rank is **50–80** (elevated but not overpriced)
- Wins if IV expands from entry to exit, regardless of stock direction
- Ideal for: ORCL, ADBE, CRM, NOW — steady earnings movers with reliable IV expansion

**Filters:** DTE 15–50 · IV Rank 30–80 · Delta 0.35–0.65 · Volume ≥ 50 · OI ≥ 250 · Spread ≤ 15%

---

### Pre-Earnings Long Strangle (`longStrangleIV`)

Buy a slightly **OTM** call and put 15–50 days before earnings. Cheaper entry than the straddle, but requires a larger move to be profitable.

- Best for high-beta names where earnings moves are often violent (TSLA, COIN, NVDA)
- Lower cost = better risk/reward if the stock explodes in either direction
- Target delta: **0.20–0.40** on both legs (1–12% OTM)

**Filters:** Same as straddle but targets OTM strikes outside the ATM zone

---

### IV Rank Screen (`ivRankScreen`)

A fast, lightweight scan of the full watchlist showing **current IV rank** for every ticker — no earnings required, no options chain fetched. Uses only historical price aggregates.

| IV Rank | Interpretation | Action |
|---|---|---|
| 80–100 | IV at yearly highs — very expensive options | Consider *selling* premium (short straddle) |
| 50–80 | Elevated — sweet spot for long straddle/strangle entry | Look for upcoming earnings catalyst |
| 30–50 | Moderate — options fairly priced | Monitor, wait for elevation |
| 0–30 | IV near yearly lows — cheap options | Calendar spreads, not straddles |

Use this screen daily to spot opportunities. The best straddle setups appear on **both** the IV screen (rank 50–80) and the straddle scanner (upcoming earnings).

---

## Trade Lifecycle

OptionsCLI tracks every candidate from discovery through resolution.

### Workflow
```
1. findAll / findOne   ->  scan for candidates, auto-saved to DB as "pending"
2. pending             ->  view all open trades with tickers, strategies, option symbols
3. analyze             ->  AI analysis of pending trades (Claude + web search)
4. sync                ->  update current stock prices + resolve post-earnings trades
5. history             ->  view full track record with IV move, P&L, win/loss
6. backtest            ->  win rate and avg P&L summary across resolved trades
```

### Status Lifecycle
| Status | Meaning |
|---|---|
| `pending` | Candidate found, earnings not yet passed — price updated on every `sync` |
| `resolved_win` | IV expanded from entry to exit (1 day before earnings) |
| `resolved_loss` | IV contracted or flat from entry to exit |
| `unresolvable` | No IV or cost data available |
| `expired` | Options expired with no resolution |

### Win/Loss Logic

The strategy exits **1 day before earnings** to capture IV expansion and avoid IV crush. P&L is measured as the % change in realized volatility from scan date to exit date:

```
pnl = (iv_at_exit - iv_at_entry) / iv_at_entry * 100
```

If IV rose 20% from entry to exit (e.g. 0.35 -> 0.42), that's a +20% win. Falls back to stock move vs breakeven if IV data is unavailable.

> **Note:** On the $29 Massive plan, bid/ask quotes are not returned — `Est. Cost` shows as `n/a`. Upgrade to Stocks Advanced ($199) for live quote data and exact P&L calculation.

---

## AI Analysis (`analyze`)

The `analyze` command passes all pending trades to Claude with web search enabled. For each trade, Claude searches for recent news, analyst sentiment, historical earnings reactions, and macro conditions — then returns a structured verdict.

**Example output:**
```
  ORCL  earnings 2026-03-10 (3d)
  Signal: Strong  Confidence: 78%  Action: Enter  IV expansion likely
  Oracle reports Monday. Strong guidance expectations after AWS/Azure beat.
  Options market pricing a 6.2% move vs 5-yr avg of 7.8%.

  Catalysts:
    + Cloud revenue acceleration expected (OCI gaining share)
    + Analyst upgrades from MS and GS in past 2 weeks

  Risks:
    - Dollar strength compresses international revenue
    - IV rank already elevated, limited further expansion room
```

**Fields returned per trade:** signal (Strong / Moderate / Weak / Avoid), confidence %, summary, catalysts, risks, IV expansion likelihood, suggested action (Enter / Monitor / Skip).

Requires `ANTHROPIC_API_KEY` in `secrets.yaml`. Each ticker costs roughly $0.01–0.02 in API usage.

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
ANTHROPIC_API_KEY:  sk-ant-...                    # required for analyze command
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

**5. Keep `trades.db` out of git**

Add to `.gitignore`, then untrack if already committed:
```bash
echo "app/data/history/trades.db" >> .gitignore
git rm --cached app/data/history/trades.db
git commit -m "untrack trades.db"
```

---

## Commands

| Command | Description |
|---|---|
| `findAll longStraddleIV` | Scan full watchlist — ATM straddle candidates |
| `findAll longStrangleIV` | Scan full watchlist — OTM strangle candidates |
| `findAll ivRankScreen` | IV rank sweep across full watchlist |
| `findOne longStraddleIV AAPL` | Scan a single ticker with any strategy |
| `pending` | Show all open trades — ticker, strategy, earnings date, option symbols |
| `analyze` | AI analysis of all pending trades (Claude + web search) |
| `sync` | Update current prices + resolve post-earnings trades |
| `history` | Show all saved trades and win/loss stats |
| `backtest longStraddleIV` | Win rate and P&L summary from resolved trades |
| `watchlist` | Show configured watchlist tickers |
| `help` | Show all commands |
| `exit` | Quit |

---

## Data Sources & API Keys

| Data | Source | Key | Min Plan |
|---|---|---|---|
| Stock prices + options chain | Massive.com | `MASSIVE_API_KEY` | $29/mo |
| Live bid/ask quotes | Massive.com | `MASSIVE_API_KEY` | $199/mo |
| Earnings calendar | Alpha Vantage | `ALPHA_API_KEY` | Free |
| AI trade analysis | Anthropic Claude | `ANTHROPIC_API_KEY` | Pay-per-use (~$0.01/ticker) |

Get your Anthropic API key at **console.anthropic.com** — new accounts receive free starter credits.

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
│   └── analyzer.py         AI trade analysis via Claude API + web search
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
│   ├── iv_straddle.py      Long straddle (ATM) implementation
│   ├── iv_strangle.py      Long strangle (OTM) implementation
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
- `trades.db` should be in `.gitignore` — contains personal trade history
- Up/down arrow key history is supported at the `options>` prompt (macOS/Linux)
- This tool is for research and screening purposes only, not financial advice