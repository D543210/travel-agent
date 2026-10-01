"""地图服务API路由"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Annotated, Optional
from ...auth.dependencies import get_current_user
from ...config import get_settings
from ...db.models import User
from ...models.schemas import (
    POISearchRequest,
    POISearchResponse,
    RouteRequest,
    RouteResponse,
    WeatherResponse
)
from ...services.amap_service import get_amap_service
from ...security.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/map", tags=["地图服务"])
settings = get_settings()


def _limit_external(request: Request, user: User) -> None:
    enforce_rate_limit(
        request,
        scope="external-map",
        identifier=str(user.id),
        limit=settings.external_api_rate_limit_per_minute,
        window_seconds=60,
    )


@router.get(
    "/poi",
    response_model=POISearchResponse,
    summary="搜索POI",
    description="根据关键词搜索POI(兴趣点)"
)
def search_poi(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    keywords: str = Query(..., min_length=1, max_length=80, description="搜索关键词", examples=["故宫"]),
    city: str = Query(..., min_length=1, max_length=50, description="城市", examples=["北京"]),
    citylimit: bool = Query(True, description="是否限制在城市范围内")
):
    """
    搜索POI
    
    Args:
        keywords: 搜索关键词
        city: 城市
        citylimit: 是否限制在城市范围内
        
    Returns:
        POI搜索结果
    """
    _limit_external(request, current_user)
    try:
        # 获取服务实例
        service = get_amap_service()
        
        # 搜索POI
        pois = service.search_poi(keywords, city, citylimit)
        
        return POISearchResponse(
            success=True,
            message="POI搜索成功",
            data=pois
        )
        
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "POI_SERVICE_UNAVAILABLE", "message": "POI服务暂时不可用"},
        )


@router.get(
    "/weather",
    response_model=WeatherResponse,
    summary="查询天气",
    description="查询指定城市的天气信息"
)
def get_weather(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    city: str = Query(..., min_length=1, max_length=50, description="城市名称", examples=["北京"])
):
    """
    查询天气
    
    Args:
        city: 城市名称
        
    Returns:
        天气信息
    """
    _limit_external(request, current_user)
    try:
        # 获取服务实例
        service = get_amap_service()
        
        # 查询天气
        weather_info = service.get_weather(city)
        
        return WeatherResponse(
            success=True,
            message="天气查询成功",
            data=weather_info
        )
        
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "WEATHER_SERVICE_UNAVAILABLE", "message": "天气服务暂时不可用"},
        )


@router.post(
    "/route",
    response_model=RouteResponse,
    summary="规划路线",
    description="规划两点之间的路线"
)
def plan_route(
    route_request: RouteRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    规划路线
    
    Args:
        request: 路线规划请求
        
    Returns:
        路线信息
    """
    _limit_external(request, current_user)
    try:
        # 获取服务实例
        service = get_amap_service()
        
        # 规划路线
        route_info = service.plan_route(
            origin_address=route_request.origin_address,
            destination_address=route_request.destination_address,
            origin_city=route_request.origin_city,
            destination_city=route_request.destination_city,
            route_type=route_request.route_type
        )
        
        return RouteResponse(
            success=True,
            message="路线规划成功",
            data=route_info
        )
        
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "ROUTE_SERVICE_UNAVAILABLE", "message": "路线服务暂时不可用"},
        )


@router.get(
    "/health",
    summary="健康检查",
    description="检查地图服务是否正常"
)
def health_check():
    """健康检查"""
    try:
        # 检查服务是否可用
        service = get_amap_service()
        
        return {
            "status": "healthy",
            "service": "map-service",
            "mcp_tools_count": len(service.mcp_tool._available_tools)
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "MAP_SERVICE_UNAVAILABLE", "message": "地图服务不可用"},
        )
