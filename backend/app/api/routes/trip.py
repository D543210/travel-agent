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
    try:
        print(f"\n{'='*60}")
        print(f"📥 收到旅行规划请求:")
        print(f"   城市: {request.city}")
        print(f"   日期: {request.start_date} - {request.end_date}")
        print(f"   天数: {request.travel_days}")
        print(f"{'='*60}\n")

        # 获取Agent实例
        print("🔄 获取多智能体系统实例...")
        agent = create_trip_planner()

        # 生成旅行计划
        print("🚀 开始生成旅行计划...")
        trip_plan = agent.plan_trip(request)

        print("✅ 旅行计划生成成功,准备返回响应\n")

        return TripPlanResponse(
            success=True,
            message="旅行计划生成成功",
            data=trip_plan
        )

    except ExternalServiceError:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "EXTERNAL_SERVICE_UNAVAILABLE",
                "message": "外部数据服务暂时不可用，请稍后重试",
            },
        )

    except AgentOutputError:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "AGENT_OUTPUT_INVALID",
                "message": "模型生成结果未通过结构校验，请重新生成",
            },
        )

    except PlanValidationError:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "PLAN_VALIDATION_FAILED",
                "message": "生成的行程未通过可靠性校验，请重新生成",
            },
        )

    except TripPlanningError:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "TRIP_PLANNING_FAILED",
                "message": "旅行规划失败，请稍后重试",
            },
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "系统内部错误",
            },
        )


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
   
