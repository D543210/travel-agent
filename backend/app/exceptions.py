class TripPlanningError(Exception):
    """旅行规划基础异常。"""


class ExternalServiceError(TripPlanningError):
    """高德、LLM 等外部服务不可用。"""


class AgentOutputError(TripPlanningError):
    """Agent 输出无法解析或不符合结构。"""


class PlanValidationError(TripPlanningError):
    """生成的行程没有通过业务约束校验。"""


class PlanFeasibilityError(PlanValidationError):
    """真实路线和固定游览时长使某一天超过时间预算。"""

    def __init__(
        self,
        *,
        day_index: int,
        visit_minutes: int,
        route_minutes: int,
        meal_minutes: int,
        available_minutes: int,
        attractions: list[dict],
        routes: list[dict],
    ) -> None:
        self.day_index = day_index
        self.visit_minutes = visit_minutes
        self.route_minutes = route_minutes
        self.meal_minutes = meal_minutes
        self.available_minutes = available_minutes
        self.attractions = attractions
        self.routes = routes
        required = visit_minutes + route_minutes + meal_minutes
        super().__init__(
            f"第{day_index + 1}天行程不可行：景点、路线和用餐"
            f"共需约{required}分钟（景点{visit_minutes}、路线"
            f"{route_minutes}、用餐{meal_minutes}），超过每日可用"
            f"{available_minutes}分钟"
        )
