"""旅行规划请求的进程内并发容量控制。"""

from threading import BoundedSemaphore

from .config import get_settings


class PlanningCapacityLimiter:
    """限制单个进程中同时执行的旅行规划数量。"""

    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("capacity必须大于等于1")

        self.capacity = capacity
        self._semaphore = BoundedSemaphore(capacity)

    def try_acquire(self) -> bool:
        """立即尝试占用一个规划名额，不等待排队。"""
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        """释放一个规划名额。"""
        self._semaphore.release()


_planning_capacity_limiter = PlanningCapacityLimiter(
    get_settings().max_concurrent_trip_plans
)


def get_planning_capacity_limiter() -> PlanningCapacityLimiter:
    """获取当前进程共享的规划容量限制器。"""
    return _planning_capacity_limiter
