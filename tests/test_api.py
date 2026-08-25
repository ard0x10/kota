"""Reading the API's answer, including the shapes it sends on other plans.

Nothing here goes near the network: `usage()` is handed a payload directly
through the one seam that exists for it.
"""

import unittest
from unittest import mock

from kota import api

# What the endpoint actually returns, trimmed. The nulls are real: which
# windows are filled depends on the plan.
FULL = {
    "five_hour": {"utilization": 45.2, "resets_at": "2026-08-25T21:59:59.79Z"},
    "seven_day": {"utilization": 76, "resets_at": "2026-08-27T16:59:59.79Z"},
    "seven_day_opus": None,
    "tangelo": None,
    "extra_usage": {"is_enabled": True, "used_credits": 3960,
                    "monthly_limit": 4500, "decimal_places": 2,
                    "utilization": 88},
}


def answering(payload):
    return mock.patch.object(api, "_request", return_value=payload)


class Usage(unittest.TestCase):
    def test_a_full_answer(self):
        with answering(FULL):
            usage = api.usage("token")
        self.assertAlmostEqual(usage.session.percent, 45.2)
        self.assertEqual(usage.week.resets_at, "2026-08-27T16:59:59.79Z")
        self.assertAlmostEqual(usage.extra.used, 39.60)
        self.assertAlmostEqual(usage.extra.limit, 45.0)

    def test_extra_usage_switched_off_is_no_extra_at_all(self):
        payload = dict(FULL, extra_usage={"is_enabled": False})
        with answering(payload):
            self.assertIsNone(api.usage("token").extra)

    def test_extra_usage_missing_entirely(self):
        payload = dict(FULL)
        del payload["extra_usage"]
        with answering(payload):
            self.assertIsNone(api.usage("token").extra)

    def test_a_window_that_is_null(self):
        payload = dict(FULL, seven_day=None)
        with answering(payload):
            usage = api.usage("token")
        self.assertEqual(usage.week.percent, 0.0)
        self.assertEqual(usage.week.resets_at, "")

    def test_an_empty_answer_does_not_raise(self):
        with answering({}):
            usage = api.usage("token")
        self.assertEqual(usage.session.percent, 0.0)
        self.assertIsNone(usage.extra)

    def test_a_number_that_arrived_as_a_string(self):
        payload = dict(FULL, five_hour={"utilization": "45.2", "resets_at": ""})
        with answering(payload):
            self.assertAlmostEqual(api.usage("token").session.percent, 45.2)

    def test_zero_decimal_places_does_not_divide_by_zero(self):
        payload = dict(FULL, extra_usage={"is_enabled": True, "used_credits": 40,
                                          "monthly_limit": 45,
                                          "decimal_places": 0, "utilization": 88})
        with answering(payload):
            self.assertAlmostEqual(api.usage("token").extra.used, 40.0)


class Identity(unittest.TestCase):
    def test_max_and_pro(self):
        with answering({"account": {"uuid": "u", "email": "a@b.c",
                                    "has_claude_max": True}}):
            self.assertEqual(api.identity("t"), ("u", "a@b.c", "max"))
        with answering({"account": {"uuid": "u", "email": "a@b.c"}}):
            self.assertEqual(api.identity("t"), ("u", "a@b.c", "pro"))

    def test_an_answer_with_no_account_in_it(self):
        with answering({}):
            self.assertEqual(api.identity("t"), ("", "", "pro"))


class Refresh(unittest.TestCase):
    def test_a_rotated_refresh_token_is_returned(self):
        with answering({"access_token": "new", "refresh_token": "rotated",
                        "expires_in": 28800}):
            self.assertEqual(api.refresh("old"), ("new", "rotated", 28800))

    def test_no_new_refresh_token_means_the_old_one_still_stands(self):
        with answering({"access_token": "new", "expires_in": 28800}):
            self.assertEqual(api.refresh("old"), ("new", "old", 28800))

    def test_an_answer_with_no_token_is_an_error(self):
        with answering({"expires_in": 28800}), self.assertRaises(api.ApiError):
            api.refresh("old")


class Errors(unittest.TestCase):
    def test_what_a_status_means(self):
        self.assertTrue(api.ApiError("x", 401).is_auth)
        self.assertTrue(api.ApiError("x", 429).is_rate_limit)
        self.assertFalse(api.ApiError("x").is_auth)


if __name__ == "__main__":
    unittest.main()
