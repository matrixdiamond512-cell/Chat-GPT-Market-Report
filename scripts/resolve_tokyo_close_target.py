#!/usr/bin/env python3
"""Resolve the latest eligible Tokyo close date without treating Japanese holidays as sessions."""
from __future__ import annotations
import argparse
import datetime as dt
from zoneinfo import ZoneInfo
import jpholiday

def is_tokyo_session(day: dt.date) -> bool:
    # TSE market holidays include Japanese national holidays and year-end closures.
    return day.weekday() < 5 and not jpholiday.is_holiday(day) and not (
        (day.month == 1 and day.day in (1, 2, 3)) or
        (day.month == 12 and day.day == 31)
    )

def resolve(now: dt.datetime, explicit: str = "") -> tuple[str, bool]:
    if explicit:
        target=dt.date.fromisoformat(explicit)
        if not is_tokyo_session(target):
            raise ValueError(f"Explicit target {target} is not a Tokyo trading day")
        return target.isoformat(), False
    today=now.date()
    # A weekday holiday after the cash close must not be published as a missing
    # same-day close; this is an expected skip, not an acquisition error.
    if today.weekday() < 5 and now.time() >= dt.time(16) and not is_tokyo_session(today):
        return today.isoformat(), True
    candidate=today if now.time() >= dt.time(16) else today-dt.timedelta(days=1)
    while not is_tokyo_session(candidate):
        candidate -= dt.timedelta(days=1)
    return candidate.isoformat(), False

def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--target-date",default="")
    p.add_argument("--github-output",default="")
    p.add_argument("--now",default="")
    args=p.parse_args()
    now=dt.datetime.fromisoformat(args.now) if args.now else dt.datetime.now(ZoneInfo("Asia/Tokyo"))
    date,skip=resolve(now,args.target_date)
    lines=f"date={date}\nskip={'true' if skip else 'false'}\n"
    if args.github_output:
        with open(args.github_output,"a",encoding="utf-8") as output:
            output.write(lines)
    print(f"Tokyo session resolution: date={date} skip={skip}")

if __name__ == "__main__":
    main()
