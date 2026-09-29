"""规划修正流程的替身测试，不访问模型或高德地图。"""

import json

import pytest

from app.agents import trip_planner_agent
from app.agents.tool_decision import ToolDecisionResult
from app.config import get_settings
from app.exceptions import PlanFeasibilityError, PlanValidationError
from app.models.schemas import (
    Attraction,
    Budget,
    DayPlan,
    Hotel,
    Location,
    Meal,
    POIInfo,
    RouteInfo,
    TripPlan,
    TripRequest,
)


def poi(poi_id, poi_type):
    return POIInfo(
        id=poi_id,
        name=f"地点{poi_id}",
        type=poi_type,
        address=f"地址{poi_id}",
        location=Location(longitude=116.4, latitude=39.9),
    )


class FakeMap:
    def __init__(self):
        self.route_calls = []
        self.duration = 600

    def search_poi(self, *, keywords, city, citylimit=True):
        assert city == "北京"
        if "酒店" in keywords:
            return [poi("H", "住宿服务")]
        if "餐厅" in keywords:
            return [poi(str(i), "餐饮服务") for i in range(1, 4)]
        return [poi(name, "风景名胜") for name in "ABC"]

    def get_weather(self, city):
        return []

    def plan_route(self, **kwargs):
        self.route_calls.append(kwargs)
        return RouteInfo(
            distance=1000,
            duration=self.duration,
            route_type=kwargs["route_type"],
            description="测试路线",
        )


class FixedAgent:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        return next(self.responses)


def make_response(attraction_ids, visit_duration=120):
    day = DayPlan(
        date="2026-10-01",
        day_index=0,
        description="一日行程",
        transportation="公共交通",
        accommodation="经济型酒店",
        hotel=Hotel(poi_id="H", name="酒店"),
        attractions=[
            Attraction(
                poi_id=poi_id,
                name="待回填",
                address="待回填",
                location=Location(longitude=0, latitude=0),
                visit_duration=visit_duration,
                description="待回填",
            )
            for poi_id in attraction_ids
        ],
        meals=[
            Meal(poi_id=str(index), type=meal_type, name="待回填")
            for index, meal_type in enumerate(
                ("breakfast", "lunch", "dinner"), start=1
            )
        ],
    )
    return TripPlan(
        city="北京",
        start_date="2026-10-01",
        end_date="2026-10-01",
        days=[day],
        overall_suggestions="测试",
        budget=Budget(total_transportation=30),
    ).model_dump_json()


def run_plan(monkeypatch, planner_responses, suggested_duration=120):
    request = TripRequest(
        city="北京",
        start_date="2026-10-01",
        end_date="2026-10-01",
        travel_days=1,
        transportation="公共交通",
        accommodation="经济型酒店",
        preferences=["历史文化"],
    )
    amap = FakeMap()
    monkeypatch.setattr(get_settings(), "daily_available_minutes", 500)
    monkeypatch.setattr(get_settings(), "daily_meal_buffer_minutes", 180)
    monkeypatch.setattr(trip_planner_agent, "get_amap_service", lambda: amap)
    monkeypatch.setattr(
        trip_planner_agent,
        "run_tool_decisions",
        lambda **kwargs: ToolDecisionResult(
            candidates=kwargs["initial_candidates"], route_hints=[], trace=[]
        ),
    )

    planner = trip_planner_agent.MultiAgentTripPlanner.__new__(
        trip_planner_agent.MultiAgentTripPlanner
    )
    planner.llm = object()
    planner.attraction_agent = FixedAgent([
        json.dumps({"attractions": [
            {"poi_id": poi_id, "reason": "合适", "suggested_duration": suggested_duration}
            for poi_id in "ABC"
        ]})
    ])
    planner.hotel_agent = FixedAgent([
        json.dumps({"hotels": [{"poi_id": "H", "reason": "近"}]})
    ])
    planner.restaurant_agent = FixedAgent([
        json.dumps({"restaurants": [
            {"poi_id": str(i), "reason": "方便"} for i in range(1, 4)
        ]})
    ])
    planner.planner_agent = FixedAgent(planner_responses)
    return planner, request, amap


def test_timeout_is_repaired_once_and_reuses_routes(monkeypatch):
    planner, request, amap = run_plan(
        monkeypatch, [make_response("ABC", 30), make_response("AB")]
    )

    result = planner.plan_trip(request)

    assert [item.poi_id for item in result.days[0].attractions] == ["A", "B"]
    assert all(item.visit_duration == 120 for item in result.days[0].attractions)
    assert len(planner.planner_agent.prompts) == 2
    assert "500分钟" in planner.planner_agent.prompts[0]
    assert '"over_minutes": 80' in planner.planner_agent.prompts[1]
    assert '"minimum": 96' in planner.planner_agent.prompts[1]
    assert "每天只能安排2个景点" in planner.planner_agent.prompts[1]
    assert len(amap.route_calls) == 5  # 首轮4段，修正后2段复用、1段新增。


def test_second_timeout_stops_without_third_model_call(monkeypatch):
    planner, request, _ = run_plan(
        monkeypatch, [make_response("ABC"), make_response("ABC")]
    )

    with pytest.raises(PlanFeasibilityError, match="景点360、路线40、用餐180"):
        planner.plan_trip(request)
    assert len(planner.planner_agent.prompts) == 2


def test_repair_cannot_introduce_unknown_poi(monkeypatch):
    planner, request, _ = run_plan(
        monkeypatch, [make_response("ABC"), make_response("AZ")]
    )

    with pytest.raises(PlanValidationError, match="未知景点POI ID"):
        planner.plan_trip(request)
    assert len(planner.planner_agent.prompts) == 2


def test_repair_can_shorten_each_visit_within_bounds(monkeypatch):
    planner, request, amap = run_plan(
        monkeypatch,
        [make_response("ABC", 30), make_response("AB", 170)],
        suggested_duration=210,
    )
    monkeypatch.setattr(get_settings(), "daily_available_minutes", 750)
    amap.duration = 4500  # 每段75分钟；修正后 340 + 225 + 180 = 745。

    result = planner.plan_trip(request)

    assert [item.visit_duration for item in result.days[0].attractions] == [170, 170]
    assert len(result.days[0].travel_legs) == 3
    assert '"minimum": 168' in planner.planner_agent.prompts[1]
    assert len(planner.planner_agent.prompts) == 2


def test_repair_rejects_unrealistically_short_visit(monkeypatch):
    planner, request, _ = run_plan(
        monkeypatch,
        [make_response("ABC"), make_response("AB", 30)],
    )

    with pytest.raises(PlanValidationError, match="修正停留时间"):
        planner.plan_trip(request)
    assert len(planner.planner_agent.prompts) == 2
