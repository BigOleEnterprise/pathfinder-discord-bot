"""Rate limiting utility for command usage."""
import time
from collections import defaultdict
from typing import DefaultDict


class RateLimiter:
    """Simple in-memory rate limiter for Discord commands."""

    def __init__(self, max_requests: int, window_seconds: int):
        """Initialize rate limiter with max requests allowed per time window."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: DefaultDict[int, list[float]] = defaultdict(list)

    def is_rate_limited(self, user_id: int) -> bool:
        """Check if user has exceeded rate limit."""
        now = time.time()
        user_requests = self._requests[user_id]

        # Remove old requests outside the time window
        cutoff_time = now - self.window_seconds
        self._requests[user_id] = [req_time for req_time in user_requests if req_time > cutoff_time]

        # Check if user has exceeded rate limit
        return len(self._requests[user_id]) >= self.max_requests

    def record_request(self, user_id: int) -> None:
        """Record a request for the given user for rate limiting tracking."""
        self._requests[user_id].append(time.time())

    def get_reset_time(self, user_id: int) -> float:
        """Get seconds until rate limit resets for user (0 if not rate limited)."""
        user_requests = self._requests[user_id]
        if not user_requests:
            return 0.0

        oldest_request = min(user_requests)
        reset_time = oldest_request + self.window_seconds
        time_remaining = reset_time - time.time()

        return max(0.0, time_remaining)
