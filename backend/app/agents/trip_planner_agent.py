"""多智能体旅行规划系统"""

import json
from datetime import date, timedelta
from math import ceil
from typing import Dict, Any, Callable, List
from hello_agents import SimpleAgent
from ..services.llm_service import get_llm
from ..models.schemas import (
    TripRequest,
    TripPlan,
    WeatherInfo,
    POIInfo,
    AttractionSelection,
    HotelSelection,
    RestaurantSelection,
    TravelLeg,
)
from ..config import get_settings
from ..services.amap_service import get_amap_service
from ..services.mcp_response_parser import extract_json_value,MCPResponseParseError
from pydantic import ValidationError

from ..exceptions import (
    AgentOutputError,
    ExternalServiceError,
    PlanFeasibilityError,
    PlanValidationError,
    TripPlanningError,
)

from .tool_decision import run_tool_decisions

from ..logging_context import log

# 修正时最多缩短原建议时长的20%；低于90分钟的建议不再缩短。
MAX_VISIT_REDUCTION_RATIO = 0.20
MIN_REPAIRED_VISIT_MINUTES = 90

ProgressCallback = Callable[[str, int, int, str], None]

# ============ Agent提示词 ============

ATTRACTION_AGENT_PROMPT = """你是景点筛选专家。

你的任务是根据用户偏好，从输入提供的候选景点中选择合适的景点。

你必须严格遵守以下规则：

1. 只能选择候选景点中真实存在的poi_id
2. 不得创建、修改或猜测poi_id
3. 不得修改景点名称、地址、类型和坐标
4. 根据旅行天数和用户偏好进行选择
5. 每个景点提供推荐原因和建议游览时长
6. 建议游览时长必须在30到480分钟之间
7. 只返回JSON，不要返回Markdown代码块或额外说明

返回格式：

{
  "attractions": [
    {
      "poi_id": "候选景点中的真实ID",
      "reason": "推荐原因",
      "suggested_duration": 120
    }
  ]
}
"""

HOTEL_AGENT_PROMPT = """你是酒店筛选专家。

你的任务是根据用户的住宿偏好和景点位置，
从输入提供的真实候选酒店中选择合适的酒店。

必须严格遵守以下规则：

1. 只能选择候选酒店中真实存在的poi_id
2. 不得创建、修改或猜测poi_id
3. 不得修改酒店名称、地址、类型和坐标
4. 根据住宿偏好和主要景点位置进行选择
5. 每家酒店需要提供推荐理由
6. 只返回JSON，不要返回Markdown代码块或额外说明

返回格式：

{
  "hotels": [
    {
      "poi_id": "候选酒店中的真实ID",
      "reason": "推荐原因"
    }
  ]
}
"""

RESTAURANT_AGENT_PROMPT = """你是餐厅筛选专家。

请根据用户偏好从真实候选餐厅中选择适合早、中、晚餐的餐厅。
只能返回候选列表中存在的poi_id，不得创建、修改或猜测poi_id，
不得修改名称、地址、类型或坐标。请选择3至10家，并给出推荐原因。
只返回JSON，不要返回Markdown代码块或额外说明。

返回格式：
{
  "restaurants": [
    {"poi_id": "候选餐厅中的真实ID", "reason": "推荐原因"}
  ]
}
"""

PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "poi_id": "高德酒店POI ID",
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "poi_id": "高德POI ID",
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"poi_id": "高德餐厅POI ID", "type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"poi_id": "高德餐厅POI ID", "type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"poi_id": "高德餐厅POI ID", "type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

**重要提示:**
1. **景点信息必须严格使用输入中提供的数据**：
   - 只能安排输入中存在的景点
   - 每个景点必须保留原始poi_id
   - 不得创建或修改poi_id
   - 不得修改景点名称、地址、经纬度和类别
   - 不得生成输入中不存在的景点
2. **weather_info只能使用“天气信息”中实际提供的数据**:
  - 不得推测、补全或生成输入中不存在日期的天气
  - 不得修改输入天气的日期、天气、温度、风向和风力
  - 如果某个旅行日期没有天气数据，则不要在weather_info中生成该日期
3. **酒店信息必须严格使用输入提供的数据**：
  - 每天的hotel必须包含poi_id
  - 只能使用酒店信息中存在的poi_id
  - 不得修改酒店名称、地址、坐标和类型
  - 不得生成输入中不存在的酒店
