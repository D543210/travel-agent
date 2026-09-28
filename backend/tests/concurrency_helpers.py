"""并发测试使用的本地替身，不访问LLM或地图服务。"""

from app.models.schemas import TripPlan


def create_request_payload(city: str = "北京") -> dict:
    return {
        "city": city,
        "start_date": "2026-10-01",
        "end_date": "2026-10-01",
        "travel_days": 1,
        "transportation": "公共交通",
        "accommodation": "经济型酒店",
        "preferences": ["历史文化"],
        "free_text_input": "",
    }


def create_test_plan(request) -> TripPlan:
    return TripPlan(
        city=request.city,
        start_date=request.start_date,
        end_date=request.end_date,
        days=[],
        weather_info=[],
        overall_suggestions="自动化测试行程",
    )
