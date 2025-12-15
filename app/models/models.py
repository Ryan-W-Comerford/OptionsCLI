from pydantic import BaseModel
from datetime import date

class OptionContract(BaseModel):
    symbol: str
    strike: float
    expiration: date
    option_type: str
    delta: float
    theta: float
    vega: float
    iv: float


class StraddleCandidate(BaseModel):
    ticker: str
    earnings_date: date
    call: OptionContract
    put: OptionContract
    iv_rank: float


class PaperTrade(BaseModel):
    ticker: str
    entry_date: date
    exit_date: date
    entry_iv_rank: float
    exit_iv_rank: float
    pnl_pct: float
    exit_reason: str
