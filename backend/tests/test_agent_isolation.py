from hello_agents.core.message import Message

from app.agents import trip_planner_agent


class DummyLLM:
    provider = "test"
    model = "test-model"


def test_factory_creates_isolated_planners_and_agents(monkeypatch):
    shared_llm = DummyLLM()

    monkeypatch.setattr(
        trip_planner_agent,
        "get_llm",
        lambda: shared_llm,
    )

    first = trip_planner_agent.create_trip_planner()
    second = trip_planner_agent.create_trip_planner()

    assert first is not second
    assert first.llm is second.llm
    assert first.attraction_agent is not second.attraction_agent
    assert first.hotel_agent is not second.hotel_agent
    assert first.planner_agent is not second.planner_agent

    first.attraction_agent.add_message(
        Message("仅属于请求A的消息", "user")
    )

    assert len(first.attraction_agent.get_history()) == 1
    assert second.attraction_agent.get_history() == []
