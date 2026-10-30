from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scripts import fetch_market_data as market_data
from scripts import validate_market_data_source as source_validator


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
    def test_stale_reference_is_reported_but_does_not_fail_independent_validation_job(self):
        stale = {"status":"rejected","referenceOnly":True,"validationCode":"STALE_DATA"}
        self.assertEqual(source_validator.validation_exit_code(stale),0)
        primary_stale = {**stale,"referenceOnly":False}
        self.assertEqual(source_validator.validation_exit_code(primary_stale),1)
        other_reference_error = {**stale,"validationCode":"SOURCE_TIMEOUT"}
        self.assertEqual(source_validator.validation_exit_code(other_reference_error),1)


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

    def test_boj_daily_pdf_selects_latest_two_official_publications(self):
        source={"id":"boj_usdjpy_17_reference","name":"BOJ USD/JPY 17:00",
                "listingUrl":"https://www.boj.or.jp/statistics/market/forex/fxdaily/index.htm",
                "sourceUrl":"https://www.boj.or.jp/statistics/market/forex/fxdaily/index.htm",
                "sourceSeriesId":"boj:USDJPY:spot:17:00:JST:bid_offer_midpoint",
                "marketType":"spot","session":"tokyo_17_daily_reference",
                "observationHourJst":17,"publishedDecimalPlaces":2}
        listing='''<a href="/statistics/market/forex/fxdaily/fxlist/fx261009.pdf">Oct 9</a>
                   <a href="/statistics/market/forex/fxdaily/fxlist/fx261008.pdf">Oct 8</a>
                   <a href="/statistics/market/forex/fxdaily/fxlist/fx261007.pdf">Oct 7</a>'''
        texts=[
            "At 9:00 JST 158.04-05 1.1212-13 177.20-24\\nAt 17:00 JST 158.33-34 1.1231-33 177.83-87",
            "At 9:00 JST 158.10-11 1.1201-02 177.20-24\\nAt 17:00 JST 158.10-11 1.1202-03 177.20-24",
        ]
        fixed_now=market_data.dt.datetime(2026,10,12,22,tzinfo=market_data.JST)
        with patch.object(market_data,"http_text",return_value=listing), patch.object(
            market_data,"http_get",side_effect=[(b"latest pdf","application/pdf"),(b"prior pdf","application/pdf")],
        ), patch.object(market_data,"extract_boj_pdf_text",side_effect=texts), patch.object(
            market_data,"now_jst",return_value=fixed_now,
        ):
            value=market_data.fetch_boj_daily_fx_pdf(source)
        self.assertEqual(value["value"],158.34)
        self.assertEqual(value["previousClose"],158.11)
        self.assertEqual(value["asOf"],"2026-10-09T17:00:00+09:00")
        self.assertEqual(value["sourceSeriesId"],source["sourceSeriesId"])
        self.assertEqual(value["reportedDecimalPlaces"],2)
        self.assertEqual(value["rawReference"],"BOJ daily FX PDF 2026-10-09")

    def test_boj_pdf_midpoint_parses_shorthand_bid_offer(self):
        self.assertEqual(market_data.parse_boj_shorthand_range("158.33-34"),market_data.Decimal("158.335"))
        self.assertEqual(market_data.parse_boj_shorthand_range("1.1231-33"),market_data.Decimal("1.1232"))

    def test_boj_daily_pdf_rejects_missing_17h_quote(self):
        source={"id":"boj","name":"BOJ","sourceSeriesId":"boj:test","marketType":"spot","session":"tokyo"}
        with self.assertRaises(market_data.FetchError) as raised:
            market_data.parse_boj_usdjpy_17_pdf_text("Foreign Exchange Rates\\nAt 9:00 JST 158.04-05",source,market_data.dt.date(2026,10,9))
        self.assertEqual(raised.exception.code,"PARSE_ERROR")

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


    def test_ecb_daily_csv_selects_usd_per_eur_and_preserves_reference_date(self):
        source={"id":"ecb_eurusd_daily_reference","name":"ECB EUR/USD reference",
                "url":"https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A",
                "seriesKey":"D.USD.EUR.SP00.A","marketType":"spot",
                "session":"euro_reference_daily_1600_cet","currency":"USD",
                "currencyDenominator":"EUR","lookbackDays":20}
        payload=("KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
                 "D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-10-08,1.1201\n"
                 "D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-10-09,1.1206\n").encode()
        seen={}
        def fake_http_get(url,timeout=20,headers=None):
            seen.update(url=url,timeout=timeout,headers=headers)
            return payload,"utf-8"
        fixed_now=market_data.dt.datetime(2026,10,12,10,tzinfo=market_data.JST)
        with patch.object(market_data,"http_get",side_effect=fake_http_get), patch.object(
            market_data,"now_jst",return_value=fixed_now
        ):
            value=market_data.fetch_ecb_reference_rate(source)
        self.assertEqual(value["value"],1.1206)
        self.assertEqual(value["previousClose"],1.1201)
        self.assertEqual(value["asOf"],"2026-10-09")
        self.assertEqual(value["rawReference"],"D.USD.EUR.SP00.A")
        self.assertIn("startPeriod=2026-09-22",seen["url"])
        self.assertIn("format=csvdata",seen["url"])

    def test_ecb_parser_rejects_rows_for_a_different_currency_pair(self):
        source={"id":"ecb","name":"ECB","url":"https://example.test","seriesKey":"D.USD.EUR.SP00.A",
                "currency":"USD","currencyDenominator":"EUR"}
        payload=("CURRENCY,CURRENCY_DENOM,TIME_PERIOD,OBS_VALUE\n"
                 "JPY,EUR,2026-10-09,177.34\n").encode()
        with patch.object(market_data,"http_get",return_value=(payload,"utf-8")):
            with self.assertRaises(market_data.FetchError) as raised:
                market_data.fetch_ecb_reference_rate(source)
        self.assertEqual(raised.exception.code,"PARSE_ERROR")


    def test_kraken_adapter_uses_last_completed_utc_btcusd_candle(self):
        source={"id":"kraken_btcusd_daily_close","name":"Kraken BTC/USD daily close",
                "url":"https://api.kraken.com/0/public/OHLC","pair":"XBTUSD",
                "resultKey":"XXBTZUSD","intervalMinutes":1440,"marketType":"spot_crypto",
                "session":"kraken_utc_daily_close"}
        dates=[market_data.dt.datetime(2026,10,8,tzinfo=market_data.UTC),
               market_data.dt.datetime(2026,10,9,tzinfo=market_data.UTC),
               market_data.dt.datetime(2026,10,10,tzinfo=market_data.UTC)]
        rows=[[int(d.timestamp()),"1","2","0.5",str(close),"1","1",1]
              for d,close in zip(dates,[62000,62500,63000])]
        seen={}
        def fake_http_text(url,timeout=20,headers=None):
            seen.update(url=url,timeout=timeout,headers=headers)
            return json.dumps({"error":[],"result":{"XXBTZUSD":rows,"last":123}})
        with patch.object(market_data,"http_text",side_effect=fake_http_text):
            value=market_data.fetch_kraken_ohlc(source)
        self.assertEqual(value["value"],62500.0)
        self.assertEqual(value["previousClose"],62000.0)
        self.assertEqual(value["asOf"],"2026-10-09T23:59:59+00:00")
        self.assertIn("pair=XBTUSD",seen["url"])
        self.assertIn("interval=1440",seen["url"])

    def test_kraken_adapter_fails_on_api_error(self):
        source={"id":"kraken","url":"https://api.kraken.com/0/public/OHLC",
                "pair":"XBTUSD","resultKey":"XXBTZUSD","intervalMinutes":1440}
        with patch.object(market_data,"http_text",return_value='{"error":["EGeneral:Invalid arguments"],"result":{}}'):
            with self.assertRaises(market_data.FetchError) as raised:
                market_data.fetch_kraken_ohlc(source)
        self.assertEqual(raised.exception.code,"SOURCE_ERROR")



    def test_official_nikkei_vi_profile_parses_japanese_title_and_jst_timestamp(self):
        source={"id":"nikkei_vi","name":"Nikkei VI official profile","url":"https://indexes.nikkei.co.jp/nkave/index/profile?cid=7&idx=nk225vi",
                "marketType":"index","session":"daily"}
        html_text="<h1>日経平均ボラティリティー・インデックス</h1><span>30.14</span><span>+1.86% +0.55 2026.10.09(15:50)</span>"
        with patch.object(market_data,"http_text",return_value=html_text):
            value=market_data.fetch_nikkei_profile(source)
        self.assertEqual(value["value"],30.14)
        self.assertEqual(value["asOf"],"2026-10-09T15:50:00+09:00")
        self.assertEqual(value["reportedDecimalPlaces"],2)

    def test_nikkei_official_daily_csv_selects_latest_close_not_future_row(self):
        source={"id":"nikkei_official_daily","name":"Nikkei official daily CSV","url":"https://example.test/nikkei.csv",
                "marketType":"index","session":"japan_cash","targetDate":"2026-10-09"}
        payload=("日付,終値,始値,高値,安値\n"
                 "2026.10.08,69042.11,69840.64,69918.20,69042.11\n"
                 "2026.10.09,69030.92,68648.50,69143.45,68150.02\n"
                 "2026.10.13,70000.00,69000.00,70100.00,68900.00\n").encode("utf-8")
        with patch.object(market_data,"http_get",return_value=(payload,"utf-8")):
            value=market_data.fetch_nikkei_daily_csv(source)
        self.assertEqual(value["value"],69030.92)
        self.assertEqual(value["previousClose"],69042.11)
        self.assertEqual(value["asOf"],"2026-10-09T15:30:00+09:00")
        self.assertEqual(value["reportedDecimalPlaces"],2)

    def test_nikkei_official_sma_uses_exact_window_on_or_before_target(self):
        source={"id":"nikkei_dev25","name":"Nikkei official SMA25","url":"https://example.test/nikkei.csv",
                "marketType":"technical","underlyingMarketType":"index","session":"japan_cash",
                "targetDate":"2026-10-09","window":25}
        dates=[]
        day=market_data.dt.date(2026,9,1)
        while len(dates)<26:
            if day.weekday()<5:
                dates.append(day)
            day += market_data.dt.timedelta(days=1)
        rows=["Date,Close"]
        rows += [f"{d:%Y.%m.%d},{i}" for i,d in enumerate(dates,1)]
        payload=("\n".join(rows)+"\n").encode("utf-8")
        with patch.object(market_data,"http_get",return_value=(payload,"utf-8")):
            value=market_data.fetch_nikkei_sma_deviation(source)
        self.assertAlmostEqual(value["value"],(26/14-1)*100)
        self.assertEqual(value["asOf"],f"{dates[25].isoformat()}T15:30:00+09:00")
        self.assertEqual(value["window"],25)
        self.assertEqual(value["marketType"],"technical")
        self.assertEqual(source["underlyingMarketType"],"index")
        accepted, code, _ = market_data.validate_candidate(
            "nikkei225_dev25", {"marketType":"technical"}, {"min":-50,"max":50}, value, None
        )
        self.assertTrue(accepted, code)

    def test_nikkei_csv_fails_closed_if_close_column_is_not_identifiable(self):
        source={"id":"nikkei","name":"Nikkei","url":"https://example.test","targetDate":"2026-10-09"}
        payload=b"Date,Open,High,Low,Volume\n2026.10.09,1,2,0,10\n"
        with patch.object(market_data,"http_get",return_value=(payload,"utf-8")):
            with self.assertRaises(market_data.FetchError) as raised:
                market_data.fetch_nikkei_daily_csv(source)
        self.assertEqual(raised.exception.code,"PARSE_ERROR")



if __name__ == "__main__":
    unittest.main()
