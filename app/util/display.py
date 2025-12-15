from app.models.models import StraddleCandidate

def print_candidates(candidates: list[StraddleCandidate]):
    if not candidates:
        print("No candidates found")
        return

    print("LONG STRADDLE IV CANDIDATES")
    print("=" * 40)
    for c in candidates:
        print(f"Ticker: {c.ticker}")
        print(f"Earnings Date: {c.earnings_date}")
        print(f"IV Rank: {c.iv_rank:.1f}")
        print(f"Call: {c.call.symbol} | Δ {c.call.delta:.2f} Θ {c.call.theta:.3f} V {c.call.vega:.3f}")
        print(f"Put : {c.put.symbol} | Δ {c.put.delta:.2f} Θ {c.put.theta:.3f} V {c.put.vega:.3f}")
        print("-" * 40)