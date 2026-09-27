"""高德地图MCP服务封装"""

from dbm import error
from typing import List, Dict, Any, Optional
from hello_agents.tools import MCPTool
from ..config import get_settings
from ..models.schemas import Location, POIInfo, WeatherInfo,RouteInfo
from .mcp_response_parser import extract_json_value
from threading import Lock

import requests
#将MCP返回的JSON字符串转换成Python对象(dict)
import json
# 全局MCP工具实例
_amap_mcp_tool = None
_amap_mcp_tool_lock = Lock()

def parse_location(value:Any)->Location:
    """
    将MCP返回的坐标数据解析为Location对象

    Args:
        value: MCP返回的坐标数据

    Returns:
        Location对象
    """
    if not isinstance(value, str):
        raise ValueError("location必须是字符串")

    parts = value.split(",")

    if len(parts) != 2:
        raise ValueError(f"location格式错误: {value}")

    try:
        longitude = float(parts[0].strip())
        latitude = float(parts[1].strip())
    except ValueError as error:
        raise ValueError(f"location包含非数字坐标: {value}") from error

    if not -180<=longitude<=180:
        raise ValueError(f"经度超出范围: {longitude}")
    
    if not -90<=latitude<=90:
        raise ValueError(f"纬度超出范围: {latitude}")

    return Location(longitude=longitude, latitude=latitude)

def parse_route_result(
        raw_result: str,
        route_type: str,
) -> RouteInfo:
    data = extract_json_value(raw_result)

    if not isinstance(data, dict):
        raise ValueError("路线响应不是JSON对象")
    
    route = data.get("route")

    if not isinstance(route, dict):
        raise ValueError("路线响应缺少route对象")
    
    paths = route.get("paths")

    if not isinstance(paths, list) or not paths:
        raise ValueError("路线响应没有可用路径")

    first_path = paths[0]

    if not isinstance(first_path, dict):
        raise ValueError("路线数据格式错误")

    distance_value = first_path.get("distance")
    duration_value = first_path.get("duration")

    if distance_value is None:
        raise ValueError("路线响应缺少distance")

    if duration_value is None:
        raise ValueError("路线响应缺少duration")

    try:
        distance = float(distance_value)
        duration = int(duration_value)

    except (TypeError, ValueError) as error:
        raise ValueError(
            "路线距离或耗时不是合法数字"
        ) from error

    raw_steps = first_path.get("steps", [])

    if not isinstance(raw_steps, list):
        raise ValueError("路线steps不是数组")

    instructions = []

    for step in raw_steps:
        if not isinstance(step, dict):
            continue

        instruction = step.get("instruction")

        if isinstance(instruction, str) and instruction.strip():
            instructions.append(instruction.strip())

    description = "；".join(instructions)

    return RouteInfo(
        distance=distance,
        duration=duration,
        route_type=route_type,
        description=description,
    )


