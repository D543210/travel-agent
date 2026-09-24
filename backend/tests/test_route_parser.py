from app.services.amap_service import (
    parse_route_result,
    parse_transit_route_result,
)

import pytest
WALKING_RESPONSE = """
工具 'maps_direction_walking_by_address' 执行结果:
{
  "route": {
    "origin": "116.397005,39.919278",
    "destination": "116.396551,39.925875",
    "paths": [
      {
        "distance": "1279",
        "duration": "1023",
        "steps": [
          {
            "instruction": "向西北步行11米左转",
            "road": [],
            "distance": "11",
            "duration": "9"
          },
          {
            "instruction": "向西步行8米",
            "road": [],
            "distance": "8",
            "duration": "6"
          }
        ]
      }
    ]
  }
}
"""


def test_parse_walking_route():
    result = parse_route_result(
        WALKING_RESPONSE,
        "walking",
    )

    assert result.distance == 1279
    assert result.duration == 1023
    assert result.route_type == "walking"
    assert "向西北步行11米左转" in result.description
    assert "向西步行8米" in result.description

def test_parse_route_rejects_empty_paths():
    raw_result = """
    {
      "route": {
        "paths": []
      }
    }
    """

    with pytest.raises(
        ValueError,
        match="没有可用路径",
    ):
        parse_route_result(
            raw_result,
            "walking",
        )

def test_parse_route_rejects_invalid_duration():
    raw_result = """
    {
      "route": {
        "paths": [
          {
            "distance": "1000",
            "duration": "未知",
            "steps": []
          }
        ]
      }
    }
    """

    with pytest.raises(
        ValueError,
        match="不是合法数字",
    ):
        parse_route_result(
            raw_result,
            "walking",
        )

TRANSIT_RESPONSE = {
    "status": "1",
    "info": "OK",
    "infocode": "10000",
    "route": {
        "origin": "116.397005,39.919278",
        "destination": "116.274533,39.998000",
        "distance": "22479",
        "transits": [
            {
                "duration": "4200",
                "walking_distance": "860",
                "segments": [
                    {
                        "walking": {
                            "distance": "300"
                        },
                        "bus": {
                            "buslines": [
                                {
                                    "name": "地铁1号线"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
}

def test_parse_transit_route():
    result = parse_transit_route_result(
        TRANSIT_RESPONSE
    )

    assert result.distance == 22479
    assert result.duration == 4200
    assert result.route_type == "transit"
    assert "步行300米" in result.description
    assert "地铁1号线" in result.description


def test_parse_transit_rejects_empty_routes():
    data = {
        "status": "1",
        "route": {
            "distance": "1000",
            "transits": [],
        },
    }

    with pytest.raises(
        ValueError,
        match="没有可用方案",
    ):
        parse_transit_route_result(data)