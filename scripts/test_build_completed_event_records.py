from build_completed_event_records import compatible, make_record, next_day_implication, surprise
from datetime import datetime
from zoneinfo import ZoneInfo


def main() -> None:
    assert surprise("3.0%", "2.8%") == ("+0.2pt", 0.20000000000000018)
    assert compatible("332.81", "3.4%") is False
    event = {"id":"x","status":"released","importance":3,"datetimeJst":"2026-08-12T21:30:00+09:00","country":"米国","title":"CPI前年比","category":"inflation","previous":"2.7%","forecast":"2.8%","actual":"3.0%"}
    row = make_record(event, datetime(2026, 8, 12, tzinfo=ZoneInfo("Asia/Tokyo")))
    assert row and row["result_judgement"] == "上振れ（インフレ強）"
    assert row["initial_market_reaction"] == "反応確認困難"
    assert row["next_day_implication"]
    assert "利下げ期待" in row["next_day_implication"]
    assert row["market_reaction_conclusion"] == row["next_day_implication"]

    claims = dict(event, id="claims", importance=2, title="米新規失業保険申請件数", category="employment", previous="199K", forecast="202K", actual="209K")
    claims_row = make_record(claims, datetime.now(ZoneInfo("Asia/Tokyo")))
    assert claims_row and claims_row["result_judgement"] == "上振れ（雇用弱）"
    assert "雇用の軟化" in claims_row["next_day_implication"]

    retail = dict(event, id="retail", importance=2, title="米国 小売売上高", category="growth", previous="-0.2%", forecast="0.2%", actual="-0.6%")
    assert "景気減速" in next_day_implication(retail, -0.8)

    bad = dict(event, actual="332.81")
    assert make_record(bad, datetime.now(ZoneInfo("Asia/Tokyo")))["actual"] == "取得不能"
    assert not make_record(bad, datetime.now(ZoneInfo("Asia/Tokyo")))["next_day_implication"]
    missing = dict(event, actual="")
    assert make_record(missing, datetime.now(ZoneInfo("Asia/Tokyo"))) is None
    print("Completed event record tests passed")


if __name__ == "__main__":
    main()
