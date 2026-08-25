"""The part most likely to be wrong: turning numbers into words."""

import datetime
import unittest

from kota import formatting


def when(**kwargs):
    """An ISO timestamp that far from now."""
    moment = datetime.datetime.now(datetime.UTC) + datetime.timedelta(**kwargs)
    return moment.isoformat()


class Countdown(unittest.TestCase):
    def test_nothing_to_say(self):
        self.assertEqual(formatting.countdown(""), "")
        self.assertEqual(formatting.countdown(None), "")
        self.assertEqual(formatting.countdown("not a date"), "")

    def test_already_gone(self):
        self.assertEqual(formatting.countdown(when(minutes=-5)), "now")

    def test_rounds_down_and_not_to_nearest(self):
        """2h48m is two hours and forty-eight minutes, not three.

        Round the hours to the nearest instead of truncating and it reads
        "3h 48m", which is wrong and contradicts its own minutes.
        """
        self.assertEqual(formatting.countdown(when(hours=2, minutes=48, seconds=5)),
                         "2h 48m")
        self.assertEqual(formatting.countdown(when(hours=2, minutes=30, seconds=5)),
                         "2h 30m")

    def test_days_take_over_from_hours(self):
        self.assertEqual(formatting.countdown(when(days=2, hours=3, seconds=5)),
                         "2d 3h")

    def test_under_an_hour_is_minutes_alone(self):
        self.assertEqual(formatting.countdown(when(minutes=42, seconds=5)), "42m")

    def test_units_can_be_said_in_another_language(self):
        self.assertEqual(
            formatting.countdown(when(hours=2, minutes=29, seconds=5),
                                 units=("g", "s", "dk")),
            "2s 29dk")

    def test_a_z_suffix_is_the_same_moment(self):
        moment = datetime.datetime.now(datetime.UTC) + \
            datetime.timedelta(hours=1, minutes=30, seconds=5)
        zulu = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertEqual(formatting.countdown(zulu), "1h 30m")

    def test_a_naive_timestamp_is_read_as_utc(self):
        moment = datetime.datetime.now(datetime.UTC) + \
            datetime.timedelta(hours=3, seconds=5)
        naive = moment.replace(tzinfo=None).isoformat()
        self.assertEqual(formatting.countdown(naive), "3h 0m")


class Bands(unittest.TestCase):
    def test_the_three_bands(self):
        self.assertEqual(formatting.level(0), formatting.OK)
        self.assertEqual(formatting.level(49.9), formatting.OK)
        self.assertEqual(formatting.level(50), formatting.WARN)
        self.assertEqual(formatting.level(79.9), formatting.WARN)
        self.assertEqual(formatting.level(80), formatting.ALARM)
        self.assertEqual(formatting.level(100), formatting.ALARM)


class Bar(unittest.TestCase):
    def test_ends(self):
        self.assertEqual(formatting.bar(0), ".......")
        self.assertEqual(formatting.bar(100), "#######")

    def test_out_of_range_is_clamped(self):
        self.assertEqual(formatting.bar(140), "#######")
        self.assertEqual(formatting.bar(-5), ".......")

    def test_width_is_honoured(self):
        self.assertEqual(formatting.bar(40, width=5), "##...")


class Money(unittest.TestCase):
    def test_cents_only_where_there_are_any(self):
        self.assertEqual(formatting.money(45.0), "$45")
        self.assertEqual(formatting.money(39.6), "$39.60")

    def test_a_pair(self):
        self.assertEqual(formatting.money_pair(39.6, 45.0), "$39.60 / $45")


class Cut(unittest.TestCase):
    def test_short_enough_is_left_alone(self):
        self.assertEqual(formatting.cut("work", 13), "work")

    def test_too_long_is_marked(self):
        self.assertEqual(formatting.cut("a.long.account.name", 13), "a.long.accou~")


class Ago(unittest.TestCase):
    def test_the_steps(self):
        import time

        now = time.time()
        self.assertEqual(formatting.ago(now - 5, now), "just now")
        self.assertEqual(formatting.ago(now - 300, now), "5m ago")
        self.assertEqual(formatting.ago(now - 7200, now), "2h ago")
        self.assertEqual(formatting.ago(now - 172800, now), "2d ago")
        self.assertEqual(formatting.ago(0, now), "")


if __name__ == "__main__":
    unittest.main()
