# OptionsCLI

A CLI tool for scanning options contracts that match pre-configured trading strategies, powered by [Massive.com](https://massive.com) market data and Alpha Vantage earnings data. Candidates are automatically saved to a local SQLite database and can be resolved post-earnings to build a live win/loss track record.

## Supported Strategies

### Pre-Earnings Long Straddle (`longStraddleIV`)

Buy both a call and put **ATM** 15–50 days before earnings to capture IV expansion — sell before earnings day to avoid IV crush.

- Best when IV rank is **50–80** (elevated but not overpriced)
- Wins if the stock moves enough in either direction to cover the combined premium
- Ideal for: ORCL, ADBE, CRM, NOW — steady earnings movers with reliable IV expansion

**Filters:** DTE 15–50 · IV Rank 30–80 · Delta 0.35–0.65 · Volume ≥ 50 · OI ≥ 250 · Spread ≤ 15%

---

### Pre-Earnings Long Strangle (`longStrangleIV`)

Buy a slightly **OTM** call and put 15–50 days before earnings. Cheaper entry than the straddle, but requires a larger move to be profitable.

- Best for high-beta names where earnings moves are often violent (TSLA, COIN, NVDA)
- Lower cost = better risk/reward if the stock explodes in either direction
- Target delta: **0.20–0.40** on both legs (outside ATM zone)

**Filters:** Same as straddle but targets OTM strikes (1–12% away from spot)

---

### IV Rank Screen (`ivRankScreen`)

A fast, lightweight scan of the full watchlist showing **current IV rank** for every ticker — no earnings required, no options chain fetched. Uses only historical price aggregates.

| IV Rank | Interpretation | Action |
|---|---|---|
| 80–100 | IV at yearly highs — very expensive options | Consider *selling* premium (short straddle) |
| 50–80 | Elevated — sweet spot for long straddle/strangle entry | Look for upcoming earnings catalyst |
| 30–50 | Moderate — options fairly priced | Monitor, wait for elevation |
| 0–30 | IV near yearly lows — cheap options | Calendar spreads, not straddles |

Use this screen daily to spot opportunities across the watchlist. The best straddle setups appear on **both** the IV screen (rank 50–80) and the straddle scanner (upcoming earnings).

---

## Trade History & Resolution

OptionsCLI tracks every candidate found and resolves win/loss post-earnings automatically.

### Workflow
```
1. findAll / findOne   →  candidates auto-saved as "pending"
2. (wait for earnings to pass)
3. resolve             →  fetches earnings-day closing price, marks win/loss
4. history             →  view full track record with move %, breakeven, P&L
5. backtest            →  win rate and avg P&L summary across resolved trades
```

### Status Lifecycle
| Status | Meaning |
|---|---|
| `pending` | Candidate found, earnings not yet passed |
| `resolved_win` | Post-earnings move exceeded straddle cost (breakeven) |
| `resolved_loss` | Move did not cover the cost |
| `unresolvable` | No cost data (bid/ask=0 on current plan) — move stored, win/loss unknown |
| `expired` | Options expired with no resolution |

### Win/Loss Logic
A trade is a **win** if the stock's absolute price move after earnings exceeds the breakeven:
```
breakeven_pct = (total_cost / stock_price_at_scan) * 100
pnl = actual_move_pct - breakeven_pct
```
`resolve` always uses the **earnings day closing price** from historical data — not the live price — so it's accurate regardless of when you run it.

> **Note:** On the $29 Options plan, bid/ask quotes are not returned — `Est. Cost` shows as `n/a` and trades resolve as `unresolvable`. You can manually set the cost via SQLite to get a real win/loss. Upgrade to Stocks Advanced ($199) for live quote data.

---

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create a secrets YAML file**
```yaml
POLYGON_API_KEY: your_massive_api_key_here
ALPHA_API_KEY:   your_alphavantage_key_here
TRADE_DB_PATH:   /path/to/your/trades.db   # optional — defaults to app/data/history/trades.db
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

---

## Commands

| Command | Description |
|---|---|
| `findAll longStraddleIV` | Scan full watchlist — ATM straddle candidates |
| `findAll longStrangleIV` | Scan full watchlist — OTM strangle candidates |
| `findAll ivRankScreen` | IV rank sweep across full watchlist |
| `findOne longStraddleIV AAPL` | Scan a single ticker with any strategy |
| `resolve` | Resolve pending trades post-earnings (win/loss) |
| `history` | Show all saved trades and win/loss stats |
| `backtest longStraddleIV` | Win rate and P&L summary from resolved trades |
| `watchlist` | Show configured watchlist tickers |
| `help` | Show all commands |
| `exit` | Quit |

---

## Data Sources & Plan Requirements

| Data | Endpoint | Minimum Plan |
|---|---|---|
| Stock price (snapshot) | Massive.com Stocks | $29/mo |
| Historical price (aggregates) | Massive.com Stocks | $29/mo |
| Options chain + greeks | Massive.com Options | $29/mo |
| Live bid/ask quotes | Massive.com Stocks Advanced | $199/mo |
| Earnings calendar | Alpha Vantage Free | Free |

---

## Project Structure

```
app/
├── cli.py                  Entry point and command router
├── config/
│   └── config.py           Strategy parameters and watchlist
├── core/
│   └── app.py              App orchestration and strategy map
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
- The `strategy` column in the DB is auto-migrated on startup — existing DBs are updated automatically
- Up/down arrow key history is supported at the `options>` prompt (macOS/Linux)
- This tool is for research and screening purposes only, not financial advice