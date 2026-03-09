from __future__ import annotations
from datetime import date, timedelta

from app.config.config import config
from app.data.provider import Provider
from app.models.models import OptionContract, StraddleCandidate
from app.strategy.strategy import Strategy


class LongStraddleEarningsStrategy(Strategy):
    def generate_candidates(
        self,
        market: Provider,
        earnings: Provider,
        ticker_filter: str | None = None,
    ) -> list[StraddleCandidate]:
        watchlist = set(config.STOCKS)
        candidates = []

        for e in earnings.get_upcoming_earnings(config.EARNINGS_LOOKAHEAD_DAYS):
            ticker, edate = e["ticker"], e["date"]

            if ticker_filter and ticker.upper() != ticker_filter.upper():
                continue
            if ticker not in watchlist:
                continue

            print(f"  Scanning {ticker}...")
            try:
                result = self._evaluate(market, ticker, edate)
                if result:
                    candidates.append(result)
            except Exception as ex:
                print(f"  Skipping {ticker}: {ex}")

        return candidates

    def _evaluate(
        self,
        market: Provider,
        ticker: str,
        edate: date,
    ) -> StraddleCandidate | None:
        today = date.today()
        days_to_earnings = (edate - today).days
        spot = market.get_stock_price(ticker)
        chain = market.get_option_chain(ticker)

        calls: list[OptionContract] = []
        puts: list[OptionContract] = []

        for o in chain:
            if o.volume < config.MIN_OPTION_VOLUME:
                continue
            if o.open_interest < config.MIN_OPEN_INTEREST:
                continue
            if o.bid > 0 and o.ask > 0:
                spread_pct = (o.ask - o.bid) / o.ask
                if spread_pct > config.MAX_BID_ASK_SPREAD_PCT:
                    continue
            dte = (o.expiration - today).days
            if not (config.TARGET_DTE_RANGE[0] <= dte <= config.TARGET_DTE_RANGE[1]):
                continue
            if spot == 0 or abs(o.strike - spot) / spot >= 0.02:
                continue
            lo, hi = config.ATM_DELTA_RANGE
            # Skip delta filter if greeks not returned by API (coerced to 0.0) — rely on ATM proximity
            if o.delta != 0.0 and not (lo <= abs(o.delta) <= hi):
                continue
            (calls if o.option_type == "call" else puts).append(o)

        if not calls or not puts:
            return None

        call = min(calls, key=lambda x: abs(x.delta - 0.5))
        put = min(puts, key=lambda x: abs(abs(x.delta) - 0.5))

        theta = abs(call.theta) + abs(put.theta)
        if theta == 0:
            return None

        vega_theta_ratio = (call.vega + put.vega) / theta
        if vega_theta_ratio < config.MIN_VEGA_THETA_RATIO:
            return None

        iv_hist = market.get_historical_iv(
            ticker,
            start=today - timedelta(days=252),
            end=today - timedelta(days=1),
        )
        current_iv = (call.iv + put.iv) / 2
        iv_rank = market.get_iv_rank(iv_hist, current_iv)

        if not (config.MIN_IV_RANK <= iv_rank <= config.MAX_ENTRY_IV_RANK):
            return None

        # total_cost will be 0.0 if bid/ask not available on current plan
        total_cost = round(call.ask + put.ask, 2)

        return StraddleCandidate(
            ticker=ticker,
            earnings_date=edate,
            days_to_earnings=days_to_earnings,
            call=call,
            put=put,
            iv_rank=iv_rank,
            vega_theta_ratio=round(vega_theta_ratio, 2),
            total_cost=total_cost,
        )