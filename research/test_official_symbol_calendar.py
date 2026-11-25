import unittest
from datetime import date, datetime, timezone

from .official_symbol_calendar import EPOCH_DAY, attach_calendars, build_clock_grid


class OfficialCalendarChecks(unittest.TestCase):
    def setUp(self):
        self.sunday = int(datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp()) * 1000
        self.monday = self.sunday + 86_400_000
        self.week = dict(scheduleTimeZone="UTC", schedule=[dict(startSecond=15, endSecond=315)])
        self.holiday = dict(holidayDate=(date(2025, 12, 25) - EPOCH_DAY).days, isRecurring=False,
                            scheduleTimeZone="Europe/Bucharest", startSecond=0, endSecond=0)

    def test_sunday_start_inclusive_end_exclusive(self):
        grid = build_clock_grid(self.week, self.sunday, self.monday)
        self.assertEqual(grid["openClocks"], [self.sunday + 15000])

    def test_invalid_out_of_window_holiday_keeps_official_sessions(self):
        grid = build_clock_grid(self.week | {"holiday": [self.holiday]}, self.sunday, self.monday)
        self.assertEqual(grid["openClocks"], [self.sunday + 15000])
        self.assertEqual(grid["issues"][0]["reason"], "HOLIDAY_OUTSIDE_WINDOW")
        self.assertFalse(grid["historicalCalendarContinuityCertified"])

    def test_ambiguous_recurring_holiday_marks_only_affected_local_day(self):
        calendar = self.week | {"schedule": [dict(startSecond=0, endSecond=604800)],
                                "holiday": [self.holiday | {"isRecurring": True,
                                 "holidayDate": (date(2025, 11, 1)-EPOCH_DAY).days}]}
        grid = build_clock_grid(calendar, self.sunday, self.monday + 86_400_000)
        self.assertEqual(grid["status"], "PARTIALLY_SUPPORTED_SNAPSHOT")
        self.assertEqual(len(grid["ambiguousClocks"]), 264)
        self.assertIn(self.monday + 15000, grid["openClocks"])

    def test_official_holiday_uses_its_own_local_clock(self):
        calendar = self.week | {"holiday": [self.holiday | {"holidayDate": (date(2026, 11, 1)-EPOCH_DAY).days,
                                                           "startSecond": 7200, "endSecond": 7500}]}
        grid = build_clock_grid(calendar, self.sunday, self.monday)
        self.assertEqual(grid["openClocks"], [])
        self.assertEqual(grid["ambiguousClocks"], [])

    def test_unknown_is_separate_from_an_officially_closed_clock(self):
        self.assertEqual(build_clock_grid(None,self.sunday,self.monday)["status"], "CALENDAR_NOT_COLLECTED")
        self.assertEqual(build_clock_grid({},self.sunday,self.monday)["status"], "CALENDAR_ABSENT_IN_OFFICIAL_RESPONSE")
        self.assertEqual(build_clock_grid(self.week | {"scheduleTimeZone":"Imaginary/Zone"},
                                          self.sunday,self.monday)["status"], "SESSION_TIME_ZONE_UNSUPPORTED")

    def test_calendar_is_bound_to_same_contract_snapshot(self):
        source = {"Start": self.sunday, "End":self.monday, "Markets": [{"TermsAcquiredAt": self.monday, "Market":
            {"Name":"SYMBOL", "DatedDevelopment":{"Digest":"expected"}}}]}
        with self.assertRaisesRegex(ValueError, "CALENDAR_CONTRACT_BINDING"):
            attach_calendars(source, {"SYMBOL":{"contractSha256":"other", "contractObservedAt":self.monday}})
