import time
from dataclasses import dataclass


@dataclass
class TimeBudget:
    duration_seconds: float
    start_time: float = 0.0

    @classmethod
    def from_seconds(cls, seconds: float) -> "TimeBudget":
        return cls(duration_seconds=seconds)

    def start(self):
        self.start_time = time.time()

    def remaining(self) -> float:
        if self.start_time == 0.0:
            return self.duration_seconds
        elapsed = time.time() - self.start_time
        return max(0.0, self.duration_seconds - elapsed)

    def is_expired(self) -> bool:
        return self.remaining() <= 0.0
