"""高德地图MCP服务封装"""

from dbm import error
from typing import List, Dict, Any, Optional
from hello_agents.tools import MCPTool
from ..config import get_settings
from ..models.schemas import Location, POIInfo, WeatherInfo
from .mcp_response_parser import extract_json_value
#将MCP返回的JSON字符串转换成Python对象(dict)
import json
# 全局MCP工具实例
_amap_mcp_tool = None

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
    """
    获取高德地图MCP工具实例(单例模式)
    
    Returns:
        MCPTool实例
    """
    global _amap_mcp_tool
    
    if _amap_mcp_tool is None:
        settings = get_settings()
        
        if not settings.amap_api_key:
            raise ValueError("高德地图API Key未配置,请在.env文件中设置AMAP_API_KEY")
        
        # 创建MCP工具
        _amap_mcp_tool = MCPTool(
            name="amap",
            description="高德地图服务,支持POI搜索、路线规划、天气查询等功能",
            server_command=["uvx", "amap-mcp-server"],
            env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
            auto_expand=True  # 自动展开为独立工具
        )
        
        print(f"✅ 高德地图MCP工具初始化成功")
        print(f"   工具数量: {len(_amap_mcp_tool._available_tools)}")
        
        # 打印可用工具列表
        if _amap_mcp_tool._available_tools:
            print("   可用工具:")
            for tool in _amap_mcp_tool._available_tools[:5]:  # 只打印前5个
                print(f"     - {tool.get('name', 'unknown')}")
            if len(_amap_mcp_tool._available_tools) > 5:
                print(f"     ... 还有 {len(_amap_mcp_tool._available_tools) - 5} 个工具")
    
    return _amap_mcp_tool


class AmapService:
    """高德地图服务封装类"""
    
    def __init__(self):
        """初始化服务"""
        self.mcp_tool = get_amap_mcp_tool()
    
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
    ) -> Dict[str, Any]:
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
            # 根据路线类型选择工具
            tool_map = {
                "walking": "maps_direction_walking_by_address",
                "driving": "maps_direction_driving_by_address",
                "transit": "maps_direction_transit_integrated_by_address"
            }
            
            tool_name = tool_map.get(route_type, "maps_direction_walking_by_address")
            
            # 构建参数
            arguments = {
                "origin_address": origin_address,
                "destination_address": destination_address
            }
            
            # 公共交通需要城市参数
            if route_type == "transit":
                if origin_city:
                    arguments["origin_city"] = origin_city
                if destination_city:
                    arguments["destination_city"] = destination_city
            else:
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
            return {}
            
        except Exception as e:
            print(f"❌ 路线规划失败: {str(e)}")
            return {}
    
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


def get_amap_service() -> AmapService:
    """获取高德地图服务实例(单例模式)"""
    global _amap_service
    
    if _amap_service is None:
        _amap_service = AmapService()
    
    return _amap_service

