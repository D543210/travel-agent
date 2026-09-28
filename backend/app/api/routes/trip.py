"""旅行规划API路由"""

from fastapi import APIRouter, HTTPException
from ...models.schemas import (
    TripRequest,
    TripPlanResponse,
    ErrorResponse
)
from ...agents.trip_planner_agent import create_trip_planner

from ...exceptions import (
    AgentOutputError,
    ExternalServiceError,
    PlanValidationError,
    TripPlanningError,
)

from ...logging_context import log
from ...planning_concurrency import get_planning_capacity_limiter

router = APIRouter(prefix="/trip", tags=["旅行规划"])


@router.post(
    "/plan",
    response_model=TripPlanResponse,
    summary="生成旅行计划",
    description="根据用户输入的旅行需求,生成详细的旅行计划"
)
def plan_trip(request: TripRequest):
    """
    生成旅行计划

    Args:
        request: 旅行请求参数

    Returns:
        旅行计划响应
    """
    capacity_limiter = get_planning_capacity_limiter()

    if not capacity_limiter.try_acquire():
        raise HTTPException(
            status_code=429,
            detail={
                "status": "failed",
                "code": "TOO_MANY_TRIP_PLANS",
                "message": "当前规划任务较多，请稍后重试",
            },
            headers={"Retry-After": "5"},
        )

    try:
        log("=" * 60)
        log("📥 收到旅行规划请求")
        log(f"城市: {request.city}")
        log(
            f"日期: {request.start_date} - "
            f"{request.end_date}"
        )
        log(f"天数: {request.travel_days}")
        log("=" * 60)

        # 获取Agent实例
        log("🔄 创建本次请求的多智能体系统")
        agent = create_trip_planner()

        # 生成旅行计划
        log("🚀 开始生成旅行计划")
        trip_plan = agent.plan_trip(request)

        log("✅ 旅行计划生成成功")

        return TripPlanResponse(
            success=True,
            status=trip_plan.status,
            message=(
                "旅行计划已生成，部分外部信息获取失败"
                if trip_plan.status == "degraded"
                else "旅行计划生成成功"
            ),
            warnings=trip_plan.warnings,
            data=trip_plan
        )

    except ExternalServiceError:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "failed",
                "code": "EXTERNAL_SERVICE_UNAVAILABLE",
                "message": "外部数据服务暂时不可用，请稍后重试",
            },
        )

    except AgentOutputError:
        raise HTTPException(
            status_code=502,
            detail={
                "status": "failed",
                "code": "AGENT_OUTPUT_INVALID",
                "message": "模型生成结果未通过结构校验，请重新生成",
            },
        )

    except PlanValidationError:
        raise HTTPException(
            status_code=502,
            detail={
                "status": "failed",
                "code": "PLAN_VALIDATION_FAILED",
                "message": "生成的行程未通过可靠性校验，请重新生成",
            },
        )

    except TripPlanningError:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "failed",
                "code": "TRIP_PLANNING_FAILED",
                "message": "旅行规划失败，请稍后重试",
            },
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "failed",
                "code": "INTERNAL_ERROR",
                "message": "系统内部错误",
            },
        )
    finally:
        capacity_limiter.release()


@router.get(
    "/health",
    summary="健康检查",
    description="检查旅行规划服务是否正常"
)
def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "trip-planner",
    }
   
