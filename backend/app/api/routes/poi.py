"""POI相关API路由"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from typing import Annotated, List, Optional
from ...auth.dependencies import get_current_user
from ...config import get_settings
from ...db.models import User
from ...security.rate_limit import enforce_rate_limit
from ...services.amap_service import get_amap_service
from ...services.unsplash_service import get_unsplash_service

router = APIRouter(prefix="/poi", tags=["POI"])
settings = get_settings()


def _limit_external(request: Request, user: User) -> None:
    enforce_rate_limit(
        request,
        scope="external-poi",
        identifier=str(user.id),
        limit=settings.external_api_rate_limit_per_minute,
        window_seconds=60,
    )


class POIDetailResponse(BaseModel):
    """POI详情响应"""
    success: bool
    message: str
    data: Optional[dict] = None


@router.get(
    "/detail/{poi_id}",
    response_model=POIDetailResponse,
    summary="获取POI详情",
    description="根据POI ID获取详细信息,包括图片"
)
def get_poi_detail(
    poi_id: Annotated[str, Path(min_length=1, max_length=128)],
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """
    获取POI详情
    
    Args:
        poi_id: POI ID
        
    Returns:
        POI详情响应
    """
    _limit_external(request, current_user)
    try:
        amap_service = get_amap_service()
        
        # 调用高德地图POI详情API
        result = amap_service.get_poi_detail(poi_id)
        
        return POIDetailResponse(
            success=True,
            message="获取POI详情成功",
            data=result
        )
        
    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "POI_SERVICE_UNAVAILABLE", "message": "POI详情服务暂时不可用"},
        )


@router.get(
    "/search",
    summary="搜索POI",
    description="根据关键词搜索POI"
)
def search_poi(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    keywords: str = Query(..., min_length=1, max_length=80),
    city: str = Query("北京", min_length=1, max_length=50),
):
    """
    搜索POI

    Args:
        keywords: 搜索关键词
        city: 城市名称

    Returns:
        搜索结果
    """
    _limit_external(request, current_user)
    try:
        amap_service = get_amap_service()
        result = amap_service.search_poi(keywords, city)

        return {
            "success": True,
            "message": "搜索成功",
            "data": result
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "POI_SERVICE_UNAVAILABLE", "message": "POI搜索服务暂时不可用"},
        )


@router.get(
    "/photo",
    summary="获取景点图片",
    description="根据景点名称从Unsplash获取图片"
)
def get_attraction_photo(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    name: str = Query(..., min_length=1, max_length=100),
):
    """
    获取景点图片

    Args:
        name: 景点名称

    Returns:
        图片URL
    """
    _limit_external(request, current_user)
    try:
        unsplash_service = get_unsplash_service()

        # 搜索景点图片
        photo_url = unsplash_service.get_photo_url(f"{name} China landmark")

        if not photo_url:
            # 如果没找到,尝试只用景点名称搜索
            photo_url = unsplash_service.get_photo_url(name)

        return {
            "success": True,
            "message": "获取图片成功",
            "data": {
                "name": name,
                "photo_url": photo_url
            }
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail={"code": "PHOTO_SERVICE_UNAVAILABLE", "message": "图片服务暂时不可用"},
        )
