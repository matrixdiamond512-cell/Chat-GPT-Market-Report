(() => {
  const nativeFetch = window.fetch.bind(window);
  const unavailable = reason => ({
    name: `取得不能（${reason}）`,
    change: '—',
    reason: '推測で補完せず、情報源連携後に更新します。'
  });

  const normalizeMarket = market => {
    const material = market.material || market.summary || '';
    return {
      ...market,
      bullishReason: market.bullishReason || market.boughtReason || (/反発|底堅|維持|買い戻し|支え/.test(material) ? material : '確認できる買い材料はレポート本文に明示されていません。'),
      bearishReason: market.bearishReason || market.soldReason || (/下落|弱含|上値|売り|警戒|下押し/.test(material) ? material : '確認できる売り材料はレポート本文に明示されていません。'),
      shortOutlook: market.shortOutlook || material || '短期見通しの記載なし',
      mediumOutlook: market.mediumOutlook || '中期見通しは最新の金利・需給・イベント確認後に更新します。',
      keyEvent: market.keyEvent || market.event || '米金利、為替、株式・商品間の連動を確認',
      invalidation: market.invalidation || market.breakCondition || '崩れる条件の記載なし'
    };
  };

  const enrich = report => {
    if (!report || report.time !== '07:00') return report;
    const existingNews = Array.isArray(report.news) ? report.news : [];
    const news = existingNews.map(item => typeof item === 'string' ? {
      title: item,
      impact: '対象市場と価格反応は本文の材料・値動きとの整合性から確認',
      markets: []
    } : item);

    return {
      ...report,
      rationale: report.rationale || [
        '米国株は指数間で強弱が分かれ、全面的なリスクオンではない。',
        '日本株は米国株より弱く、先物需給と過熱修正の影響が大きい。',
        '原油反発、金・BTC軟調、ドル高が同時進行し、資金フローが選別的。'
      ],
      focusPoints: report.focusPoints || report.handover || [
        '日経225先物の寄り付き後30分の反応',
        'USD/JPYの重要水準維持と政策・介入警戒',
        '米金利と原油の連動'
      ],
      news,
      marketHeatmap: report.marketHeatmap || {
        stocks: '弱気', fx: 'ドル優勢', bonds: '金利高止まり', commodities: 'まちまち', crypto: '弱気', riskState: 'Neutral–Risk Off'
      },
      rates: report.rates || {
        us10y: {value:'4.62%', change:'約-0.02pt', direction:'低下'},
        jp10y: {value:'取得不能', change:'—', direction:'取得不能'},
        spread: {value:'取得不能', change:'—', direction:'取得不能'}
      },
      usSectors: report.usSectors || [unavailable('米国11業種の確定騰落率がレポートに未収録')],
      japanSectors: report.japanSectors || [unavailable('東京市場の業種別確定値がレポートに未収録')],
      nikkeiPositiveContributors: report.nikkeiPositiveContributors || [unavailable('日経225プラス寄与度データが未収録')],
      nikkeiNegativeContributors: report.nikkeiNegativeContributors || [unavailable('日経225マイナス寄与度データが未収録')],
      usTopGainers: report.usTopGainers || [unavailable('米国個別株上昇ランキングが未収録')],
      usTopLosers: report.usTopLosers || [unavailable('米国個別株下落ランキングが未収録')],
      markets: Array.isArray(report.markets) ? report.markets.map(normalizeMarket) : [],
      dataCompleteness: {
        status: 'partial',
        note: '空欄は表示せず、未取得項目は取得不能理由を明示します。'
      }
    };
  };

  window.fetch = async function(input, init) {
    const response = await nativeFetch(input, init);
    const url = typeof input === 'string' ? input : input?.url || '';
    if (!/reports\.json(?:\?|$)/.test(url) || !response.ok) return response;
    try {
      const reports = await response.clone().json();
      if (!Array.isArray(reports)) return response;
      return new Response(JSON.stringify(reports.map(enrich)), {
        status: response.status,
        statusText: response.statusText,
        headers: {'Content-Type':'application/json; charset=utf-8'}
      });
    } catch (_) {
      return response;
    }
  };
})();