def parse_transit_route_result(
    data: Any,
) -> RouteInfo:
    if not isinstance(data, dict):
        raise ValueError("公交路线响应不是JSON对象")

    if data.get("status") != "1":
        info = data.get("info", "未知错误")
        infocode = data.get("infocode", "")
        raise ValueError(
            f"公交路线查询失败: {info} ({infocode})"
        )

    route = data.get("route")

    if not isinstance(route, dict):
        raise ValueError("公交路线响应缺少route对象")

    transits = route.get("transits")

    if not isinstance(transits, list) or not transits:
        raise ValueError("公交路线响应没有可用方案")

    first_transit = transits[0]

    if not isinstance(first_transit, dict):
        raise ValueError("公交方案格式错误")

    distance_value = route.get("distance")
    duration_value = first_transit.get("duration")

    if distance_value is None:
        raise ValueError("公交路线缺少总距离")

    if duration_value is None:
        raise ValueError("公交路线缺少总耗时")

    try:
        distance = float(distance_value)
        duration = int(duration_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "公交路线距离或耗时不是合法数字"
        ) from error

    description_parts = []

    segments = first_transit.get("segments", [])

    if isinstance(segments, list):
        for segment in segments:
            if not isinstance(segment, dict):
                continue

            walking = segment.get("walking")

            if isinstance(walking, dict):
                walking_distance = walking.get("distance")

                try:
                    walking_distance_number = int(
                        walking_distance or 0
                    )
                except (TypeError, ValueError):
                    walking_distance_number = 0

                if walking_distance_number > 0:
                    description_parts.append(
                        f"步行{walking_distance_number}米"
                    )

            bus = segment.get("bus")

            if not isinstance(bus, dict):
                continue

            buslines = bus.get("buslines")

            if not isinstance(buslines, list) or not buslines:
                continue

            first_busline = buslines[0]

            if not isinstance(first_busline, dict):
                continue

            line_name = first_busline.get("name")

            if isinstance(line_name, str) and line_name.strip():
                description_parts.append(
                    f"乘坐{line_name.strip()}"
                )

    description = "；".join(description_parts)

    if not description:
        description = "公共交通路线"

    return RouteInfo(
        distance=distance,
        duration=duration,
        route_type="transit",
        description=description,
    )

def parse_poi_detail(data:Dict[str,Any])->POIInfo:
    """
    将MCP返回的POI详情数据解析为POIInfo对象
    
    Args:
        data: MCP返回的POI详情数据
    
    Returns:
        POIInfo对象
    """
    if not isinstance(data, dict):
        raise ValueError("POI详情数据必须是字典")

    poi_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()

    if not poi_id:
        raise ValueError("POI详情数据缺少id字段")

    if not name:
        raise ValueError("POI详情数据缺少name字段")

    return POIInfo(
        id=poi_id,
        name=name,
        type=str(data.get("type", "")).strip(),
        address=str(data.get("address", "")).strip(),
        location=parse_location(data.get("location")),
        tel=data.get("tel")
    )

def get_amap_mcp_tool() -> MCPTool:
    """线程安全地获取共享高德MCP工具。"""
    global _amap_mcp_tool

    if _amap_mcp_tool is None:
        with _amap_mcp_tool_lock:
            if _amap_mcp_tool is None:
                settings = get_settings()

                if not settings.amap_api_key:
                    raise ValueError(
                        "高德地图API Key未配置,"
                        "请在.env文件中设置AMAP_API_KEY"
                    )

                _amap_mcp_tool = MCPTool(
                    name="amap",
                    description="高德地图服务",
                    server_command=["uvx", "amap-mcp-server"],
                    env={
                        "AMAP_MAPS_API_KEY":
                            settings.amap_api_key
                    },
                    auto_expand=True,
                )
                print("✅ 高德地图MCP工具初始化成功")
                print(
                    "   工具数量: "
                    f"{len(_amap_mcp_tool._available_tools)}"
                )

    return _amap_mcp_tool

