try:
    import readline  # noqa: F401 — enables up/down arrow history in input() (Unix/macOS only)
except ImportError:
    pass  # Windows — degrades gracefully, no history
import warnings
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

from app.core.app import OptionsApp
from app.config.config import config
from app.util.display import Colors as C, print_candidates, print_strangle_candidates, print_iv_screen, print_history

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
            inserted = app.store.save_candidate(c, stock_price=price, strategy=strategy_name)
            if inserted:
                saved += 1
        except Exception as e:
            print(f"  {C.DIM}Warning: could not save {c.ticker} to DB: {e}{C.RESET}")
    if saved:
        print(f"  {C.DIM}Saved {saved} new candidate(s) to trade history.{C.RESET}")


def _display(strategy_name: str, candidates: list) -> None:
    """Route candidates to the correct display function by strategy."""
    if strategy_name == "longStrangleIV":
        print_strangle_candidates(candidates)
    elif strategy_name == "ivRankScreen":
        print_iv_screen(candidates)
    else:
        print_candidates(candidates)


def start_findall(commands: list[str]) -> None:
    if len(commands) != 2:
        raise ValueError("Usage: findAll <strategy>")
    strategy = app.get_strategy(commands[1])
    if commands[1] == "ivRankScreen":
        print(f"\n{C.DIM}  Checking IV rank across {len(config.STOCKS)} watchlist tickers...{C.RESET}")
        candidates = strategy.generate_candidates(app.market, app.earnings)
    else:
        count = app.upcoming_earnings_count()
        print(f"\n{C.DIM}  Scanning {count} upcoming earnings events on watchlist...{C.RESET}")
        candidates = strategy.generate_candidates(app.market, app.earnings)
    _display(commands[1], candidates)
    if candidates and commands[1] != "ivRankScreen":
        _save_candidates(candidates, commands[1])


def start_findone(commands: list[str]) -> None:
    if len(commands) != 3:
        raise ValueError("Usage: findOne <strategy> <ticker>")
    strategy = app.get_strategy(commands[1])
    ticker = commands[2].upper()
    print(f"\n{C.DIM}  Scanning {ticker}...{C.RESET}")
    candidates = strategy.generate_candidates(app.market, app.earnings, ticker_filter=ticker)
    _display(commands[1], candidates)
    if candidates and commands[1] != "ivRankScreen":
        _save_candidates(candidates, commands[1])


def start_resolve(_commands: list[str]) -> None:
    """
    Resolve pending trades using IV expansion as the P&L proxy.

    Exit point = 2 trading days before earnings (when IV is near its peak).
    This matches the actual strategy — we sell before earnings to avoid IV crush,
    not after. P&L = % change in realized vol from scan date to exit date.

    Falls back to stock move vs breakeven if IV data is unavailable.
    """
    pending = app.store.get_pending()
    if not pending:
        print(f"\n  {C.DIM}No pending trades to resolve.{C.RESET}\n")
        return

    from datetime import date, timedelta
    today = date.today()
    resolved = 0

    print(f"\n{C.DIM}  Resolving {len(pending)} pending trade(s)...{C.RESET}\n")
    for trade in pending:
        edate = date.fromisoformat(trade["earnings_date"])
        scan_date = date.fromisoformat(trade["scan_date"])

        # Need earnings to have passed so we can look back at the exit window
        if edate >= today:
            print(f"  {C.DIM}{trade['ticker']} — earnings on {edate}, not yet passed. Skipping.{C.RESET}")
            continue

        try:
            # Exit = 2 trading days before earnings (approximate: 2 calendar days back,
            # get_closing_price has a 4-day forward buffer so weekends are handled)
            exit_date = edate - timedelta(days=2)

            exit_price = app.market.get_closing_price(trade["ticker"], exit_date)
            if exit_price is None:
                print(f"  {C.YELLOW}{trade['ticker']} — no exit price found around {exit_date}. Skipping.{C.RESET}")
                continue

            # IV at entry — fetch realized vol window ending on scan date
            iv_at_entry = app.market.get_iv_as_of(trade["ticker"], as_of=scan_date)
            # IV at exit — fetch realized vol window ending on exit date
            iv_at_exit  = app.market.get_iv_as_of(trade["ticker"], as_of=exit_date)

            status = app.store.resolve_trade(
                trade_id=trade["id"],
                iv_at_entry=iv_at_entry or 0.0,
                iv_at_exit=iv_at_exit or 0.0,
                total_cost=trade["total_cost"] or 0.0,
                stock_price_at_exit=exit_price,
                stock_price_at_scan=trade["stock_price_at_scan"] or 0.0,
            )

            # Display
            iv_str = (
                f"IV {iv_at_entry:.3f} → {iv_at_exit:.3f}"
                if iv_at_entry and iv_at_exit
                else "no IV data"
            )
            icon = "✅" if status == "resolved_win" else ("❓" if status == "unresolvable" else "❌")
            print(f"  {icon} {C.BOLD}{trade['ticker']}{C.RESET}  exit={exit_date}  {iv_str}  status={status}")
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
    _ = app.get_strategy(commands[1])  # validate strategy name
    print(f"\n{C.DIM}  Running backtest from trade history DB...{C.RESET}")
    trades = app.store.get_all()
    resolved = [t for t in trades if t["status"] in ("resolved_win", "resolved_loss")]
    if not resolved:
        print(f"\n  {C.YELLOW}No resolved trades yet — run 'resolve' after earnings pass to populate.{C.RESET}\n")
        return
    from app.util.display import print_backtest
    print_backtest(resolved)


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
    {C.YELLOW}longStraddleIV{C.RESET}  Pre-earnings ATM straddle (buy call + put at strike)
    {C.YELLOW}longStrangleIV{C.RESET}  Pre-earnings OTM strangle (cheaper, needs bigger move)
    {C.YELLOW}ivRankScreen{C.RESET}   IV rank alert across full watchlist (no earnings needed)
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