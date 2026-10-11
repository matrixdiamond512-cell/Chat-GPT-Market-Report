from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scripts import fetch_market_data as market_data


MOF_CSV = """Date,1yr,2yr,3yr,4yr,5yr,6yr,7yr,8yr,9yr,10yr,15yr,20yr,25yr,30yr,40yr
2026-10-08,1.001,1.002,1.003,1.004,1.005,1.006,1.007,1.008,1.009,3.004,3.2,3.3,3.4,3.5,3.6
2026-10-09,1.101,1.102,1.103,1.104,1.105,1.106,1.107,1.108,1.109,3.125,3.3,3.4,3.5,3.6,3.7
"""

BOJ_JSON = {
    "STATUS": "200",
    "RESULTSET": [{
        "SERIES_CODE": "FXERD04",
        "FREQUENCY": "DAILY",
        "UNIT": "yen per U.S. dollar",
        "VALUES": {"SURVEY_DATES": [20261008, 20261009], "VALUES": [152.15, 152.4]},
    }],
}


class OfficialMarketDataAdapterTests(unittest.TestCase):
    def test_mof_daily_csv_selects_ten_year_column_and_preserves_date(self):
        source = {"id":"mof_jgbcm_10y","name":"MOF JGB CMT 10Y","kind":"mof_jgb_yield_csv",
                  "url":"https://www.mof.go.jp/example.csv","marketType":"yield",
                  "session":"daily_1500_jst_published_next_business_day","encoding":"utf-8"}
        with patch.object(market_data,"http_get",return_value=(MOF_CSV.encode(),"utf-8")):
            value=market_data.fetch_mof_jgb_yield_csv(source)
        self.assertEqual(value["value"],3.125)
        self.assertEqual(value["asOf"],"2026-10-09")
        self.assertEqual(value["previousClose"],3.004)
        self.assertEqual(value["reportedDecimalPlaces"],3)
        self.assertEqual(value["sourceId"],"mof_jgbcm_10y")

    def test_mof_parser_handles_japanese_era_dates_and_cp932(self):
        content=("基準日,1年,2年,3年,4年,5年,6年,7年,8年,9年,10年,15年,20年,25年,30年,40年\n"
                 "R8.10.09,1,2,3,4,5,6,7,8,9,3.125,15,20,25,30,40\n").encode("cp932")
        source={"id":"mof","name":"MOF","url":"https://example.test","encoding":"cp932",
                "marketType":"yield","session":"daily"}
        with patch.object(market_data,"http_get",return_value=(content,"cp932")):
            value=market_data.fetch_mof_jgb_yield_csv(source)
        self.assertEqual(value["asOf"],"2026-10-09")
        self.assertEqual(value["value"],3.125)

    def test_boj_daily_api_selects_series_and_assigns_tokyo_17_time(self):
        source={"id":"boj_usdjpy_17_reference","name":"BOJ USD/JPY 17:00",
                "url":"https://www.stat-search.boj.or.jp/api/v1/getDataCode","database":"FM08",
                "seriesCode":"FXERD04","marketType":"spot","session":"tokyo_17_daily_reference",
                "observationHourJst":17,"publishedDecimalPlaces":2}
        seen={}
        def fake_http_text(url,timeout=20,headers=None):
            seen.update(url=url,timeout=timeout,headers=headers)
            return json.dumps(BOJ_JSON)
        fixed_now=market_data.dt.datetime(2026,10,12,10,tzinfo=market_data.JST)
        with patch.object(market_data,"http_text",side_effect=fake_http_text), patch.object(
            market_data,"now_jst",return_value=fixed_now
        ):
            value=market_data.fetch_boj_time_series(source)
        self.assertEqual(value["value"],152.4)
        self.assertEqual(value["previousClose"],152.15)
        self.assertEqual(value["asOf"],"2026-10-09T17:00:00+09:00")
        self.assertIn("db=FM08",seen["url"])
        self.assertIn("code=FXERD04",seen["url"])
        self.assertIn("startDate=202607",seen["url"])

    def test_boj_non_success_status_fails_closed(self):
        source={"id":"boj","name":"BOJ","url":"https://www.stat-search.boj.or.jp/api/v1/getDataCode",
                "database":"FM08","seriesCode":"FXERD04"}
        with patch.object(market_data,"http_text",return_value='{"STATUS":"400","MESSAGE":"bad parameters"}'):
            with self.assertRaises(market_data.FetchError) as raised:
                market_data.fetch_boj_time_series(source)
        self.assertEqual(raised.exception.code,"SOURCE_ERROR")


if __name__ == "__main__":
    unittest.main()
