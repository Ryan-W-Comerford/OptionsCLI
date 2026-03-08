from datetime import date
from pydantic import BaseModel


class OptionContract(BaseModel):
    symbol: str
    strike: float
    expiration: date
    option_type: str  # "call" or "put"
    delta: float
    theta: float
    vega: float
    iv: float
    volume: int = 0
    open_interest: int = 0
    bid: float = 0.0
    ask: float = 0.0


class StraddleCandidate(BaseModel):
    ticker: str
    earnings_date: date
    days_to_earnings: int
    call: OptionContract
    put: OptionContract
    iv_rank: float
    vega_theta_ratio: float
    total_cost: float  # combined ask of call + put — rough entry cost estimate


class StrangleCandidate(BaseModel):
    ticker: str
    earnings_date: date
    days_to_earnings: int
    call: OptionContract
    put: OptionContract
    iv_rank: float
    vega_theta_ratio: float
    total_cost: float
    call_delta: float  # OTM target delta
    put_delta: float


class IVRankAlert(BaseModel):
    ticker: str
    iv_rank: float
    current_iv: float
    spot: float
    iv_52w_low: float
    iv_52w_high: float


class PaperTrade(BaseModel):
    ticker: str
    entry_date: date
    exit_date: date
    entry_iv_rank: float
    exit_iv_rank: float
    pnl_pct: float
    exit_reason: str