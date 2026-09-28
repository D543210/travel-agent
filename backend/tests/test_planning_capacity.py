import asyncio
import threading

import httpx

from app.api.main import app
from app.planning_concurrency import PlanningCapacityLimiter
from tests.concurrency_helpers import (
    create_request_payload,
    create_test_plan,
)


class BlockingPlanner:
    def __init__(self, started_event, release_event, counter, lock):
        self.started_event = started_event
        self.release_event = release_event
        self.counter = counter
        self.lock = lock

    def plan_trip(self, request):
        with self.lock:
            self.counter["started"] += 1

            if self.counter["started"] >= 2:
                self.started_event.set()

        if not self.release_event.wait(timeout=3):
            raise AssertionError("测试没有释放阻塞中的规划请求")

        return create_test_plan(request)


def test_capacity_limit_rejects_excess_request(monkeypatch):
    limiter = PlanningCapacityLimiter(capacity=2)
    started_event = threading.Event()
    release_event = threading.Event()
    counter = {"started": 0}
    lock = threading.Lock()

    monkeypatch.setattr(
        "app.api.routes.trip.get_planning_capacity_limiter",
        lambda: limiter,
    )
    monkeypatch.setattr(
        "app.api.routes.trip.create_trip_planner",
        lambda: BlockingPlanner(
            started_event,
            release_event,
            counter,
            lock,
        ),
    )

    async def run_test():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            first = asyncio.create_task(
                client.post(
                    "/api/trip/plan",
                    json=create_request_payload("城市A"),
                )
            )
            second = asyncio.create_task(
                client.post(
                    "/api/trip/plan",
                    json=create_request_payload("城市B"),
                )
            )

            started = await asyncio.to_thread(
                started_event.wait,
                3,
            )
            assert started

            rejected = await client.post(
                "/api/trip/plan",
                json=create_request_payload("城市C"),
            )

            release_event.set()
            completed = await asyncio.gather(first, second)
            return rejected, completed

    rejected, completed = asyncio.run(run_test())

    assert rejected.status_code == 429
    assert rejected.headers["Retry-After"] == "5"
    assert rejected.json()["detail"]["code"] == "TOO_MANY_TRIP_PLANS"
    assert all(response.status_code == 200 for response in completed)


def test_capacity_slot_is_released_after_failure(monkeypatch):
    limiter = PlanningCapacityLimiter(capacity=1)

    class FailingPlanner:
        def plan_trip(self, request):
            raise RuntimeError("expected test failure")

    class SuccessfulPlanner:
        def plan_trip(self, request):
            return create_test_plan(request)

    planners = iter([FailingPlanner(), SuccessfulPlanner()])

    monkeypatch.setattr(
        "app.api.routes.trip.get_planning_capacity_limiter",
        lambda: limiter,
    )
    monkeypatch.setattr(
        "app.api.routes.trip.create_trip_planner",
        lambda: next(planners),
    )

    async def run_test():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            failed = await client.post(
                "/api/trip/plan",
                json=create_request_payload("失败城市"),
            )
            succeeded = await client.post(
                "/api/trip/plan",
                json=create_request_payload("成功城市"),
            )
            return failed, succeeded

    failed, succeeded = asyncio.run(run_test())

    assert failed.status_code == 500
    assert succeeded.status_code == 200
