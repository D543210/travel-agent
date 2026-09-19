import unittest

from app.services.mcp_response_parser import extract_json_value,MCPResponseParseError

class TestMCPResponseParser(unittest.TestCase):
    def test_extract_object_with_perfix(self):
        raw = """

        工具'maps_text_search'执行结果：
        {
            "pois":[
                {
                    "id":"B001",
                    "name":"故宫博物院"
                }
            ]       
        }
        """

        result = extract_json_value(raw)

        self.assertEqual(result["pois"][0]["id"], "B001")
        self.assertEqual(result["pois"][0]["name"], "故宫博物院")

    def test_extract_array_with_prefix(self):
        raw = """

        工具执行结果：
        [
            {"id":"B001"},
            {"id":"B002"}
        ]
        """

        result = extract_json_value(raw)

        self.assertEqual(len(result),2)
        self.assertEqual(result[1]["id"], "B002")


    def test_accept_existing_dict(self):
        raw = {"city": "北京"}

        result = extract_json_value(raw)

        self.assertEqual(result, {"city": "北京"})

    def test_accept_existing_list(self):
        raw = [{"id": "B001"}]

        result = extract_json_value(raw)

        self.assertEqual(result, [{"id": "B001"}])

    def test_reject_empty_string(self):
        with self.assertRaises(MCPResponseParseError):
            extract_json_value("")

    def test_reject_error_message(self):
        raw = "异步操作失败: MCP服务器无法连接"

        with self.assertRaises(MCPResponseParseError):
            extract_json_value(raw)

    def test_reject_invalid_type(self):
        with self.assertRaises(MCPResponseParseError):
            extract_json_value(123)


if __name__ == "__main__":
    unittest.main()