4. 温度必须是纯数字(不要带°C等单位)
5. 每天安排2-3个景点
6. 考虑景点之间的距离和游览时间
7. 每天必须包含早中晚三餐
8. **餐厅信息必须严格使用输入提供的数据**：每餐必须保留真实poi_id，不得修改名称、地址和坐标
9. 提供实用的旅行建议
10. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(self):
        """初始化多智能体系统"""
        log("🔄 开始初始化多智能体旅行规划系统")

        try:
            self.llm = get_llm()

            # 创建景点搜索Agent
            print("  - 创建景点搜索Agent...")
            self.attraction_agent = SimpleAgent(
                name="景点搜索专家",
                llm=self.llm,
                system_prompt=ATTRACTION_AGENT_PROMPT
            )

            # 创建酒店推荐Agent
            print("  - 创建酒店推荐Agent...")
            self.hotel_agent = SimpleAgent(
                name="酒店推荐专家",
                llm=self.llm,
                system_prompt=HOTEL_AGENT_PROMPT
            )

            print("  - 创建餐厅推荐Agent...")
            self.restaurant_agent = SimpleAgent(
                name="餐厅推荐专家",
                llm=self.llm,
                system_prompt=RESTAURANT_AGENT_PROMPT,
            )

            # 创建行程规划Agent(不需要工具)
            print("  - 创建行程规划Agent...")
            self.planner_agent = SimpleAgent(
                name="行程规划专家",
                llm=self.llm,
                system_prompt=PLANNER_AGENT_PROMPT
            )

            print(f"✅ 多智能体系统初始化成功")
            print(f"   景点搜索Agent: {len(self.attraction_agent.list_tools())} 个工具")
            print(f"   酒店推荐Agent: {len(self.hotel_agent.list_tools())} 个工具")

        except Exception as e:
            print(f"❌ 多智能体系统初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def plan_trip(
        self,
        request: TripRequest,
        progress_callback: ProgressCallback | None = None,
    ) -> TripPlan:
        """
        使用多智能体协作生成旅行计划

        Args:
            request: 旅行请求

        Returns:
            旅行计划
        """
        try:
            warnings: List[str] = []
            log("开始多智能体协作规划旅行")


            # 获取高德服务，后续景点和天气共用
            amap_service = get_amap_service()

            # 步骤1: 通过Service获取真实景点，再由Agent进行筛选
            self._emit_progress(
                progress_callback,
                "searching_attractions",
                1,
                10,
                "正在查询真实景点",
            )
            log("📍 步骤1: 获取并筛选景点")
            attraction_keyword = (
                request.preferences[0]
                if request.preferences
                else "景点"
            )
            try:
                attraction_candidates = amap_service.search_poi(
                    keywords=attraction_keyword,
                    city=request.city
                )

            except Exception as error:
                raise ExternalServiceError(
                    "景点数据服务暂时不可用"
                )from error

            log(
                f"获取到真实景点候选: "
                f"{len(attraction_candidates)}个"
            )

            # 步骤2: 通过天气service查询天气信息
            self._emit_progress(
                progress_callback, "fetching_weather", 2, 10, "正在查询天气"
            )
            log("🌤️ 步骤2: 查询天气")

            # 使用高德服务直接查询天气
            weather_info_list : List[WeatherInfo] = []

            try:
                weather_info_list = amap_service.get_weather(request.city)
                print("Service天气数量：",len(weather_info_list))

            except Exception as e:
                print(f"⚠️ 天气查询失败，继续生成无天气行程: {str(e)}")
                warnings.append("天气服务不可用，行程未包含天气信息")

            weather_response = json.dumps(
                [weather.model_dump() for weather in weather_info_list],
                ensure_ascii=False,
                indent=2
            )
            log("天气数据准备完成")


            self._emit_progress(
                progress_callback,
                "tool_decision",
                3,
                10,
                "正在分析是否需要补充数据",
            )
            decision_result = run_tool_decisions(
                request=request,
                initial_candidates=attraction_candidates,
                weather=weather_info_list,
                amap_service=amap_service,
                llm=self.llm,
                route_type=self._route_type_for_transportation(
                    request.transportation
                ),
            )

            attraction_candidates = decision_result.candidates
            route_hints = decision_result.route_hints


            minimum_required = request.travel_days * 2
            maximum_required = min(len(attraction_candidates), request.travel_days * 3,)

            if len(attraction_candidates) < minimum_required:
                raise PlanValidationError(
                    f"有效景点候选不足："
                    f"当前只有{len(attraction_candidates)}个，"
                    f"{request.travel_days}天行程至少需要"
                    f"{minimum_required}个"
                )

            attraction_query = self._build_attraction_query(
                request=request,
                candidates=attraction_candidates,
                route_hints=route_hints,
            )

            self._emit_progress(
                progress_callback,
                "selecting_attractions",
                4,
                10,
                "正在筛选景点",
            )
            try:
                attraction_response = self.attraction_agent.run(
                    attraction_query
                )

            except Exception as error:
                raise ExternalServiceError(
                    "景点筛选模型暂时不可用"
                ) from error

            log("景点筛选完成")

            attraction_selection_data = extract_json_value(
                attraction_response
            )

            if not isinstance(attraction_selection_data, dict):
                raise AgentOutputError(
                    "景点Agent返回的不是JSON对象"
                )
            
            attraction_selection = AttractionSelection.model_validate(
                attraction_selection_data
            )
            selection_count = len(attraction_selection.attractions)

            if selection_count < minimum_required:
                raise PlanValidationError(
                    f"景点Agent选择数量不足："
                    f"实际选择{selection_count}个，"
                    f"至少需要{minimum_required}个"
                )

            if selection_count > maximum_required:
                raise PlanValidationError(
                    f"景点Agent选择数量过多："
                    f"实际选择{selection_count}个，"
                    f"最多允许{maximum_required}个"
                )
                        
            print(
                f"景点Agent选择了"
                f"{len(attraction_selection.attractions)}个景点"
            )

            # 建立真实候选POI的索引
            candidate_by_id = {
                poi.id: poi
                for poi in attraction_candidates
            }

            selected_ids = [
                item.poi_id
                for item in attraction_selection.attractions
            ]

            # 检查重复ID
            if len(selected_ids) != len(set(selected_ids)):
                raise PlanValidationError(
                    "景点Agent返回了重复的POI ID"
                )
            
            # 检查未知ID
            unknown_ids = [
                poi_id
                for poi_id in selected_ids
                if poi_id not in candidate_by_id
            ]

            if unknown_ids:
                raise PlanValidationError(
                    f"景点Agent返回了候选列表之外的POI ID: {unknown_ids}"
                )
            selected_by_id = {
                item.poi_id: item
                for item in attraction_selection.attractions
            }

            selected_id_set = set(selected_by_id)
            
            trusted_attractions = []

            for selected in attraction_selection.attractions:
                source_poi = candidate_by_id[selected.poi_id]

                trusted_attractions.append({
                    "poi_id": source_poi.id,
                    "name": source_poi.name,
                    "address": source_poi.address,
                    "location": source_poi.location.model_dump(),
                    "category": source_poi.type,
                    "visit_duration": selected.suggested_duration,
                    "description": selected.reason
                })

            trusted_attractions_json = json.dumps(
                trusted_attractions,
                ensure_ascii=False,
                indent=2
            )


            # 步骤3: 酒店推荐Agent搜索酒店
            self._emit_progress(
                progress_callback,
                "selecting_hotel",
                5,
                10,
                "正在查询并筛选酒店",
            )
            log("🏨 步骤3: 搜索酒店")
            hotel_query = f"请搜索{request.city}的{request.accommodation}"
            hotel_keyword = request.accommodation.strip()

            if not hotel_keyword.endswith(("酒店", "宾馆")):
                hotel_keyword += "酒店"
            try:
                hotel_candidates = amap_service.search_poi(
                    keywords=hotel_keyword,
                    city=request.city,
                )
            except Exception as error:
                raise ExternalServiceError(
                    "酒店数据服务暂时不可用"
                ) from error

            candidate_hotel_by_id = {
                hotel.id: hotel
                for hotel in hotel_candidates
            }
            selected_attraction_pois = [
                candidate_by_id[item.poi_id]
                for item in attraction_selection.attractions
            ]

            hotel_query = self._build_hotel_query(
                request=request,
                candidates=hotel_candidates,
                selected_attractions=selected_attraction_pois
            )
            try:
                hotel_response = self.hotel_agent.run(
                    hotel_query
                )

            except Exception as error:
                raise ExternalServiceError(
                    "酒店筛选模型暂时不可用"
                ) from error

            log("酒店筛选完成")
            try:
                hotel_selection_data = extract_json_value(
                    hotel_response
                )

                if not isinstance(hotel_selection_data, dict):
                    raise AgentOutputError(
                        "酒店Agent返回的不是JSON对象"
                    )

                hotel_selection = HotelSelection.model_validate(
                    hotel_selection_data
                )

            except MCPResponseParseError as error:
                raise AgentOutputError(
                    "酒店Agent响应中没有合法JSON"
                ) from error

            except ValidationError as error:
                raise AgentOutputError(
                    "酒店Agent返回的数据不符合HotelSelection结构"
                ) from error

            selection_count = len(hotel_selection.hotels)

            if selection_count < 1 or selection_count > 3:
                raise PlanValidationError(
                    f"酒店Agent选择数量不合理：{selection_count}家，"
                    "要求选择1至3家"
                )

            selected_hotel_ids = [
                hotel.poi_id
                for hotel in hotel_selection.hotels
            ]

            if len(selected_hotel_ids) != len(set(selected_hotel_ids)):
                raise PlanValidationError("酒店Agent返回了重复的POI ID")

            unknown_ids = [
                poi_id
                for poi_id in selected_hotel_ids
                if poi_id not in candidate_hotel_by_id
            ]

            if unknown_ids:
                raise PlanValidationError(
                    f"酒店Agent返回了候选列表之外的POI ID: {unknown_ids}"
                )


            selected_hotel_id_set = set(selected_hotel_ids)

            # 7. 生成可信酒店数据
            trusted_hotels = [
                {
                    "poi_id": candidate_hotel_by_id[item.poi_id].id,
                    "name": candidate_hotel_by_id[item.poi_id].name,
                    "address": candidate_hotel_by_id[item.poi_id].address,
                    "location": (
                        candidate_hotel_by_id[item.poi_id]
                        .location.model_dump()
                    ),
                    "type": candidate_hotel_by_id[item.poi_id].type,
                    "reason": item.reason,
                }
                for item in hotel_selection.hotels
            ]

            trusted_hotels_json = json.dumps(
                trusted_hotels,
                ensure_ascii=False,
                indent=2,
            )

            # 步骤4: 获取真实餐厅并由Agent筛选，形成餐厅POI可信闭环
            self._emit_progress(
                progress_callback,
                "selecting_restaurants",
                6,
                10,
                "正在查询并筛选餐厅",
            )
            log("🍽️ 步骤4: 获取并筛选餐厅")
            try:
                restaurant_candidates = amap_service.search_poi(
                    keywords="美食餐厅",
                    city=request.city,
                )
            except Exception as error:
                raise ExternalServiceError("餐厅数据服务暂时不可用") from error

            if len(restaurant_candidates) < 3:
                raise PlanValidationError(
                    f"有效餐厅候选不足：当前只有{len(restaurant_candidates)}家，至少需要3家"
                )

            candidate_restaurant_by_id = {
                restaurant.id: restaurant for restaurant in restaurant_candidates
            }
            restaurant_query = self._build_restaurant_query(
                request=request,
                candidates=restaurant_candidates,
            )
            try:
                restaurant_response = self.restaurant_agent.run(restaurant_query)
            except Exception as error:
                raise ExternalServiceError("餐厅筛选模型暂时不可用") from error

            try:
                restaurant_data = extract_json_value(restaurant_response)
                if not isinstance(restaurant_data, dict):
                    raise AgentOutputError("餐厅Agent返回的不是JSON对象")
                restaurant_selection = RestaurantSelection.model_validate(
                    restaurant_data
                )
            except MCPResponseParseError as error:
                raise AgentOutputError("餐厅Agent响应中没有合法JSON") from error
            except ValidationError as error:
                raise AgentOutputError(
                    "餐厅Agent返回的数据不符合RestaurantSelection结构"
                ) from error

            selected_restaurant_ids = [
                restaurant.poi_id
                for restaurant in restaurant_selection.restaurants
            ]
            if not 3 <= len(selected_restaurant_ids) <= min(
                10, len(restaurant_candidates)
            ):
                raise PlanValidationError("餐厅Agent必须选择3至10家真实候选餐厅")
            if len(selected_restaurant_ids) != len(set(selected_restaurant_ids)):
                raise PlanValidationError("餐厅Agent返回了重复的POI ID")
            unknown_restaurants = [
                poi_id
                for poi_id in selected_restaurant_ids
                if poi_id not in candidate_restaurant_by_id
            ]
            if unknown_restaurants:
                raise PlanValidationError(
                    f"餐厅Agent返回了候选列表之外的POI ID: {unknown_restaurants}"
                )

            selected_restaurant_id_set = set(selected_restaurant_ids)
            restaurant_reason_by_id = {
                restaurant.poi_id: restaurant.reason
                for restaurant in restaurant_selection.restaurants
            }
            trusted_restaurants_json = json.dumps(
                [
                    {
                        "poi_id": candidate_restaurant_by_id[poi_id].id,
                        "name": candidate_restaurant_by_id[poi_id].name,
                        "address": candidate_restaurant_by_id[poi_id].address,
                        "location": candidate_restaurant_by_id[
                            poi_id
                        ].location.model_dump(),
                        "type": candidate_restaurant_by_id[poi_id].type,
                        "reason": restaurant_reason_by_id[poi_id],
                    }
                    for poi_id in selected_restaurant_ids
                ],
                ensure_ascii=False,
                indent=2,
            )

            # 步骤5: 行程规划Agent整合信息生成计划
            self._emit_progress(
                progress_callback,
                "generating_plan",
                7,
                10,
                "模型正在生成行程",
            )
            log("📋 步骤5: 生成行程计划")
            planner_query = self._build_planner_query(
                request,
                trusted_attractions_json,
                weather_response,
                trusted_hotels_json,
                trusted_restaurants_json,
            )
            try:
                planner_response = self.planner_agent.run(
                    planner_query
                )
            except Exception as error:
                raise ExternalServiceError(
                    "行程规划模型暂时不可用"
                ) from error
            log("行程模型输出完成")

            # 只在真实路线导致超时的情况下给规划 Agent 一次修正机会。
            # 两次校验共用路线缓存，避免重复请求相同的地图路线。
            route_cache = {}
            for attempt in range(2):
                trip_plan = self._parse_response(planner_response, request)
                try:
                    route_warnings = self._validate_and_hydrate_generated_plan(
                        trip_plan=trip_plan,
                        request=request,
                        candidate_by_id=candidate_by_id,
                        selected_id_set=selected_id_set,
                        selected_by_id=selected_by_id,
                        selected_hotel_id_set=selected_hotel_id_set,
                        candidate_hotel_by_id=candidate_hotel_by_id,
                        selected_restaurant_id_set=selected_restaurant_id_set,
                        candidate_restaurant_by_id=candidate_restaurant_by_id,
                        restaurant_reason_by_id=restaurant_reason_by_id,
                        amap_service=amap_service,
                        route_cache=route_cache,
                        allow_duration_adjustment=(attempt == 1),
                        progress_callback=progress_callback,
                    )
                except PlanFeasibilityError as error:
                    if attempt == 1:
                        raise
                    log(f"行程超时，要求规划 Agent 修正一次: {error}")
                    self._emit_progress(
                        progress_callback,
                        "repairing_plan",
                        8,
                        10,
                        "真实路线校验超时，正在修正行程",
                    )
                    repair_feedback = {
                        "day_index": error.day_index,
                        "visit_minutes": error.visit_minutes,
                        "route_minutes": error.route_minutes,
                        "meal_minutes": error.meal_minutes,
                        "available_minutes": error.available_minutes,
                        "over_minutes": (
                            error.visit_minutes + error.route_minutes
                            + error.meal_minutes - error.available_minutes
                        ),
                        "attractions": error.attractions,
                        "routes": error.routes,
                        "allowed_visit_minutes": [
                            {
                                "poi_id": item.poi_id,
                                "minimum": self._minimum_repaired_visit_minutes(
                                    item.suggested_duration
                                ),
                                "maximum": item.suggested_duration,
                            }
                            for item in selected_by_id.values()
                        ],
                    }
                    repair_query = (
                        planner_query
                        + "\n\n**修正上次行程（只允许一次）:**\n"
                        + "上次行程根据真实地图路线校验后超时。"
                        + "本次修正每天只能安排2个景点，不能保留造成超时的三景点组合。"
                        + "优先替换路线耗时最长的景点或选择更近的已选酒店，"
                        + "同时调整景点顺序，预留酒店往返和三餐时间。"
                        + "可以在校验反馈的allowed_visit_minutes范围内"
                        + "为每个景点重新填写visit_duration；请计算总时间，"
                        + "让景点停留、真实路线和三餐预留不超过每日上限。"
                        + "生成完整的新JSON行程，"
                        + "不要使用未提供的景点、酒店或餐厅POI ID。"
                        + "保持日期、三餐和预算结构完整。\n"
                        + "校验反馈: "
                        + json.dumps(repair_feedback, ensure_ascii=False)
                        + "\n上次行程: "
                        + trip_plan.model_dump_json()
                    )
                    try:
                        planner_response = self.planner_agent.run(repair_query)
                    except Exception as model_error:
                        raise ExternalServiceError(
                            "行程修正模型暂时不可用"
                        ) from model_error
                    continue
                warnings.extend(route_warnings)
                break
            trusted_weather_info = [
                weather
                for weather in weather_info_list
                if request.start_date <= weather.date <= request.end_date
            ]

            trip_plan.weather_info = trusted_weather_info
            self._emit_progress(
                progress_callback,
                "normalizing_budget",
                9,
                10,
                "正在重算预算",
            )
            self._normalize_and_validate_budget(trip_plan)
            trip_plan.warnings = warnings
            trip_plan.status = "degraded" if warnings else "success"


            print(f"{'='*60}")
            log("✅ 旅行计划生成完成")
            print(f"{'='*60}\n")

            return trip_plan

        except Exception as e:
            log(f"旅行计划生成失败: {type(e).__name__}")
            raise
    
    def _validate_and_hydrate_generated_plan(
        self,
        *,
        trip_plan: TripPlan,
        request: TripRequest,
        candidate_by_id: Dict[str, POIInfo],
        selected_id_set: set[str],
        selected_by_id: Dict[str, Any],
        selected_hotel_id_set: set[str],
        candidate_hotel_by_id: Dict[str, POIInfo],
        selected_restaurant_id_set: set[str],
        candidate_restaurant_by_id: Dict[str, POIInfo],
        restaurant_reason_by_id: Dict[str, str],
        amap_service,
        route_cache: dict,
        allow_duration_adjustment: bool = False,
        progress_callback: ProgressCallback | None = None,
    ) -> List[str]:
        """每次都从头校验并回填可信 POI；修正计划也走同一套校验。"""
        warnings: List[str] = []
        self._validate_plan_against_request(trip_plan, request)

        # 校验规划Agent使用的景点是否全部来自真实候选列表
        scheduled_poi_ids = set()

        for day in trip_plan.days:

            # 酒店校验
            if day.hotel is None:
                raise PlanValidationError(
                    f"第{day.day_index + 1}天缺少酒店"
                )

            if not day.hotel.poi_id:
                raise PlanValidationError(
                    f"第{day.day_index + 1}天的酒店缺少poi_id"
                )

            if day.hotel.poi_id not in selected_hotel_id_set:
                raise PlanValidationError(
                    f"第{day.day_index + 1}天使用了"
                    f"酒店Agent未选中的POI ID：{day.hotel.poi_id}"
                )

            source_hotel = candidate_hotel_by_id[day.hotel.poi_id]

            # 用高德真实数据覆盖规划Agent输出
            day.hotel.name = source_hotel.name
            day.hotel.address = source_hotel.address
            day.hotel.location = source_hotel.location.model_copy(deep=True)
            day.hotel.type = source_hotel.type



            attraction_count = len(day.attractions)

            if attraction_count < 2 or attraction_count > 3:
                raise PlanValidationError(
                    f"第{day.day_index + 1}天的景点数量不合理: "
                    f"{attraction_count}个，要求每天2到3个"
                )

            for attraction in day.attractions:
                if not attraction.poi_id:
                    raise PlanValidationError(
                        f"第{day.day_index + 1}天的景点"
                        f"“{attraction.name}”缺少poi_id"
                    )

                if attraction.poi_id not in candidate_by_id:
                    raise PlanValidationError(
                        f"第{day.day_index + 1}天使用了未知景点POI ID: "
                        f"{attraction.poi_id}"
                    )

                if attraction.poi_id not in selected_id_set:
                    raise PlanValidationError(
                        f"第{day.day_index + 1}天使用了"
                        f"景点Agent未选中的POI ID："
                        f"{attraction.poi_id}"
                    )

                if attraction.poi_id in scheduled_poi_ids:
                    raise PlanValidationError(
                        f"景点被重复安排: {attraction.poi_id}"
                    )

                scheduled_poi_ids.add(attraction.poi_id)

                source_poi = candidate_by_id[attraction.poi_id]

                selected = selected_by_id[attraction.poi_id]

                attraction.name = source_poi.name
                attraction.address = source_poi.address
                attraction.location = source_poi.location.model_copy(deep=True)
                attraction.category = source_poi.type
                if allow_duration_adjustment:
                    # 只在修正轮允许模型缩短“建议”时长；地点事实仍由 POI 回填。
                    minimum = self._minimum_repaired_visit_minutes(
                        selected.suggested_duration
                    )
                    if not minimum <= attraction.visit_duration <= selected.suggested_duration:
                        raise PlanValidationError(
                            f"景点{source_poi.name}的修正停留时间"
                            f"必须在{minimum}至{selected.suggested_duration}分钟之间"
                        )
                else:
                    attraction.visit_duration = selected.suggested_duration
                attraction.description = selected.reason

            self._validate_and_hydrate_meals(
                day=day,
                selected_restaurant_id_set=selected_restaurant_id_set,
                candidate_restaurant_by_id=candidate_restaurant_by_id,
                restaurant_reason_by_id=restaurant_reason_by_id,
            )

            route_warnings = self._populate_routes_and_validate_feasibility(
                day=day,
                city=request.city,
                requested_transportation=request.transportation,
                amap_service=amap_service,
                route_cache=route_cache,
                progress_callback=progress_callback,
            )
            warnings.extend(route_warnings)
        return warnings

    @staticmethod
    def _minimum_repaired_visit_minutes(suggested_duration: int) -> int:
        """防止模型通过极短停留时间凑过每日时间预算。"""
        return min(
            suggested_duration,
            max(
                MIN_REPAIRED_VISIT_MINUTES,
                ceil(suggested_duration * (1 - MAX_VISIT_REDUCTION_RATIO)),
            ),
        )

    def _build_attraction_query(self, request: TripRequest,candidates:List[POIInfo],route_hints: List[str] | None = None,) -> str:
        """把真实POI候选数据传给景点Agent进行筛选"""

        candidate_data = [
            poi.model_dump()
            for poi in candidates
        ]

        candidate_json = json.dumps(
            candidate_data,
            ensure_ascii=False,
            indent=2
        )

        minimum_required = request.travel_days * 2
        maximum_required = min(
            len(candidates),
            request.travel_days * 3,
        )


        route_hint_text = "\n".join(route_hints or []) or "无"

        return f"""请从候选景点中选择适合本次旅行的景点。

旅行信息：
- 城市：{request.city}
- 旅行天数：{request.travel_days}
- 用户偏好：{", ".join(request.preferences) if request.preferences else "无"}
- 最少选择数量：{minimum_required}个
- 最多选择数量：{maximum_required}个


候选景点：
{candidate_json}

只允许选择候选列表中的POI ID。
选择数量必须在{minimum_required}到{maximum_required}之间。

候选景点之间的路线预查信息（仅作筛选参考）：
{route_hint_text}

请严格按照系统提示词规定的JSON格式返回结果。
"""

    def _build_hotel_query(self, request: TripRequest, candidates:List[POIInfo], selected_attractions:List[POIInfo]) -> str:
        candidate_data = [
            poi.model_dump()
            for poi in candidates
        ]

        candidate_json = json.dumps(
            candidate_data,
            ensure_ascii=False,
            indent=2
        )

        attraction_json = json.dumps(
                [attraction.model_dump() for attraction in selected_attractions],
                ensure_ascii=False,
                indent=2,
            )

        return f"""请从候选酒店中选择适合本次旅行的酒店。

旅行信息：
- 城市：{request.city}
- 住宿偏好：{request.accommodation}
- 旅行天数：{request.travel_days}

已选景点：
{attraction_json}

候选酒店：
{candidate_json}

请选择1至3家酒店。
只能选择候选列表中的POI ID。
请严格按照系统提示词规定的JSON格式返回结果。
"""

    def _build_restaurant_query(
        self,
        request: TripRequest,
        candidates: List[POIInfo],
    ) -> str:
        candidate_json = json.dumps(
            [poi.model_dump() for poi in candidates],
            ensure_ascii=False,
            indent=2,
        )
        return f"""请从候选餐厅中选择适合本次旅行早、中、晚餐的餐厅。

旅行信息：
- 城市：{request.city}
- 旅行天数：{request.travel_days}
- 用户偏好：{", ".join(request.preferences) if request.preferences else "无"}

候选餐厅：
{candidate_json}

请选择3至{min(10, len(candidates))}家餐厅，只能使用候选列表中的POI ID。
请严格按照系统提示词规定的JSON格式返回结果。
"""

    def _build_planner_query(
        self,
        request: TripRequest,
        attractions: str,
        weather: str,
        hotels: str = "",
        restaurants: str = "",
    ) -> str:
        """构建行程规划查询"""
        settings = get_settings()
        route_budget = (
            settings.daily_available_minutes
            - settings.daily_meal_buffer_minutes
        )
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息:**
{attractions}

