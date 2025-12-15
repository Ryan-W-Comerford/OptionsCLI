from app.data.polygon import PolygonProvider
from app.strategy.strategy import Strategy
from app.models.models import PaperTrade, StraddleCandidate
from app.config.config import config
from datetime import date, timedelta

class LongStraddleIVStrategy(Strategy):
    def generate_candidates(self, provider: PolygonProvider):
        candidates = []
        for e in provider.get_upcoming_earnings(config.EARNINGS_LOOKAHEAD_DAYS):
            ticker, edate = e["ticker"], e["date"]
            spot = provider.get_stock_price(ticker)
            chain = provider.get_option_chain(ticker)

            calls, puts = [], []
            for o in chain:
                dte = (o.expiration - date.today()).days
                if config.TARGET_DTE_RANGE[0] <= dte <= config.TARGET_DTE_RANGE[1]:
                    if abs(o.strike - spot) / spot < 0.02:
                        (calls if o.option_type == "call" else puts).append(o)

            if not calls or not puts:
                continue

            call = min(calls, key=lambda x: abs(x.delta - 0.5))
            put = min(puts, key=lambda x: abs(x.delta + 0.5))

            theta = abs(call.theta + put.theta)
            if theta == 0:
                continue

            if (call.vega + put.vega) / theta < config.MIN_VEGA_THETA_RATIO:
                continue

            iv_hist = provider.get_historical_iv(ticker, date.today()-timedelta(days=252), date.today())
            iv_rank = provider.get_iv_rank(iv_hist, call.iv)

            if not (config.MIN_IV_RANK <= iv_rank <= config.MAX_ENTRY_IV_RANK):
                continue

            candidates.append(StraddleCandidate(ticker, edate, call, put, iv_rank))

        return candidates

    def simulate_trade(self, provider: PolygonProvider, c: StraddleCandidate):
        entry = c.earnings_date - timedelta(days=25)
        exit_deadline = c.earnings_date - timedelta(days=config.EXIT_DAYS_BEFORE_EARNINGS)
        iv_path = provider.get_historical_iv(c.ticker, entry, exit_deadline)

        if len(iv_path) < 5:
            return None

        pnl = 0
        prev_iv = iv_path[0]
        for iv in iv_path[1:]:
            pnl += (c.call.vega + c.put.vega) * (iv - prev_iv)
            prev_iv = iv
            if pnl >= config.TARGET_PNL:
                break

        return PaperTrade(
            ticker=c.ticker,
            entry_date=entry,
            exit_date=exit_deadline,
            entry_iv_rank=c.iv_rank,
            exit_iv_rank=min(config.EXIT_IV_RANK, c.iv_rank + 10),
            pnl_pct=pnl,
            exit_reason="simulated",
        )

