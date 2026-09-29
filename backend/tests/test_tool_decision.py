"""工具决策的行为测试：模型输出仅能触发受控的地图调用。"""

import json

import pytest

from app.agents import tool_decision
from app.models.schemas import Location, POIInfo, RouteInfo, TripRequest


def poi(poi_id: str, poi_type: str = "风景名胜") -> POIInfo:
    return POIInfo(
        id=poi_id,
        name=f"景点{poi_id}",
        type=poi_type,
        address=f"地址{poi_id}",
        location=Location(longitude=116.4, latitude=39.9),
    )


class ScriptedAgent:
    """按顺序返回模型决策，并保留输入以检查下一轮观察。"""

    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        return next(self.responses)


class FakeMap:
    def __init__(self, search_results=()):
        self.search_results = list(search_results)
        self.search_calls = []
        self.route_calls = []

    def search_poi(self, **kwargs):
        self.search_calls.append(kwargs)
        return self.search_results

    def plan_route(self, **kwargs):
        self.route_calls.append(kwargs)
        return RouteInfo(
            distance=1800,
            duration=1200,
            route_type=kwargs["route_type"],
            description="测试路线",
        )


@pytest.fixture
def trip_request():
    return TripRequest(
        city="北京",
        start_date="2026-10-01",
        end_date="2026-10-01",
        travel_days=1,
        transportation="步行",
        accommodation="经济型酒店",
        preferences=["历史文化"],
    )


def decide(monkeypatch, trip_request, responses, amap, initial=None):
    agent = ScriptedAgent(responses)
    monkeypatch.setattr(tool_decision, "SimpleAgent", lambda **_kwargs: agent)
    result = tool_decision.run_tool_decisions(
        request=trip_request,
        initial_candidates=initial if initial is not None else [poi("A"), poi("B")],
        weather=[],
        amap_service=amap,
        llm=object(),
        route_type="walking",
    )
    return result, agent


def action(name, **kwargs):
    return json.dumps({"action": name, "reason": "测试需要", **kwargs}, ensure_ascii=False)


def test_finish_does_not_call_map(monkeypatch, trip_request):
    amap = FakeMap()
    result, agent = decide(monkeypatch, trip_request, [action("finish")], amap)

    assert [item.id for item in result.candidates] == ["A", "B"]
    assert result.route_hints == []
    assert result.trace[0]["status"] == "finished"
    assert len(agent.prompts) == 1
    assert amap.search_calls == amap.route_calls == []


def test_search_adds_only_new_attractions_and_reports_observation(monkeypatch, trip_request):
    amap = FakeMap([poi("A"), poi("C"), poi("D", "餐饮服务;中餐厅")])
    result, agent = decide(
        monkeypatch,
        trip_request,
        [action("search_more", keyword="博物馆"), action("finish")],
        amap,
    )

    assert amap.search_calls == [{"keywords": "博物馆", "city": "北京", "citylimit": True}]
    assert [item.id for item in result.candidates] == ["A", "B", "C"]
    assert result.trace[0]["added_count"] == 1
    assert result.trace[0]["excluded_count"] == 1
    assert '"added_poi_ids": ["C"]' in agent.prompts[1]


def test_route_uses_addresses_from_known_pois(monkeypatch, trip_request):
    amap = FakeMap()
    result, _ = decide(
        monkeypatch,
        trip_request,
        [action("check_route", origin_poi_id="A", destination_poi_id="B"), action("finish")],
        amap,
    )

    assert amap.route_calls == [{
        "origin_address": "地址A",
        "destination_address": "地址B",
        "origin_city": "北京",
        "destination_city": "北京",
        "route_type": "walking",
    }]
    assert "20 分钟" in result.route_hints[0]


def test_missing_explanatory_reason_keeps_valid_route_action(monkeypatch, trip_request):
    """真实模型可能省略解释字段，安全参数仍需按原规则校验。"""
    amap = FakeMap()
    response = json.dumps({
        "action": "check_route",
        "origin_poi_id": "A",
        "destination_poi_id": "B",
    })
    result, _ = decide(monkeypatch, trip_request, [response, action("finish")], amap)

    assert len(amap.route_calls) == 1
    assert result.trace[0]["reason"] == "模型未提供原因"


@pytest.mark.parametrize("response", [
    "不是 JSON",
    action("check_route", origin_poi_id="A", destination_poi_id="不存在"),
    action("search_more", keyword="https://example.com"),
    action("finish", keyword="博物馆"),
])
def test_invalid_decision_never_calls_map(monkeypatch, trip_request, response):
    amap = FakeMap()
    result, _ = decide(monkeypatch, trip_request, [response], amap)

    assert amap.search_calls == amap.route_calls == []
    assert result.trace[0]["status"] in {"invalid_decision", "invalid_poi_rejected"}


def test_duplicate_call_is_rejected(monkeypatch, trip_request):
    amap = FakeMap()
    result, _ = decide(
        monkeypatch,
        trip_request,
        [action("search_more", keyword="博物馆")] * 2,
        amap,
    )

    assert len(amap.search_calls) == 1
    assert result.trace[-1]["status"] == "duplicate_rejected"


def test_only_two_extra_calls_are_allowed(monkeypatch, trip_request):
    amap = FakeMap()
    result, agent = decide(
        monkeypatch,
        trip_request,
        [action("search_more", keyword="博物馆"), action("search_more", keyword="美术馆")],
        amap,
    )

    assert len(agent.prompts) == 2
    assert len(amap.search_calls) == 2
    assert len(result.trace) == 2
