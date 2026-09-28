"""本地并发基准：不访问真实LLM或地图服务。"""

import argparse
import asyncio
import math
import time
from dataclasses import dataclass

import httpx

from app.api.main import app
from app.api.routes import trip as trip_routes
from app.models.schemas import TripPlan
from app.planning_concurrency import PlanningCapacityLimiter


def create_payload(index: int) -> dict:
    return {
        "city": f"基准城市{index}",
        "start_date": "2026-10-01",
        "end_date": "2026-10-01",
        "travel_days": 1,
        "transportation": "公共交通",
        "accommodation": "经济型酒店",
        "preferences": ["历史文化"],
        "free_text_input": "",
    }


class FakePlanner:
    def __init__(self, delay_seconds: float):
        self.delay_seconds = delay_seconds

    def plan_trip(self, request):
        time.sleep(self.delay_seconds)

        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=[],
            weather_info=[],
            overall_suggestions="并发基准测试行程",
        )


@dataclass
class RequestResult:
    status_code: int
    duration_ms: float


def percentile(values: list[float], percentage: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = max(
        0,
        math.ceil(len(ordered) * percentage) - 1,
    )
    return ordered[index]


async def send_request(
    client: httpx.AsyncClient,
    index: int,
) -> RequestResult:
    started_at = time.perf_counter()
    response = await client.post(
        "/api/trip/plan",
        headers={"X-Request-ID": f"benchmark-{index}"},
        json=create_payload(index),
    )
    duration_ms = (
        time.perf_counter() - started_at
    ) * 1000

    return RequestResult(
        status_code=response.status_code,
        duration_ms=duration_ms,
    )


async def run_level(
    concurrency: int,
    capacity: int,
    delay_seconds: float,
) -> dict:
    limiter = PlanningCapacityLimiter(capacity)

    trip_routes.get_planning_capacity_limiter = lambda: limiter
    trip_routes.create_trip_planner = lambda: FakePlanner(
        delay_seconds
    )
    trip_routes.log = lambda _message: None

    transport = httpx.ASGITransport(app=app)
    started_at = time.perf_counter()

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://benchmark",
    ) as client:
        results = await asyncio.gather(
            *[
                send_request(client, index)
                for index in range(concurrency)
            ]
        )

    wall_time_ms = (
        time.perf_counter() - started_at
    ) * 1000
    durations = [result.duration_ms for result in results]
    successes = sum(
        result.status_code == 200
        for result in results
    )
    rejected = sum(
        result.status_code == 429
        for result in results
    )

    return {
        "concurrency": concurrency,
        "successes": successes,
        "failures": len(results) - successes,
        "rejected": rejected,
        "p50_ms": percentile(durations, 0.50),
        "p95_ms": percentile(durations, 0.95),
        "wall_time_ms": wall_time_ms,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--capacity",
        type=int,
        default=10,
        help="单进程允许同时执行的规划数量",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=200,
        help="Fake Planner单次执行耗时",
    )
    args = parser.parse_args()

    print(
        "并发数 | 成功 | 失败 | 429 | P50(ms) | "
        "P95(ms) | 总耗时(ms)"
    )
    print("-" * 72)

    for concurrency in (1, 5, 10):
        result = await run_level(
            concurrency=concurrency,
            capacity=args.capacity,
            delay_seconds=args.delay_ms / 1000,
        )
        print(
            f"{result['concurrency']:>6} | "
            f"{result['successes']:>4} | "
            f"{result['failures']:>4} | "
            f"{result['rejected']:>3} | "
            f"{result['p50_ms']:>7.1f} | "
            f"{result['p95_ms']:>7.1f} | "
            f"{result['wall_time_ms']:>10.1f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
