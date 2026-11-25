"""Interpret dated Spotware calendar snapshots without inferring historical continuity."""
import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_SECONDS = 86400
WEEK_SECONDS = 7 * DAY_SECONDS
EPOCH_DAY = date(1970, 1, 1)


def build_clock_grid(fields, start, end, step=300000, offset=15000):
    """Return open and ambiguous clocks on an explicit UTC decision grid."""
    if start < 0 or end <= start or not 0 <= offset < step:
        raise ValueError("INVALID_CALENDAR_GRID")

    def result(status, issues=(), opened=None, ambiguous=()):
        return dict(status=status, issues=list(issues), openClocks=opened,
                    ambiguousClocks=list(ambiguous), historicalCalendarContinuityCertified=False)

    if fields is None:
        return result("CALENDAR_NOT_COLLECTED")
    if not fields.get("schedule"):
        return result("CALENDAR_ABSENT_IN_OFFICIAL_RESPONSE")
    if not fields.get("scheduleTimeZone"):
        return result("SESSION_TIME_ZONE_ABSENT")
    try:
        zone = ZoneInfo(fields["scheduleTimeZone"])
    except (ValueError, ZoneInfoNotFoundError):
        return result("SESSION_TIME_ZONE_UNSUPPORTED")
    sessions = [(r.get("startSecond"), r.get("endSecond")) for r in fields["schedule"]]
    if any(type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= WEEK_SECONDS
           for lo, hi in sessions):
        return result("OFFICIAL_SESSION_INTERVAL_UNSUPPORTED")

    def utc(at):
        return datetime.fromtimestamp(at / 1000, timezone.utc)

    holidays = []
    issues = []
    for index, row in enumerate(fields.get("holiday", [])):
        try:
            day = EPOCH_DAY + timedelta(days=row["holidayDate"])
        except (KeyError, TypeError, OverflowError):
            return result("HOLIDAY_DATE_UNSUPPORTED", [dict(index=index)])
        recurring = row.get("isRecurring")
        if type(recurring) is not bool:
            return result("HOLIDAY_RECURRENCE_ABSENT", [dict(index=index)])
        try:
            holiday_zone = ZoneInfo(row["scheduleTimeZone"])
        except (KeyError, ValueError, TypeError):
            return result("HOLIDAY_TIME_ZONE_UNSUPPORTED", [dict(index=index)])
        first = utc(start).astimezone(holiday_zone).date()
        last = utc(end - 1).astimezone(holiday_zone).date()
        days = {day} if first <= day <= last else set()
        if recurring:
            dates = (first + timedelta(days=i) for i in range((last - first).days + 1))
            days = {current for current in dates if (current.month, current.day) == (day.month, day.day)}
        lo, hi = row.get("startSecond"), row.get("endSecond")
        supported = type(lo) is int and type(hi) is int and 0 <= lo < hi <= DAY_SECONDS
        if not supported:
            issues.append(dict(index=index, date=day.isoformat(), startSecond=lo, endSecond=hi,
                               reason="HOLIDAY_BOUNDS_AMBIGUOUS" if days else "HOLIDAY_OUTSIDE_WINDOW"))
        if days:
            holidays.append((holiday_zone, days, lo, hi, supported))

    opened, ambiguous = [], []
    for at in range(start + (offset - start) % step, end, step):
        instant = utc(at)
        local = instant.astimezone(zone)
        second = ((local.weekday() + 1) % 7) * DAY_SECONDS + (
            local.hour * 3600 + local.minute * 60 + local.second)
        if not any(lo <= second < hi for lo, hi in sessions):
            continue
        closed, uncertain = False, False
        for holiday_zone, days, lo, hi, supported in holidays:
            holiday = instant.astimezone(holiday_zone)
            if holiday.date() not in days:
                continue
            second = holiday.hour * 3600 + holiday.minute * 60 + holiday.second
            if not supported:
                uncertain = True
            elif lo <= second < hi:
                closed = True
                break
        if not closed:
            (ambiguous if uncertain else opened).append(at)

    return result("PARTIALLY_SUPPORTED_SNAPSHOT" if ambiguous else "CONDITIONAL_OFFICIAL_SNAPSHOT",
                  issues, opened, ambiguous)


def from_original_calendar_audit(row, start, end):
    if "contractSha256" not in row:
        return build_clock_grid(None, start, end)
    return build_clock_grid(dict(schedule=row["sessions"], scheduleTimeZone=row["sessionTimeZone"],
                                 holiday=row["holidays"]), start, end)


def attach_calendars(source, snapshots):
    """Join normalised sealed-source inputs to authenticated contract digests."""
    start, end = source["Start"], source["End"]
    for market in source["Markets"]:
        current = market["Market"]
        row = snapshots.get(current["Name"], {})
        if "contractSha256" in row and (row["contractSha256"] != current["DatedDevelopment"]["Digest"] or
                                       row["contractObservedAt"] != market["TermsAcquiredAt"]):
            raise ValueError("CALENDAR_CONTRACT_BINDING")
        grid = from_original_calendar_audit(row, start, end + 7 * DAY_SECONDS * 1000)
        market.update(ScheduledClocks=grid["openClocks"], AmbiguousCalendarClocks=grid["ambiguousClocks"],
                      CalendarStatus=grid["status"] if "contractSha256" in row else
                      row.get("reason", "CALENDAR_NOT_COLLECTED"))
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("custody_normalized_input", type=Path)
    parser.add_argument("verified_calendar_snapshots", type=Path)
    parser.add_argument("replay_input", type=Path)
    args = parser.parse_args()
    source = json.loads(args.custody_normalized_input.read_bytes())
    snapshots = json.loads(args.verified_calendar_snapshots.read_bytes())["calendars"]
    # Normalised quotes, contract terms and funding stay in the custody job.
    normalized = json.dumps(attach_calendars(source, snapshots), separators=(",", ":"), allow_nan=False).encode()
    with os.fdopen(os.open(args.replay_input, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(normalized)


if __name__ == "__main__":
    main()
