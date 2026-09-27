"""多智能体旅行规划系统"""

import json
from typing import Dict, Any, List
from hello_agents import SimpleAgent
from ..services.llm_service import get_llm
from ..models.schemas import (
    TripRequest,
    TripPlan,
    WeatherInfo,
    POIInfo,
    AttractionSelection,
    HotelSelection
)
from ..services.amap_service import get_amap_service
from ..services.mcp_response_parser import extract_json_value,MCPResponseParseError
from pydantic import ValidationError

from ..exceptions import (
    AgentOutputError,
    ExternalServiceError,
    PlanValidationError,
    TripPlanningError,
)
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
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
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
8. 提供实用的旅行建议
9. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(self):
        """初始化多智能体系统"""
        print("🔄 开始初始化多智能体旅行规划系统...")

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
    
    def plan_trip(self, request: TripRequest) -> TripPlan:
        """
        使用多智能体协作生成旅行计划

        Args:
            request: 旅行请求

        Returns:
            旅行计划
        """
        try:
            print(f"\n{'='*60}")
            print(f"🚀 开始多智能体协作规划旅行...")
            print(f"目的地: {request.city}")
            print(f"日期: {request.start_date} 至 {request.end_date}")
            print(f"天数: {request.travel_days}天")
            print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
            print(f"{'='*60}\n")


            # 获取高德服务，后续景点和天气共用
            amap_service = get_amap_service()

            # 步骤1: 通过Service获取真实景点，再由Agent进行筛选
            print("📍 步骤1: 获取并筛选景点...")
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

            print(f"获取到真实景点候选: {len(attraction_candidates)}个")


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
                candidates=attraction_candidates
            )

            try:
                attraction_response = self.attraction_agent.run(
                    attraction_query
                )

            except Exception as error:
                raise ExternalServiceError(
                    "景点筛选模型暂时不可用"
                ) from error

            print(f"景点筛选结果: {attraction_response[:200]}...\n")

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
            # 步骤2: 通过天气service查询天气信息
            print("🌤️  步骤2: 查询天气...")

            # 使用高德服务直接查询天气
            weather_info_list : List[WeatherInfo] = []

            try:
                weather_info_list = amap_service.get_weather(request.city)
                print("Service天气数量：",len(weather_info_list))

            except Exception as e:
                print(f"⚠️ 天气查询失败，继续生成无天气行程: {str(e)}")
           
            weather_response = json.dumps(
                [weather.model_dump() for weather in weather_info_list],
                ensure_ascii=False,
                indent=2
            )
            print(f"天气查询结果: {weather_response[:200]}...\n")

            # 步骤3: 酒店推荐Agent搜索酒店
            print("🏨 步骤3: 搜索酒店...")
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

            print(f"酒店筛选结果: {hotel_response[:200]}...\n")
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


            # 步骤4: 行程规划Agent整合信息生成计划
            print("📋 步骤4: 生成行程计划...")
            planner_query = self._build_planner_query(request, trusted_attractions_json, weather_response, trusted_hotels_json)
            try:
                planner_response = self.planner_agent.run(
                    planner_query
                )
            except Exception as error:
                raise ExternalServiceError(
                    "行程规划模型暂时不可用"
                ) from error
            print(f"行程规划结果: {planner_response[:300]}...\n")

            # 解析最终计划
            trip_plan = self._parse_response(planner_response, request)
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
                    attraction.visit_duration = (selected.suggested_duration)
                    attraction.description = selected.reason
            trusted_weather_info = [
                weather
                for weather in weather_info_list
                if request.start_date <= weather.date <= request.end_date
            ]

            trip_plan.weather_info = trusted_weather_info


            print(f"{'='*60}")
            print(f"✅ 旅行计划生成完成!")
            print(f"{'='*60}\n")

            return trip_plan

        except Exception as e:
            print(f"❌ 生成旅行计划失败: {str(e)}")
            raise
    
    def _build_attraction_query(self, request: TripRequest,candidates:List[POIInfo]) -> str:
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

    def _build_planner_query(self, request: TripRequest, attractions: str, weather: str, hotels: str = "") -> str:
        """构建行程规划查询"""
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

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
3. 考虑景点之间的距离和交通方式
4. 返回完整的JSON格式数据
5. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query
    
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


# 全局多智能体系统实例
def create_trip_planner() -> MultiAgentTripPlanner:
    """为每次请求创建独立的旅行规划器"""
    return MultiAgentTripPlanner()
