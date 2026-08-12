from datetime import datetime
from zoneinfo import ZoneInfo

from build_usdjpy_flow_summary import build_speculative, clip, direction, judgement, relationship


def main() -> None:
    assert clip(4 + -2) == 2
    assert judgement(clip(4 + -2), True) == "ややドル買い優勢"
    assert clip(4 + 3) == 5
    assert judgement(5, True) == "強いドル買い優勢"
    assert clip(-3 + -4) == -5
    assert judgement(-5, True) == "強いドル売り優勢"
    assert relationship(4, -2)[0] == "逆行"
    assert relationship(4, 3)[0] == "一致"
    assert direction(-2) == "usd_sell"
    assert direction(None) == "unknown"
    now = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
    stale = build_speculative({"cftc": {"status": "verified", "asOf": "2026-08-04", "netChange": 117939}}, now)
    cftc = next(row for row in stale["drivers"] if row["id"] == "cftc")
    assert cftc["status"] == "stale" and cftc["score"] is None
    print("USDJPY flow summary tests passed")


if __name__ == "__main__":
    main()
