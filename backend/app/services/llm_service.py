"""LLM服务模块"""
from threading import Lock

from hello_agents import HelloAgentsLLM


# 全局LLM实例
_llm_instance = None
_llm_lock = Lock()


def get_llm() -> HelloAgentsLLM:
    global _llm_instance

    if _llm_instance is None:#初始化完成后不用每次都判断锁
        with _llm_lock:
            if _llm_instance is None:#等待锁期间可能已经被另一个线程初始化
                _llm_instance = HelloAgentsLLM()

                print("✅ LLM服务初始化成功")
                print(f"   提供商: {_llm_instance.provider}")
                print(f"   模型: {_llm_instance.model}")

    return _llm_instance


def reset_llm():
    global _llm_instance

    with _llm_lock:
        _llm_instance = None
