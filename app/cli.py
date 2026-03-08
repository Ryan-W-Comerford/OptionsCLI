try:
    import readline  # noqa: F401 — enables up/down arrow history in input() (Unix/macOS only)
except ImportError:
    pass  # Windows — degrades gracefully, no history
import warnings
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

from app.core.app import OptionsApp
from app.util.display import Colors as C, print_candidates, print_history

BANNER = C.CYAN + r"""
 ██████╗ ██████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗ ██████╗██╗     ██╗
██╔═══██╗██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝██╔════╝██║     ██║
██║   ██║██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║███████╗██║     ██║     ██║
██║   ██║██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║╚════██║██║     ██║     ██║
╚██████╔╝██║        ██║   ██║╚██████╔╝██║ ╚████║███████║╚██████╗███████╗██║
 ╚═════╝ ╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝╚══════╝╚═╝
""" + C.RESET

app = OptionsApp()


def _save_candidates(candidates, strategy_name: str) -> None:
    """Auto-save all candidates to the trade DB."""
    saved = 0
    for c in candidates:
        try:
            price = app.market.get_stock_price(c.ticker)
            inserted = app.store.save_candidate(c, stock_price=price)
            if inserted:
                saved += 1
        except Exception as e:
            print(f"  {C.DIM}Warning: could not save {c.ticker} to DB: {e}{C.RESET}")
    if saved:
        print(f"  {C.DIM}Saved {saved} new candidate(s) to trade history.{C.RESET}")


def start_findall(commands: list[str]) -> None:
    if len(commands) != 2:
        raise ValueError("Usage: findAll <strategy>")
    strategy = app.get_strategy(commands[1])
    count = app.upcoming_earnings_count()
    print(f"\n{C.DIM}  Scanning {count} upcoming earnings events on watchlist...{C.RESET}")
    candidates = strategy.generate_candidates(app.market, app.earnings)
    print_candidates(candidates)
    if candidates:
        _save_candidates(candidates, commands[1])


def start_findone(commands: list[str]) -> None:
    if len(commands) != 3:
        raise ValueError("Usage: findOne <strategy> <ticker>")
    strategy = app.get_strategy(commands[1])
    ticker = commands[2].upper()
    print(f"\n{C.DIM}  Scanning {ticker}...{C.RESET}")
    candidates = strategy.generate_candidates(app.market, app.earnings, ticker_filter=ticker)
    print_candidates(candidates)
    if candidates:
        _save_candidates(candidates, commands[1])


def start_resolve(_commands: list[str]) -> None:
    """Fetch post-earnings prices for all pending trades and resolve them."""
    pending = app.store.get_pending()
    if not pending:
        print(f"\n  {C.DIM}No pending trades to resolve.{C.RESET}\n")
        return

    from datetime import date
    today = date.today()
    resolved = 0

    print(f"\n{C.DIM}  Resolving {len(pending)} pending trade(s)...{C.RESET}\n")
    for trade in pending:
        edate = date.fromisoformat(trade["earnings_date"])
        if edate >= today:
            print(f"  {C.DIM}{trade['ticker']} — earnings on {edate}, not yet passed. Skipping.{C.RESET}")
            continue
        try:
            current_price = app.market.get_stock_price(trade["ticker"])
            status = app.store.resolve_trade(
                trade_id=trade["id"],
                stock_price_at_earnings=current_price,
                stock_price_at_scan=trade["stock_price_at_scan"],
                total_cost=trade["total_cost"],
            )
            move = abs(current_price - trade["stock_price_at_scan"]) / trade["stock_price_at_scan"] * 100
            icon = "✅" if status == "resolved_win" else ("❓" if status == "unresolvable" else "❌")
            print(f"  {icon} {C.BOLD}{trade['ticker']}{C.RESET}  move={move:.1f}%  status={status}")
            resolved += 1
        except Exception as e:
            print(f"  {C.YELLOW}Could not resolve {trade['ticker']}: {e}{C.RESET}")

    print(f"\n  {C.DIM}Resolved {resolved} trade(s).{C.RESET}\n")


def start_history(_commands: list[str]) -> None:
    """Print all trades and win/loss stats."""
    trades = app.store.get_all()
    stats  = app.store.get_stats()
    print_history(trades, stats)


def start_backtest(commands: list[str]) -> None:
    if len(commands) != 2:
        raise ValueError("Usage: backtest <strategy>")
    from app.backtest import Backtester
    from app.config.config import config

    _ = app.get_strategy(commands[1])
    print(f"\n{C.DIM}  Loading historical earnings and running backtest...{C.RESET}")

    from datetime import datetime
    all_rows = app.earnings._read_cache() if app.earnings._cache_is_fresh() \
        else app.earnings._fetch_and_cache()

    historical = []
    for row in all_rows:
        try:
            edate = datetime.fromisoformat(row["reportDate"]).date()
            historical.append({"ticker": row["symbol"], "date": edate})
        except (KeyError, ValueError):
            continue

    backtester = Backtester(app.market)
    trades = backtester.run(config.STOCKS, historical)
    Backtester.print_summary(trades)


def start_watchlist(_commands: list[str]) -> None:
    from app.config.config import config
    tickers = sorted(config.STOCKS)
    print(f"\n{C.BOLD}  Watchlist{C.RESET}  {C.DIM}({len(tickers)} tickers){C.RESET}")
    print(f"  {C.DIM}{'─' * 40}{C.RESET}")
    row = "  "
    for i, t in enumerate(tickers, 1):
        row += f"{C.BOLD}{t:<7}{C.RESET}"
        if i % 6 == 0:
            print(row)
            row = "  "
    if row.strip():
        print(row)
    print()


run_map = {
    "findAll":   start_findall,
    "findOne":   start_findone,
    "resolve":   start_resolve,
    "history":   start_history,
    "backtest":  start_backtest,
    "watchlist": start_watchlist,
}

HELP_TEXT = f"""
{C.BOLD}  Commands:{C.RESET}
    {C.CYAN}findAll{C.RESET}   <strategy>            Scan all watchlist tickers
    {C.CYAN}findOne{C.RESET}   <strategy> <ticker>   Scan a single ticker
    {C.CYAN}resolve{C.RESET}                         Resolve pending trades post-earnings
    {C.CYAN}history{C.RESET}                         Show all trades and win/loss stats
    {C.CYAN}backtest{C.RESET}  <strategy>            Replay historical earnings (past 1yr)
    {C.CYAN}watchlist{C.RESET}                       Show configured watchlist tickers
    {C.CYAN}help{C.RESET}                            Show this message
    {C.CYAN}exit{C.RESET}                            Quit

{C.BOLD}  Available strategies:{C.RESET}
    {C.YELLOW}longStraddleIV{C.RESET}  Pre-earnings IV expansion straddle
"""

if __name__ == "__main__":
    print(BANNER)
    print(f"  {C.DIM}Type 'help' for commands or 'exit' to quit{C.RESET}\n")

    while True:
        try:
            raw = input(f"{C.CYAN}options>{C.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.DIM}  Goodbye!{C.RESET}")
            break

        if not raw:
            continue

        if raw in ("exit", "quit"):
            print(f"\n{C.DIM}  Goodbye!{C.RESET}\n")
            break

        if raw == "help":
            print(HELP_TEXT)
            continue

        commands = raw.split()
        run_type = commands[0]

        if run_type not in run_map:
            print(f"\n  {C.YELLOW}Unknown command '{run_type}'. Type 'help' for options.{C.RESET}\n")
            continue

        try:
            run_map[run_type](commands)
        except Exception as e:
            print(f"\n  {C.RED}Error: {e}{C.RESET}\n")