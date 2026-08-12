from datetime import datetime
from zoneinfo import ZoneInfo

from build_usdjpy_flow_summary import clip, direction, judgement, relationship


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
    assert datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
    print("USDJPY flow summary tests passed")


if __name__ == "__main__":
    main()
