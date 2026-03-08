"""
Backtester for OptionsCLI strategies.

Replays historical earnings events to estimate how the strategy would have
performed over the past year. For each candidate it:

  1. Identifies the hypothetical entry window (~20-30 days before earnings)
  2. Fetches real historical price/IV data for that window
  3. Simulates exit at TARGET_PNL, EXIT_IV_RANK threshold, or pre-earnings,
     whichever comes first
  4. Reports P&L as IV expansion % (proxy for straddle value change)

Note: P&L is IV-proxy based, not Black-Scholes. It's a directional signal,
not a precise dollar figure. Real options P&L also depends on theta decay
and delta — treat this as a screening tool, not a financial model.
"""

from datetime import date, timedelta

from app.config.config import config
from app.data.massive import MassiveProvider
from app.models.models import PaperTrade


class Backtester:
    def __init__(self, market: MassiveProvider):
        self.market = market

    def run(
        self,
        tickers: list[str],
        historical_earnings: list[dict],
        lookback_days: int = 365,
    ) -> list[PaperTrade]:
        """
        Run backtest over historical earnings events.

        Args:
            tickers:             Watchlist to filter against.
            historical_earnings: List of {"ticker": str, "date": date} dicts
                                 from a past period.
            lookback_days:       How far back to simulate (default 1 year).
        """
        watchlist = set(tickers)
        cutoff = date.today() - timedelta(days=lookback_days)
        trades = []

        for e in historical_earnings:
            ticker, edate = e["ticker"], e["date"]
            if ticker not in watchlist:
                continue
            if edate < cutoff or edate >= date.today():
                continue

            print(f"  Backtesting {ticker} ({edate})...")
            trade = self._simulate(ticker, edate)
            if trade:
                trades.append(trade)

        return trades

    def _simulate(self, ticker: str, edate: date) -> PaperTrade | None:
        # Entry: DTE midpoint of TARGET_DTE_RANGE before earnings
        dte_mid = (config.TARGET_DTE_RANGE[0] + config.TARGET_DTE_RANGE[1]) // 2
        entry_date = edate - timedelta(days=dte_mid)
        exit_date  = edate - timedelta(days=config.EXIT_DAYS_BEFORE_EARNINGS)

        if entry_date >= exit_date:
            return None

        try:
            # Fetch full window with a warm-up buffer for IV rank calculation
            iv_series = self.market.get_historical_iv(
                ticker,
                start=entry_date - timedelta(days=30),
                end=exit_date,
            )
        except Exception:
            return None

        if len(iv_series) < 5:
            return None

        # Split warm-up from the actual trade window
        warmup = 30
        if len(iv_series) <= warmup:
            return None

        rank_series  = iv_series                     # full series for IV rank calc
        trade_series = iv_series[warmup:]            # actual trade window

        entry_iv      = trade_series[0]
        entry_iv_rank = self.market.get_iv_rank(rank_series, entry_iv)

        # Walk forward day-by-day to find the actual exit
        exit_iv          = trade_series[-1]
        exit_iv_rank     = self.market.get_iv_rank(rank_series, exit_iv)
        exit_reason      = "pre-earnings exit"
        actual_exit_date = exit_date  # may be overridden if early exit triggers

        for i, daily_iv in enumerate(trade_series[1:], start=1):
            pnl_so_far  = (daily_iv - entry_iv) / entry_iv if entry_iv > 0 else 0
            rank_so_far = self.market.get_iv_rank(rank_series, daily_iv)

            if pnl_so_far >= config.TARGET_PNL:
                exit_iv          = daily_iv
                exit_iv_rank     = rank_so_far
                exit_reason      = f"target hit ({config.TARGET_PNL*100:.0f}%)"
                actual_exit_date = entry_date + timedelta(days=i)
                break

            if rank_so_far >= config.EXIT_IV_RANK:
                exit_iv          = daily_iv
                exit_iv_rank     = rank_so_far
                exit_reason      = f"IV rank threshold ({config.EXIT_IV_RANK})"
                actual_exit_date = entry_date + timedelta(days=i)
                break

        pnl_pct = (exit_iv - entry_iv) / entry_iv if entry_iv > 0 else 0.0

        return PaperTrade(
            ticker=ticker,
            entry_date=entry_date,
            exit_date=actual_exit_date,
            entry_iv_rank=round(entry_iv_rank, 1),
            exit_iv_rank=round(exit_iv_rank, 1),
            pnl_pct=round(pnl_pct, 4),
            exit_reason=exit_reason,
        )

    @staticmethod
    def print_summary(trades: list[PaperTrade]) -> None:
        from app.util.display import Colors as C

        if not trades:
            print(f"\n{C.YELLOW}No backtest results.{C.RESET}")
            return

        winners  = [t for t in trades if t.pnl_pct > 0]
        losers   = [t for t in trades if t.pnl_pct <= 0]
        avg_pnl  = sum(t.pnl_pct for t in trades) / len(trades)
        win_rate = len(winners) / len(trades) * 100
        best     = max(trades, key=lambda t: t.pnl_pct)
        worst    = min(trades, key=lambda t: t.pnl_pct)

        print(f"\n{C.BOLD}{C.CYAN}BACKTEST SUMMARY{C.RESET}  {C.DIM}({len(trades)} trades){C.RESET}")
        print(C.CYAN + "=" * 52 + C.RESET)
        print(f"  Win Rate   {C.BOLD}{win_rate:.1f}%{C.RESET}   {C.GREEN}{len(winners)}W{C.RESET} / {C.RED}{len(losers)}L{C.RESET}")
        pnl_color = C.GREEN if avg_pnl > 0 else C.RED
        print(f"  Avg P&L    {pnl_color}{C.BOLD}{avg_pnl*100:+.2f}%{C.RESET}")
        print(f"  Best       {C.GREEN}{best.ticker}  {best.pnl_pct*100:+.2f}%{C.RESET}")
        print(f"  Worst      {C.RED}{worst.ticker}  {worst.pnl_pct*100:+.2f}%{C.RESET}")
        print()

        col = f"  {'TICKER':<8} {'ENTRY':>10} {'EXIT':>10} {'IVR-IN':>7} {'IVR-OUT':>7} {'P&L':>7}  REASON"
        print(C.DIM + col + C.RESET)
        print(C.DIM + "  " + "-" * 70 + C.RESET)

        for t in sorted(trades, key=lambda t: t.pnl_pct, reverse=True):
            pnl_str   = f"{t.pnl_pct*100:>+6.2f}%"
            color     = C.GREEN if t.pnl_pct > 0 else C.RED
            print(
                f"  {C.BOLD}{t.ticker:<8}{C.RESET}"
                f" {str(t.entry_date):>10} {str(t.exit_date):>10}"
                f" {t.entry_iv_rank:>7.1f} {t.exit_iv_rank:>7.1f}"
                f" {color}{pnl_str}{C.RESET}"
                f"  {C.DIM}{t.exit_reason}{C.RESET}"
            )
        print()