class TripPlanningError(Exception):
    """旅行规划基础异常。"""


class ExternalServiceError(TripPlanningError):
    """高德、LLM 等外部服务不可用。"""


class AgentOutputError(TripPlanningError):
    """Agent 输出无法解析或不符合结构。"""


class PlanValidationError(TripPlanningError):
    """生成的行程没有通过业务约束校验。"""