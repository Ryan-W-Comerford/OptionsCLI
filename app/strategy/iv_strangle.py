"""
Pre-Earnings Long Strangle Strategy (`longStrangleIV`)

Same thesis as the long straddle but buys slightly OTM call and put
(target delta ~0.25-0.35) instead of ATM. Cheaper entry cost, requires a
larger move to profit, but better risk/reward on high-beta names where
earnings moves are often violent (TSLA, COIN, NVDA etc).

Entry:  Buy OTM call + OTM put 15-50 DTE before earnings
Exit:   Sell before earnings day (avoid IV crush)
Win if: Underlying moves enough to cover combined premium
"""
from __future__ import annotations
from datetime import date, timedelta

from app.config.config import config
from app.data.provider import Provider
from app.models.models import OptionContract, StrangleCandidate
from app.strategy.strategy import Strategy

# OTM delta targets for the strangle legs
STRANGLE_DELTA_RANGE = (0.20, 0.40)   # target OTM — wider than straddle's 0.35–0.65
ATM_EXCLUDE_DELTA   = 0.42            # exclude contracts too close to ATM (those belong to straddle)


class LongStrangleIVStrategy(Strategy):
    def generate_candidates(
        self,
        market: Provider,
        earnings: Provider,
        ticker_filter: str | None = None,
    ) -> list[StrangleCandidate]:
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
    ) -> StrangleCandidate | None:
        today = date.today()
        days_to_earnings = (edate - today).days
        spot = market.get_stock_price(ticker)
        chain = market.get_option_chain(ticker)

        calls: list[OptionContract] = []
        puts: list[OptionContract] = []

        for o in chain:
            # Liquidity filters
            if o.volume < config.MIN_OPTION_VOLUME:
                continue
            if o.open_interest < config.MIN_OPEN_INTEREST:
                continue
            if o.bid > 0 and o.ask > 0:
                spread_pct = (o.ask - o.bid) / o.ask
                if spread_pct > config.MAX_BID_ASK_SPREAD_PCT:
                    continue

            # DTE filter
            dte = (o.expiration - today).days
            if not (config.TARGET_DTE_RANGE[0] <= dte <= config.TARGET_DTE_RANGE[1]):
                continue

            # OTM filter — must be outside ATM zone (not too close to spot)
            if spot == 0:
                continue
            otm_pct = abs(o.strike - spot) / spot
            if otm_pct < 0.01:  # too close to ATM
                continue
            if otm_pct > 0.12:  # too far OTM — illiquid / unrealistic
                continue

            # Delta filter — OTM range only, skip if greeks missing
            lo, hi = STRANGLE_DELTA_RANGE
            if o.delta != 0.0 and not (lo <= abs(o.delta) <= hi):
                continue

            (calls if o.option_type == "call" else puts).append(o)

        if not calls or not puts:
            return None

        # Pick call with delta closest to 0.30, put with delta closest to -0.30
        call = min(calls, key=lambda x: abs(abs(x.delta) - 0.30))
        put  = min(puts,  key=lambda x: abs(abs(x.delta) - 0.30))

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

        total_cost = round(call.ask + put.ask, 2)

        return StrangleCandidate(
            ticker=ticker,
            earnings_date=edate,
            days_to_earnings=days_to_earnings,
            call=call,
            put=put,
            iv_rank=iv_rank,
            vega_theta_ratio=round(vega_theta_ratio, 2),
            total_cost=total_cost,
            call_delta=round(call.delta, 3),
            put_delta=round(put.delta, 3),
        )