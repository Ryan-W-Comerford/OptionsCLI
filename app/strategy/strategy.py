from abc import ABC, abstractmethod

from app.data.provider import Provider
from app.models.models import StraddleCandidate


class Strategy(ABC):
    @abstractmethod
    def generate_candidates(
        self,
        market: Provider,
        earnings: Provider,
        ticker_filter: str = None
    ) -> list[StraddleCandidate]:
        raise NotImplementedError