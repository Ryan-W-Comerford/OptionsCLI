# OptionsCLI

A CLI tool for scanning options contracts that match pre-configured trading strategies, powered by [Massive.com](https://massive.com) market data and Alpha Vantage earnings data. Candidates are automatically saved to a local SQLite database and can be resolved post-earnings to build a live win/loss track record.

## Supported Strategies

### Pre-Earnings Long Straddle (`longStraddleIV`)

Buy both a call and put ATM 15–50 days before earnings to capture IV expansion — then sell before earnings day to avoid IV crush.

**Filters applied:**
- Target DTE: 15–50 days
- IV Rank: 30–80 (elevated but not overpriced)
- Delta within 0.35–0.65 (near ATM; skipped if greeks unavailable)
- Volume ≥ 50, Open Interest ≥ 250 (liquid contracts only)
- Bid/Ask spread ≤ 15% (skipped if no quote data)
- ATM proximity: within 2% of spot price

## Setup

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Create a secrets YAML file**
```yaml
POLYGON_API_KEY: your_massive_api_key_here
ALPHA_API_KEY: your_alphavantage_key_here
TRADE_DB_PATH: /path/to/your/trades.db   # optional — defaults to app/data/history/trades.db
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

## Commands

| Command | Description |
|---|---|
| `findAll longStraddleIV` | Scan full watchlist for candidates |
| `findOne longStraddleIV AAPL` | Scan a single ticker |
| `resolve` | Resolve pending trades post-earnings (win/loss) |
| `history` | Show all saved trades and win/loss stats |
| `backtest longStraddleIV` | Summarise win/loss stats from resolved trade history |
| `watchlist` | Show configured watchlist |
| `help` | Show all commands |
| `exit` | Quit |

## Trade History Workflow

OptionsCLI maintains a local SQLite database of every candidate found, with a simple post-earnings resolution step:

```
1. findAll / findOne   →  candidates auto-saved as "pending"
2. (wait for earnings)
3. resolve             →  fetches post-earnings price, marks win/loss
4. history             →  view full track record and stats
```

**Status lifecycle:**
| Status | Meaning |
|---|---|
| `pending` | Candidate found, earnings not yet passed |
| `resolved_win` | Post-earnings move exceeded straddle cost (breakeven) |
| `resolved_loss` | Move did not cover the cost |
| `unresolvable` | No cost data available (bid/ask=0 on current plan) — move stored, win/loss unknown |
| `expired` | Options expired with no resolution |

**Win/loss logic:** A trade is a win if the stock's absolute price move (%) after earnings exceeds the breakeven percentage `(total_cost / stock_price_at_scan) * 100`. This requires live bid/ask data at scan time — if quotes are unavailable (`Est. Cost: n/a`), trades are marked `unresolvable` and you can resolve manually.

## Data Sources & Plan Requirements

| Data | Endpoint | Minimum Plan |
|---|---|---|
| Stock price (snapshot) | Massive.com Stocks Starter | $29/mo |
| Historical price (aggregates) | Massive.com Stocks Starter | $29/mo |
| Options chain + greeks | Massive.com Options Starter | $29/mo |
| Live bid/ask quotes | Massive.com Stocks Advanced | $199/mo |
| Earnings calendar | Alpha Vantage Free | Free |

> **Note:** On the $29 Options plan, bid/ask quotes are not returned — `Est. Cost` will show as `n/a`. The scanner still works for identifying candidates via IV rank and greeks. Upgrade to Stocks Advanced ($199) for live quote data and accurate cost/PnL tracking.

## Project Structure

```
app/
├── cli.py                  Entry point and command router
├── config/
│   └── config.py           Strategy parameters and watchlist
├── core/
│   └── app.py              App orchestration
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
│   └── iv_straddle.py      Long straddle implementation
└── util/
    └── display.py          Terminal output and history formatting
```

## Notes

- Earnings data is cached locally for 12 hours — re-fetched automatically when stale
- Historical IV is computed from annualized realized volatility (20-day rolling log returns) to match the same scale as options implied volatility
- Backtest reads from the trade history DB — results improve as more trades are resolved over time
- Up/down arrow key history is supported at the `options>` prompt (macOS/Linux)
- This tool is for research and screening purposes only, not financial advice