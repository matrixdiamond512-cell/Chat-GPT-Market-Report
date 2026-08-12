from datetime import datetime
from zoneinfo import ZoneInfo

from build_usdjpy_flow_summary import build_speculative, clip, direction, judgement, parse_securities_pdf, parse_trade_pdf, relationship


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
    trade = parse_trade_pdf("10,926,535 9,162,327 19.3\n11,336,461 9,040,057 25.4\n▲ 409,926 122,270 -", "2026-06")
    assert trade["balance"] == -409926
    securities = parse_securities_pdf("""1．対外証券投資
30,449 33,213 -2,764 93,013 88,234 4,779 2,015 12,021 7,774 4,247 6,262
2．対内証券投資
468,415 472,340 -3,925 60,022 54,434 5,589 1,664 38,916 41,845 -2,929 -1,266
July 26, - August 1, 2026""")
    assert securities == {"asOf": "2026-08-01", "outward": 6262, "inward": -1266}
    now = datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
    stale = build_speculative({"cftc": {"status": "verified", "asOf": "2026-08-04", "netChange": 117939}}, now)
    cftc = next(row for row in stale["drivers"] if row["id"] == "cftc")
    assert cftc["status"] == "stale" and cftc["score"] is None
    print("USDJPY flow summary tests passed")


if __name__ == "__main__":
    main()
