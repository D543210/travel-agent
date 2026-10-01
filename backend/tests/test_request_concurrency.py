import asyncio
import threading

import httpx
import pytest

from app.api.main import app
from app.exceptions import ExternalServiceError
from app.logging_context import get_request_id
from app.planning_concurrency import PlanningCapacityLimiter
from tests.concurrency_helpers import (
    create_request_payload,
    create_test_plan,
)


pytestmark = pytest.mark.usefixtures("authenticated_user")


class ConcurrencyTracker:
    def __init__(self, release_after: int = 2):
        self.active = 0
        self.max_active = 0
        self.release_after = release_after
        self.lock = threading.Lock()
        self.release_event = threading.Event()

    def enter(self) -> None:
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)

            if self.active >= self.release_after:
                self.release_event.set()

    def leave(self) -> None:
        with self.lock:
            self.active -= 1


class TrackingPlanner:
    def __init__(self, tracker, observed_request_ids=None):
        self.tracker = tracker
        self.observed_request_ids = observed_request_ids

    def plan_trip(self, request):
        self.tracker.enter()

        try:
            if self.observed_request_ids is not None:
                self.observed_request_ids[request.city] = get_request_id()

            if not self.tracker.release_event.wait(timeout=3):
                raise AssertionError("并发请求没有在预期时间内重叠执行")

            return create_test_plan(request)
        finally:
            self.tracker.leave()


async def _send_plans(client, cities, request_ids=None):
    requests = []

    for index, city in enumerate(cities):
        headers = {}

        if request_ids is not None:
            headers["X-Request-ID"] = request_ids[index]

        requests.append(
            client.post(
                "/api/trip/plan",
                headers=headers,
                json=create_request_payload(city),
            )
        )

    return await asyncio.gather(*requests)


def test_trip_requests_overlap_in_thread_pool(monkeypatch):
    tracker = ConcurrencyTracker(release_after=2)
    limiter = PlanningCapacityLimiter(capacity=10)

    monkeypatch.setattr(
        "app.api.routes.trip.create_trip_planner",
        lambda: TrackingPlanner(tracker),
    )
    monkeypatch.setattr(
        "app.api.routes.trip.get_planning_capacity_limiter",
        lambda: limiter,
    )

    async def run_test():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await _send_plans(
                client,
                ["城市A", "城市B", "城市C", "城市D", "城市E"],
            )

    responses = asyncio.run(run_test())

    assert all(response.status_code == 200 for response in responses)
    assert all(
        response.json()["status"] == "success"
        for response in responses
    )
    assert tracker.max_active >= 2
    assert {
        response.json()["data"]["city"]
        for response in responses
    } == {"城市A", "城市B", "城市C", "城市D", "城市E"}


def test_request_id_isolated_and_propagated_to_worker(monkeypatch):
    tracker = ConcurrencyTracker(release_after=2)
    limiter = PlanningCapacityLimiter(capacity=4)
    observed_request_ids = {}

    monkeypatch.setattr(
        "app.api.routes.trip.create_trip_planner",
        lambda: TrackingPlanner(tracker, observed_request_ids),
    )
    monkeypatch.setattr(
        "app.api.routes.trip.get_planning_capacity_limiter",
        lambda: limiter,
    )

    async def run_test():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await _send_plans(
                client,
                ["北京", "上海"],
                ["request-a", "request-b"],
            )

    first, second = asyncio.run(run_test())

    assert first.headers["X-Request-ID"] == "request-a"
    assert second.headers["X-Request-ID"] == "request-b"
    assert observed_request_ids == {
        "北京": "request-a",
        "上海": "request-b",
    }


def test_request_id_is_generated_when_header_is_missing():
    async def run_test():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await asyncio.gather(
                client.get("/api/trip/health"),
                client.get("/api/trip/health"),
            )

    first, second = asyncio.run(run_test())
    first_id = first.headers["X-Request-ID"]
    second_id = second.headers["X-Request-ID"]

    assert len(first_id) == 12
    assert len(second_id) == 12
    assert first_id != second_id
    int(first_id, 16)
    int(second_id, 16)


def test_request_id_is_returned_on_business_error(monkeypatch):
    limiter = PlanningCapacityLimiter(capacity=1)

    class FailingPlanner:
        def plan_trip(self, request):
            assert get_request_id() == "request-error"
            raise ExternalServiceError("expected test failure")

    monkeypatch.setattr(
        "app.api.routes.trip.create_trip_planner",
        lambda: FailingPlanner(),
    )
    monkeypatch.setattr(
        "app.api.routes.trip.get_planning_capacity_limiter",
        lambda: limiter,
    )

    async def run_test():
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/trip/plan",
                headers={"X-Request-ID": "request-error"},
                json=create_request_payload("错误城市"),
            )

    response = asyncio.run(run_test())

    assert response.status_code == 503
    assert response.headers["X-Request-ID"] == "request-error"
    assert response.json()["detail"]["code"] == (
        "EXTERNAL_SERVICE_UNAVAILABLE"
    )
    assert response.json()["detail"]["status"] == "failed"


def test_degraded_plan_status_and_warnings_are_returned(monkeypatch):
    limiter = PlanningCapacityLimiter(capacity=1)

    class DegradedPlanner:
        def plan_trip(self, request):
            plan = create_test_plan(request)
            plan.status = "degraded"
            plan.warnings = ["天气服务不可用"]
            return plan

    monkeypatch.setattr(
        "app.api.routes.trip.create_trip_planner",
        lambda: DegradedPlanner(),
    )
    monkeypatch.setattr(
        "app.api.routes.trip.get_planning_capacity_limiter",
        lambda: limiter,
    )

    async def run_test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            return await client.post(
                "/api/trip/plan",
                json=create_request_payload(),
            )

    response = asyncio.run(run_test())
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["warnings"] == ["天气服务不可用"]
