import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.services import amap_service, llm_service


def _run_concurrently(callable_, count=20):
    with ThreadPoolExecutor(max_workers=count) as executor:
        return list(executor.map(lambda _: callable_(), range(count)))


def test_llm_singleton_initializes_once(monkeypatch):
    constructor_count = 0
    count_lock = threading.Lock()

    class FakeLLM:
        def __init__(self):
            nonlocal constructor_count

            with count_lock:
                constructor_count += 1

            time.sleep(0.05)
            self.provider = "test"
            self.model = "test-model"

    monkeypatch.setattr(llm_service, "HelloAgentsLLM", FakeLLM)
    monkeypatch.setattr(llm_service, "_llm_instance", None)

    instances = _run_concurrently(llm_service.get_llm)

    assert constructor_count == 1
    assert len({id(instance) for instance in instances}) == 1


def test_llm_initialization_can_retry_after_failure(monkeypatch):
    constructor_count = 0

    class FlakyLLM:
        def __init__(self):
            nonlocal constructor_count
            constructor_count += 1

            if constructor_count == 1:
                raise RuntimeError("expected initialization failure")

            self.provider = "test"
            self.model = "test-model"

    monkeypatch.setattr(llm_service, "HelloAgentsLLM", FlakyLLM)
    monkeypatch.setattr(llm_service, "_llm_instance", None)

    with pytest.raises(
        RuntimeError,
        match="expected initialization failure",
    ):
        llm_service.get_llm()

    instance = llm_service.get_llm()

    assert isinstance(instance, FlakyLLM)
    assert constructor_count == 2


def test_amap_mcp_tool_initializes_once(monkeypatch):
    constructor_count = 0
    count_lock = threading.Lock()

    class FakeMCPTool:
        def __init__(self, **kwargs):
            nonlocal constructor_count

            with count_lock:
                constructor_count += 1

            time.sleep(0.05)
            self._available_tools = []

    monkeypatch.setattr(amap_service, "MCPTool", FakeMCPTool)
    monkeypatch.setattr(amap_service, "_amap_mcp_tool", None)
    monkeypatch.setattr(
        amap_service,
        "get_settings",
        lambda: SimpleNamespace(amap_api_key="test-key"),
    )

    instances = _run_concurrently(amap_service.get_amap_mcp_tool)

    assert constructor_count == 1
    assert len({id(instance) for instance in instances}) == 1


def test_amap_service_initializes_once(monkeypatch):
    constructor_count = 0
    count_lock = threading.Lock()

    class FakeAmapService:
        def __init__(self):
            nonlocal constructor_count

            with count_lock:
                constructor_count += 1

            time.sleep(0.05)

    monkeypatch.setattr(amap_service, "AmapService", FakeAmapService)
    monkeypatch.setattr(amap_service, "_amap_service", None)

    instances = _run_concurrently(amap_service.get_amap_service)

    assert constructor_count == 1
    assert len({id(instance) for instance in instances}) == 1
