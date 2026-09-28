from copy import deepcopy

import pytest

from app.agents.trip_planner_agent import MultiAgentTripPlanner
from app.config import get_settings
from app.exceptions import PlanValidationError
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


def make_request(days: int = 2) -> TripRequest:
    return TripRequest(
        city="北京",
        start_date="2026-10-01",
        end_date=f"2026-10-0{days}",
        travel_days=days,
        transportation="公共交通",
        accommodation="经济型酒店",
    )


def make_hotel() -> Hotel:
    return Hotel(
        poi_id="hotel-1",
        name="可信酒店",
        address="酒店地址",
        location=Location(longitude=116.1, latitude=39.1),
        estimated_cost=300,
    )


def make_attraction(index: int, duration: int = 120) -> Attraction:
    return Attraction(
        poi_id=f"attraction-{index}",
        name=f"景点{index}",
        address=f"景点地址{index}",
        location=Location(longitude=116.1 + index, latitude=39.1),
        visit_duration=duration,
        description="描述",
        ticket_price=50,
    )


def make_meals() -> list[Meal]:
    return [
        Meal(poi_id="restaurant-1", type="breakfast", name="早餐", estimated_cost=20),
        Meal(poi_id="restaurant-2", type="lunch", name="午餐", estimated_cost=40),
        Meal(poi_id="restaurant-3", type="dinner", name="晚餐", estimated_cost=60),
    ]


def make_day(index: int = 0, day_date: str = "2026-10-01") -> DayPlan:
    return DayPlan(
        date=day_date,
        day_index=index,
        description="测试行程",
        transportation="公共交通",
        accommodation="经济型酒店",
        hotel=make_hotel(),
        attractions=[make_attraction(1), make_attraction(2)],
        meals=make_meals(),
    )


def make_plan(days: list[DayPlan]) -> TripPlan:
    return TripPlan(
        city="北京",
        start_date="2026-10-01",
        end_date=f"2026-10-0{len(days)}",
        days=days,
        overall_suggestions="测试建议",
        budget=Budget(total_transportation=100),
    )


def test_dates_and_day_indexes_must_be_continuous():
    planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
    plan = make_plan([
        make_day(0, "2026-10-01"),
        make_day(1, "2026-10-02"),
    ])
    planner._validate_plan_against_request(plan, make_request())

    invalid_index = plan.model_copy(deep=True)
    invalid_index.days[1].day_index = 2
    with pytest.raises(PlanValidationError, match="day_index不连续"):
        planner._validate_plan_against_request(invalid_index, make_request())

    invalid_date = plan.model_copy(deep=True)
    invalid_date.days[1].date = "2026-10-03"
    with pytest.raises(PlanValidationError, match="行程日期不连续"):
        planner._validate_plan_against_request(invalid_date, make_request())


def test_meals_are_exactly_three_and_hydrated_from_trusted_pois():
    planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
    day = make_day()
    pois = {
        f"restaurant-{index}": POIInfo(
            id=f"restaurant-{index}",
            name=f"真实餐厅{index}",
            type="餐饮服务",
            address=f"真实地址{index}",
            location=Location(longitude=116 + index, latitude=39),
        )
        for index in range(1, 4)
    }
    reasons = {poi_id: f"推荐{poi_id}" for poi_id in pois}

    planner._validate_and_hydrate_meals(day, set(pois), pois, reasons)
    assert [meal.name for meal in day.meals] == [
        "真实餐厅1", "真实餐厅2", "真实餐厅3"
    ]
    assert all(meal.address.startswith("真实地址") for meal in day.meals)

    invalid = deepcopy(day)
    invalid.meals[2].type = "lunch"
    with pytest.raises(PlanValidationError, match="早、中、晚餐"):
        planner._validate_and_hydrate_meals(invalid, set(pois), pois, reasons)


def test_budget_is_recalculated_from_plan_details():
    planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
    plan = make_plan([make_day()])
    planner._normalize_and_validate_budget(plan)
    assert plan.budget.total_attractions == 100
    assert plan.budget.total_hotels == 300
    assert plan.budget.total_meals == 120
    assert plan.budget.total == 620


class FakeRouteService:
    def __init__(self, fail_on_call: int | None = None, duration: int = 600):
        self.calls = 0
        self.fail_on_call = fail_on_call
        self.duration = duration

    def plan_route(self, **kwargs):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("route unavailable")
        return RouteInfo(
            distance=1000,
            duration=self.duration,
            route_type=kwargs["route_type"],
            description="真实路线",
        )


def test_real_routes_are_written_to_day_plan(monkeypatch):
    planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
    day = make_day()
    monkeypatch.setattr(get_settings(), "daily_available_minutes", 720)
    monkeypatch.setattr(get_settings(), "daily_meal_buffer_minutes", 180)

    warnings = planner._populate_routes_and_validate_feasibility(
        day, "北京", "公共交通", FakeRouteService()
    )
    assert warnings == []
    assert len(day.travel_legs) == 3
    assert day.travel_legs[0].origin_poi_id == "hotel-1"
    assert day.travel_legs[-1].destination_poi_id == "hotel-1"
    assert all(leg.route_type == "transit" for leg in day.travel_legs)


def test_incomplete_routes_degrade_and_skip_feasibility_check(monkeypatch):
    planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
    day = make_day()
    monkeypatch.setattr(get_settings(), "daily_available_minutes", 1)
    warnings = planner._populate_routes_and_validate_feasibility(
        day, "北京", "公共交通", FakeRouteService(fail_on_call=2)
    )
    assert len(day.travel_legs) == 2
    assert "无法完整校验时间可行性" in warnings[0]


def test_route_duration_can_make_a_day_infeasible(monkeypatch):
    planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
    day = make_day()
    monkeypatch.setattr(get_settings(), "daily_available_minutes", 400)
    monkeypatch.setattr(get_settings(), "daily_meal_buffer_minutes", 180)
    with pytest.raises(PlanValidationError, match="行程不可行"):
        planner._populate_routes_and_validate_feasibility(
            day, "北京", "公共交通", FakeRouteService()
        )
