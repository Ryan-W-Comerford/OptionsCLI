from app.strategy.strategy import Strategy
from app.data.polygon import PolygonProvider
from app.config.config import config
from app.strategy.iv_straddle import LongStraddleIVStrategy
from app.util.display import print_candidates
import argparse

def run_find_all(provider: PolygonProvider, strategy: Strategy):
    candidates = strategy.generate_candidates(provider)
    print_candidates(candidates)

def run_find_one(provider: PolygonProvider, strategy: Strategy, ticker: str):
    candidates = strategy.generate_candidates(provider)
    filtered = [c for c in candidates if c.ticker.upper() == ticker.upper()]
    print_candidates(filtered)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Options Strategy Scanner CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    find_all = subparsers.add_parser("findAll", help="Find all candidates")
    find_all.add_argument(
        "strategy",
        type=str,
        help="Strategy name (e.g. longStraddleIV)"
    )

    find_one = subparsers.add_parser("findOne", help="Check a single ticker")
    find_one.add_argument(
        "strategy",
        type=str,
        help="Strategy name (e.g. longStraddleIV)"
    )
    find_one.add_argument(
        "ticker",
        type=str,
        help="Ticker symbol, e.g. AAPL"
    )

    args = parser.parse_args()

    provider = PolygonProvider(config.POLYGON_API_KEY)

    STRATEGIES = {
        "longStraddleIV": LongStraddleIVStrategy(),
    }
    if args.strategy not in STRATEGIES:
        raise ValueError(
            f"Strategy '{args.strategy}' not supported. "
            f"Available: {list(STRATEGIES.keys())}"
        )
    strategy = STRATEGIES[args.strategy]

    if args.command == "findAll":
        run_find_all(provider, strategy)

    elif args.command == "findOne":
        run_find_one(provider, strategy, args.ticker)