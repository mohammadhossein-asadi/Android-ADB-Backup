"""Time and ETA utilities."""

import time
from collections import deque
from typing import Optional


class ETACalculator:
    """Calculate ETA based on recent completion times."""

    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.completion_times: deque[float] = deque(maxlen=window_size)
        self.start_time = time.monotonic()
        self.last_update = self.start_time

    def record_completion(self, duration: float) -> None:
        """Record a task completion time."""
        self.completion_times.append(duration)
        self.last_update = time.monotonic()

    def get_eta(self, completed: int, total: int) -> Optional[float]:
        """Get estimated time remaining in seconds."""
        if completed < 2 or len(self.completion_times) < 2:
            return None
        if completed >= total:
            return 0.0

        avg_time = sum(self.completion_times) / len(self.completion_times)
        remaining = total - completed
        return avg_time * remaining

    def get_elapsed(self) -> float:
        """Get total elapsed time."""
        return time.monotonic() - self.start_time

    def get_avg_time(self) -> Optional[float]:
        """Get average task time."""
        if not self.completion_times:
            return None
        return sum(self.completion_times) / len(self.completion_times)


def format_eta(eta_seconds: Optional[float]) -> str:
    """Format ETA as human-readable string."""
    if eta_seconds is None or eta_seconds <= 0:
        return "calculating..."
    if eta_seconds < 60:
        return f"{eta_seconds:.0f}s"
    minutes = int(eta_seconds // 60)
    secs = int(eta_seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"
