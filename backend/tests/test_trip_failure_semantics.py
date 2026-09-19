import unittest

from app.agents.trip_planner_agent import MultiAgentTripPlanner
from app.exceptions import AgentOutputError
from app.models.schemas import TripRequest


class TestTripFailureSemantics(unittest.TestCase):

    def setUp(self):
        self.planner = MultiAgentTripPlanner.__new__(
            MultiAgentTripPlanner
        )

        self.request = TripRequest(
            city="北京",
            start_date="2026-10-01",
            end_date="2026-10-03",
            travel_days=3,
            transportation="公共交通",
            accommodation="经济型酒店",
            preferences=["历史文化"],
            free_text_input="",
        )

    def test_reject_non_json_planner_response(self):
        with self.assertRaises(AgentOutputError):
            self.planner._parse_response(
                "这不是合法JSON",
                self.request,
            )

    def test_reject_invalid_trip_plan_structure(self):
        response = """
        {
            "city": "北京",
            "days": []
        }
        """

        with self.assertRaises(AgentOutputError):
            self.planner._parse_response(
                response,
                self.request,
            )


if __name__ == "__main__":
    unittest.main()