"""TTFT and latency measurement for proxied requests."""

import time
from dataclasses import dataclass, field


@dataclass
class RequestMetrics:
    """Collects timing metrics for a single proxied request."""
    t_request_received: float = 0.0
    t_first_token: float = 0.0
    t_response_done: float = 0.0

    def start(self) -> None:
        self.t_request_received = time.time()

    def mark_first_token(self) -> None:
        if self.t_first_token == 0.0:
            self.t_first_token = time.time()

    def mark_done(self) -> None:
        self.t_response_done = time.time()

    @property
    def ttft_ms(self) -> int | None:
        if self.t_first_token > 0:
            return int((self.t_first_token - self.t_request_received) * 1000)
        return None

    @property
    def latency_ms(self) -> int:
        if self.t_response_done > 0:
            return int((self.t_response_done - self.t_request_received) * 1000)
        return 0