class AmapService:
    """高德地图服务封装类"""
    
    def __init__(self):
        """初始化服务"""
        self.mcp_tool = get_amap_mcp_tool()


    def _geocode_direct(
        self,
        address: str,
        city: Optional[str] = None,
    ) -> str:
        settings = get_settings()

        params = {
            "key": settings.amap_api_key,
            "address": address,
        }

        if city:
            params["city"] = city

        response = requests.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params=params,
            timeout=(5, 20),
        )

        response.raise_for_status()

        data = response.json()

        if data.get("status") != "1":
            info = data.get("info", "未知错误")
            infocode = data.get("infocode", "")
            raise ValueError(
                f"地址解析失败: {info} ({infocode})"
            )

        geocodes = data.get("geocodes")

        if not isinstance(geocodes, list) or not geocodes:
            raise ValueError(
                f"没有找到地址坐标: {address}"
            )

        first_geocode = geocodes[0]

        if not isinstance(first_geocode, dict):
            raise ValueError("地理编码结果格式错误")

        location = first_geocode.get("location")

        if not isinstance(location, str) or not location.strip():
            raise ValueError("地理编码结果缺少location")

        # 复用已有函数校验坐标格式与范围
        parse_location(location)

        return location.strip()

    def _plan_transit_route_direct(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str],
        destination_city: Optional[str],
    ) -> RouteInfo:
        if not origin_city:
            raise ValueError("公交路线缺少起点城市")

        if not destination_city:
            raise ValueError("公交路线缺少终点城市")

        origin = self._geocode_direct(
            origin_address,
            origin_city,
        )

        destination = self._geocode_direct(
            destination_address,
            destination_city,
        )

        settings = get_settings()

        response = requests.get(
            "https://restapi.amap.com/v3/direction/transit/integrated",
            params={
                "key": settings.amap_api_key,
                "origin": origin,
                "destination": destination,
                "city": origin_city,
                "cityd": destination_city,
                "extensions": "all",
            },
            timeout=(5, 20),
        )

        response.raise_for_status()

        data = response.json()

        return parse_transit_route_result(data)

    def search_poi(self, keywords: str, city: str, citylimit: bool = True) -> List[POIInfo]:
        """
        搜索POI
        
        Args:
            keywords: 搜索关键词
            city: 城市
            citylimit: 是否限制在城市范围内
            
        Returns:
            POI信息列表
        """
        try:
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_text_search",
                "arguments": {
                    "keywords": keywords,
                    "city": city,
                    "citylimit": str(citylimit).lower()
                }
            })
            
            data = extract_json_value(result)

            if not isinstance(data, dict):
                raise ValueError("POI搜索结果不是JSON响应对象")

            poi_items = data.get("pois", [])

            if not isinstance(poi_items, list):
                raise ValueError("POI搜索结果中的pois不是列表")

            poi_info_list : List[POIInfo] = []

            # 暂时最多解析前10条，避免产生过多详情请求
            for item in poi_items[:10]:
                if not isinstance(item, dict):
                    continue

                poi_id = str(item.get("id", "")).strip()

                if not poi_id:
                    continue

                try:
                    poi_info = self.get_poi_info(poi_id)
                    poi_info_list.append(poi_info)
                except Exception as error:
                    # 单个POI失败，不影响其他POI
                    print(f"⚠️ 跳过POI {poi_id}: {error}")

            if not poi_info_list:
                raise ValueError("没有获得有效的POI详情")

            return poi_info_list

        except Exception as error:
            print(f"❌ POI搜索失败: {error}")
            raise
           
    
    def get_weather(self, city: str) -> List[WeatherInfo]:
        """
        查询天气
        
        Args:
            city: 城市名称
            
        Returns:
            天气信息列表
        """
        try:
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_weather",
                "arguments": {
                    "city": city
                }
            })
            
            print(f"天气查询结果: {result[:200]}...")

            
            if "{" in result and "}" in result:
                #直接查找JSON对象
                json_start = result.find("{")
                json_end = result.rfind("}")+1
                json_str = result[json_start:json_end]

            else:
                raise  ValueError("响应中未找到JSON数据")

            data = json.loads(json_str)

            weather_info_list = []
            forecasts_list = data.get("forecasts",[])

            if not isinstance(forecasts_list, list):
                raise ValueError("forecasts不是列表")

            if not forecasts_list:
                raise ValueError("天气预报列表为空")

            for forecast in forecasts_list:
                if not isinstance(forecast,dict):
                    raise ValueError("天气预报不是字典")
                #读取first_forecast中的字段并映射为WeatherInfo对象
                #WeatherInfo初始化会触发Pydantic的验证器,会自动调用parse_temperature方法解析温度    
                weather_info = WeatherInfo(
                    date=forecast["date"],
                    day_weather=forecast.get("dayweather", ""),
                    night_weather=forecast.get("nightweather", ""),
                    day_temp=forecast.get("daytemp", 0),
                    night_temp=forecast.get("nighttemp", 0),
                    wind_direction=forecast.get("daywind", ""),
                    wind_power=forecast.get("daypower", "")
                )
                weather_info_list.append(weather_info)
          
            return weather_info_list
            
        except Exception as e:
            print(f"❌ 天气查询失败: {str(e)}")
            raise
    
    def plan_route(
        self,
        origin_address: str,
        destination_address: str,
        origin_city: Optional[str] = None,
        destination_city: Optional[str] = None,
        route_type: str = "walking"
    ) -> RouteInfo:
        """
        规划路线
        
        Args:
            origin_address: 起点地址
            destination_address: 终点地址
            origin_city: 起点城市
            destination_city: 终点城市
            route_type: 路线类型 (walking/driving/transit)
            
        Returns:
            路线信息
        """
        try:
            # 公共交通需要城市参数
            if route_type == "transit":
                return self._plan_transit_route_direct(
                    origin_address=origin_address,
                    destination_address=destination_address,
                    origin_city=origin_city,
                    destination_city=destination_city,
                )
            # 根据路线类型选择工具
            tool_map = {
                "walking": "maps_direction_walking_by_address",
                "driving": "maps_direction_driving_by_address",
            }

            if route_type not in tool_map:
                raise ValueError(
                    f"不支持的路线类型: {route_type}"
                )
            
            tool_name = tool_map[route_type]
            
            # 构建参数
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address
            }


            # 其他路线类型也可以提供城市参数提高准确性
            if origin_city:
                arguments["origin_city"] = origin_city
            if destination_city:
                arguments["destination_city"] = destination_city
            
            # 调用MCP工具
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": tool_name,
                "arguments": arguments
            })
            
            print(f"路线规划结果: {result[:200]}...")
            
            # TODO: 解析实际的路线数据
            return parse_route_result(
                raw_result=result,
                route_type=route_type,
            )
            
        except Exception as e:
            print(f"❌ 路线规划失败: {str(e)}")
            raise
    
    def geocode(self, address: str, city: Optional[str] = None) -> Optional[Location]:
        """
        地理编码(地址转坐标)

        Args:
            address: 地址
            city: 城市

        Returns:
            经纬度坐标
        """
        try:
            arguments = {"address": address}
            if city:
                arguments["city"] = city

            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_geo",
                "arguments": arguments
            })

            print(f"地理编码结果: {result[:200]}...")

            # TODO: 解析实际的坐标数据
            return None

        except Exception as e:
            print(f"❌ 地理编码失败: {str(e)}")
            return None

    def get_poi_info(self, poi_id: str) -> POIInfo:
        """
        获取POI信息

        Args:
            poi_id: POI ID

        Returns:
            POI信息
        """
        if not poi_id:
            raise ValueError("poi_id不能为空")

        try:
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_search_detail",
                "arguments": {
                    "id": poi_id
                }
            })

            # 解析结果并提取POI详情
            data = extract_json_value(result)

            if not isinstance(data, dict):
                raise ValueError("POI详情数据不是JSON响应对象")

            return parse_poi_detail(data)

        except Exception as error:
            print(f"❌ 获取POI信息失败: {error}")
            raise

    def get_poi_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        获取POI详情

        Args:
            poi_id: POI ID

        Returns:
            POI详情信息
        """
        try:
            result = self.mcp_tool.run({
                "action": "call_tool",
                "tool_name": "maps_search_detail",
                "arguments": {
                    "id": poi_id
                }
            })

            print(f"POI详情结果: {result[:200]}...")

            # 解析结果并提取图片
            import json
            import re

            # 尝试从结果中提取JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return data

            return {"raw": result}

        except Exception as e:
            print(f"❌ 获取POI详情失败: {str(e)}")
            return {}


# 创建全局服务实例
_amap_service = None
_amap_service_lock = Lock()

def get_amap_service() -> AmapService:
    """线程安全地获取共享高德服务"""
    global _amap_service

    if _amap_service is None:
        with _amap_service_lock:
            if _amap_service is None:
                _amap_service = AmapService()

    return _amap_service