**天气信息:**
{weather}

**酒店信息:**
{hotels}

**餐厅信息:**
{restaurants}

**每日时间预算（必须遵守）:**
- 每日可用时间：{settings.daily_available_minutes}分钟。
- 早、中、晚餐固定预留：{settings.daily_meal_buffer_minutes}分钟。
- 景点游览与全部交通路线合计最多：{route_budget}分钟。
- 首稿使用景点信息中的建议visit_duration；如真实路线校验超时，系统最多允许一次受限修正。
- 修正时每个景点最多缩短原建议的20%，且通常不能低于90分钟；后端会再次校验时间与真实路线。
- 路线包括酒店出发、景点之间、返回酒店。优先选相距较近的2个景点；只有时间足够时才选3个。
- 最终行程会根据真实地图路线耗时重新校验，超时会被拒绝。

**要求:**
1. 每天安排2-3个景点
2. 每天必须且只能包含breakfast、lunch、dinner各一餐，餐厅必须从餐厅信息中选择并保留poi_id
3. 每天推荐一个具体的酒店(从酒店信息中选择)
4. 考虑景点之间的距离和交通方式
5. 返回完整的JSON格式数据
6. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query

    def _validate_and_hydrate_meals(
        self,
        day,
        selected_restaurant_id_set: set[str],
        candidate_restaurant_by_id: Dict[str, POIInfo],
        restaurant_reason_by_id: Dict[str, str],
    ) -> None:
        """校验一日三餐，并用真实POI覆盖模型生成的事实字段。"""
        required_types = {"breakfast", "lunch", "dinner"}
        meal_types = [meal.type for meal in day.meals]
        if len(meal_types) != 3 or set(meal_types) != required_types:
            raise PlanValidationError(
                f"第{day.day_index + 1}天必须且只能包含早、中、晚餐各一次"
            )

        meal_poi_ids = [meal.poi_id for meal in day.meals]
        if len(meal_poi_ids) != len(set(meal_poi_ids)):
            raise PlanValidationError(
                f"第{day.day_index + 1}天的三餐不能使用同一家餐厅"
            )

        for meal in day.meals:
            if meal.poi_id not in selected_restaurant_id_set:
                raise PlanValidationError(
                    f"第{day.day_index + 1}天使用了餐厅Agent未选中的POI ID："
                    f"{meal.poi_id}"
                )
            source = candidate_restaurant_by_id[meal.poi_id]
            meal.name = source.name
            meal.address = source.address
            meal.location = source.location.model_copy(deep=True)
            meal.description = restaurant_reason_by_id[meal.poi_id]

    @staticmethod
    def _route_type_for_transportation(transportation: str) -> str:
        if "自驾" in transportation or "驾车" in transportation:
            return "driving"
        if "步行" in transportation:
            return "walking"
        return "transit"

    def _populate_routes_and_validate_feasibility(
        self,
        day,
        city: str,
        requested_transportation: str,
        amap_service,
        route_cache: dict | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> List[str]:
        """写入真实路线；路线完整时用总耗时校验单日可行性。"""
        if day.hotel is None:
            raise PlanValidationError(f"第{day.day_index + 1}天缺少酒店")

        route_type = self._route_type_for_transportation(
            requested_transportation
        )
        stops = [day.hotel, *day.attractions, day.hotel]
        day.travel_legs = []
        warnings: List[str] = []
        if route_cache is None:
            route_cache = {}

        expected_leg_count = len(stops) - 1
        for leg_index, (origin, destination) in enumerate(
            zip(stops, stops[1:]),
            start=1,
        ):
            try:
                cache_key = (
                    origin.address, destination.address, city, route_type
                )
                route = route_cache.get(cache_key)
                if route is None:
                    route = amap_service.plan_route(
                        origin_address=origin.address,
                        destination_address=destination.address,
                        origin_city=city,
                        destination_city=city,
                        route_type=route_type,
                    )
                    route_cache[cache_key] = route
                day.travel_legs.append(
                    TravelLeg(
                        origin_poi_id=origin.poi_id,
                        origin_name=origin.name,
                        destination_poi_id=destination.poi_id,
                        destination_name=destination.name,
                        distance=route.distance,
                        duration=route.duration,
                        route_type=route.route_type,
                        description=route.description,
                    )
                )
                self._emit_progress(
                    progress_callback,
                    "validating_routes",
                    8,
                    10,
                    f"第{day.day_index + 1}天路线已完成"
                    f"{leg_index}/{expected_leg_count}段",
                )
            except Exception as error:
                log(
                    f"⚠️ 第{day.day_index + 1}天路线查询失败: "
                    f"{origin.name} -> {destination.name}: {error}"
                )

        if len(day.travel_legs) != expected_leg_count:
            warnings.append(
                f"第{day.day_index + 1}天仅获取到"
                f"{len(day.travel_legs)}/{expected_leg_count}段路线，"
                "无法完整校验时间可行性"
            )
            return warnings

        settings = get_settings()
        visit_minutes = sum(
            attraction.visit_duration for attraction in day.attractions
        )
        route_minutes = sum(
            ceil(leg.duration / 60) for leg in day.travel_legs
        )
        required_minutes = (
            visit_minutes
            + route_minutes
            + settings.daily_meal_buffer_minutes
        )
        if required_minutes > settings.daily_available_minutes:
            raise PlanFeasibilityError(
                day_index=day.day_index,
                visit_minutes=visit_minutes,
                route_minutes=route_minutes,
                meal_minutes=settings.daily_meal_buffer_minutes,
                available_minutes=settings.daily_available_minutes,
                attractions=[
                    {
                        "poi_id": attraction.poi_id,
                        "name": attraction.name,
                        "visit_minutes": attraction.visit_duration,
                    }
                    for attraction in day.attractions
                ],
                routes=[
                    {
                        "from": leg.origin_name,
                        "to": leg.destination_name,
                        "minutes": ceil(leg.duration / 60),
                    }
                    for leg in day.travel_legs
                ],
            )
        return warnings

    @staticmethod
    def _emit_progress(
        callback: ProgressCallback | None,
        stage: str,
        current: int,
        total: int,
        message: str,
    ) -> None:
        if callback is not None:
            callback(stage, current, total, message)

    @staticmethod
    def _normalize_and_validate_budget(trip_plan: TripPlan) -> None:
        """以行程明细为唯一来源重算预算，避免模型汇总算术错误。"""
        if trip_plan.budget is None:
            raise PlanValidationError("行程缺少预算信息")

        attractions = sum(
            attraction.ticket_price or 0
            for day in trip_plan.days
            for attraction in day.attractions
        )
        hotels = sum(
            day.hotel.estimated_cost
            for day in trip_plan.days
            if day.hotel is not None
        )
        meals = sum(
            meal.estimated_cost
            for day in trip_plan.days
            for meal in day.meals
        )
        transportation = trip_plan.budget.total_transportation
        trip_plan.budget.total_attractions = attractions
        trip_plan.budget.total_hotels = hotels
        trip_plan.budget.total_meals = meals
        trip_plan.budget.total = attractions + hotels + meals + transportation
    
    def _parse_response(self, response: str, request: TripRequest) -> TripPlan:
        """
        解析Agent响应
        
        Args:
            response: Agent响应文本
            request: 原始请求
            
        Returns:
            旅行计划
        """
        try:
            data = extract_json_value(response)

            if not isinstance(data,dict):
                raise AgentOutputError("规划Agent返回的不是JSON对象")

            return TripPlan.model_validate(data)


        
        except MCPResponseParseError as error:
            raise AgentOutputError(
                "规划 Agent 响应中没有合法 JSON"
            ) from error

        except ValidationError as error:
            raise AgentOutputError(
                "规划 Agent 返回的数据不符合 TripPlan 结构"
            ) from error


    def _validate_plan_against_request(
        self,
        trip_plan: TripPlan,
        request: TripRequest,
    ) -> None:
        """校验生成的行程是否与原始请求一致。"""

        if trip_plan.city != request.city:
            raise PlanValidationError("行程城市与请求城市不一致")

        if trip_plan.start_date != request.start_date:
            raise PlanValidationError("行程开始日期与请求不一致")

        if trip_plan.end_date != request.end_date:
            raise PlanValidationError("行程结束日期与请求不一致")

        if len(trip_plan.days) != request.travel_days:
            raise PlanValidationError(
                f"行程天数不正确：期望{request.travel_days}天，"
                f"实际{len(trip_plan.days)}天"
            )

        expected_start = date.fromisoformat(request.start_date)
        for expected_index, day_plan in enumerate(trip_plan.days):
            if day_plan.day_index != expected_index:
                raise PlanValidationError(
                    f"day_index不连续：第{expected_index + 1}项应为"
                    f"{expected_index}，实际为{day_plan.day_index}"
                )
            expected_date = (
                expected_start + timedelta(days=expected_index)
            ).isoformat()
            if day_plan.date != expected_date:
                raise PlanValidationError(
                    f"行程日期不连续：第{expected_index + 1}天应为"
                    f"{expected_date}，实际为{day_plan.date}"
                )


# 全局多智能体系统实例
def create_trip_planner() -> MultiAgentTripPlanner:
    """为每次请求创建独立的旅行规划器"""
    return MultiAgentTripPlanner()
