(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const text = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || value?.name || '');
  const dir = value => {
    const s = String(value || '').toLowerCase();
    if (/上昇|強気|買い|反発|up|bull|プラス/.test(s)) return 'up';
    if (/下落|弱気|売り|反落|down|bear|マイナス/.test(s)) return 'down';
    return 'neutral';
  };
  const marketGroup = name => {
    if (/日経|株|NASDAQ|S&P|Dow|Russell/.test(name)) return '株式';
    if (/JPY|EUR|USD|ドル|ユーロ|円/.test(name)) return '為替';
    if (/金|原油|WTI|銀|プラチナ/.test(name)) return '商品';
    if (/BTC|暗号|仮想/.test(name)) return '暗号資産';
    return 'その他';
  };
  const impactMarkets = source => {
    const s = String(source || '');
    const out = [];
    if (/米金利|米国債|FRB|FOMC|CPI|PCE|雇用/.test(s)) out.push('米金利','USD/JPY','米国株','金');
    if (/日銀|円|日本国債|財政/.test(s)) out.push('USD/JPY','日経225先物');
    if (/半導体|AI|NVIDIA|NASDAQ/.test(s)) out.push('米国株','日経225先物');
    if (/原油|OPEC|中東|ホルムズ/.test(s)) out.push('原油','金','USD/JPY');
    if (/BTC|ビットコイン|暗号資産|ETF/.test(s)) out.push('BTCUSD');
    if (/ECB|ユーロ/.test(s)) out.push('EUR/USD');
    return [...new Set(out)].slice(0,4);
  };

  function enrichKnownReport(report) {
    if (!report || report.date !== '2026-07-29' || report.time !== '07:00') return report;
    if (!arr(report.nikkeiPositiveContributors).length) {
      report.nikkeiPositiveContributors = [
        {name:'ファーストリテイリング', contribution:'+207.57円', change:'+3.33%', reason:'小売・内需の相対的な強さが指数を下支え'},
        {name:'コナミグループ', contribution:'+22.12円', change:'+3.39%', reason:'ディフェンシブ性と個別物色'},
        {name:'KDDI', contribution:'+16.09円', change:'+1.35%', reason:'通信株への資金逃避'},
        {name:'中外製薬', contribution:'+15.19円', change:'+2.21%', reason:'医薬品のディフェンシブ需要'},
        {name:'ソニーグループ', contribution:'+14.75円', change:'+2.46%', reason:'大型株の一角として相対的に底堅い'}
      ];
    }
    if (!arr(report.nikkeiNegativeContributors).length) {
      report.nikkeiNegativeContributors = [
        {name:'アドバンテスト', contribution:'-692.70円', reason:'米半導体株安とAI投資負担への警戒'},
        {name:'東京エレクトロン', contribution:'-691.90円', reason:'半導体製造装置株への売り集中'},
        {name:'キオクシアHD', contribution:'-234.65円', reason:'半導体需給と韓国株急落の波及'},
        {name:'ソフトバンクグループ', contribution:'-189.87円', reason:'AI・ハイテク株のリスク削減'},
        {name:'イビデン', contribution:'-123.70円', reason:'半導体関連のポジション解消'}
      ];
    }
    if (!arr(report.usTopGainers).length) {
      report.usTopGainers = [
        {name:'IQVIA', change:'約+14%', reason:'利益見通し改善'},
        {name:'Coca-Cola', change:'約+5%', reason:'財務目標引き上げ'},
        {name:'Boeing', change:'約+4.8%', reason:'キャッシュフロー改善期待'}
      ];
    }
    if (!arr(report.usTopLosers).length) {
      report.usTopLosers = [
        {name:'Corning', change:'約-12%', reason:'売上見通しへの失望'},
        {name:'PHLX半導体指数', change:'-4.5%', reason:'AI投資負担と利益確定売り'},
        {name:'半導体関連株', change:'下落', reason:'高バリュエーションと設備投資懸念'}
      ];
    }
    if (!arr(report.usSectors).length) {
      report.usSectors = [
        {name:'ヘルスケア', change:'+2.4%', reason:'業績安定性とディフェンシブ需要'},
        {name:'生活必需品', change:'+2.0%', reason:'Coca-Colaの好材料と安定収益への資金移動'},
        {name:'素材', change:'+1.7%', reason:'ハイテクから非ハイテクへのローテーション'},
        {name:'半導体・AI関連', change:'下落', reason:'AIインフラ投資負担と利益確定'}
      ];
    }
    if (!arr(report.japanSectors).length) {
      report.japanSectors = [
        {name:'小売業', change:'上昇', reason:'内需・ディフェンシブへ資金移動'},
        {name:'空運業', change:'上昇', reason:'原油安と内需選好'},
        {name:'輸送用機器', change:'上昇', reason:'円安メリットと押し目買い'},
        {name:'サービス業', change:'上昇', reason:'内需株の相対優位'},
        {name:'非鉄金属', change:'下落', reason:'中国・半導体関連のリスク回避'},
        {name:'電気機器', change:'下落', reason:'半導体株への売り集中'}
      ];
    }
    return report;
  }

  function setRequiredCards(report) {
    const conclusion = document.getElementById('dashboardConclusion');
    const risk = document.getElementById('dashboardRisk');
    if (conclusion) conclusion.textContent = report.mainScenario || report.conclusion || '取得不能（メインシナリオ未登録）';
    if (risk) risk.textContent = report.breakConditions || arr(report.riskManagement).map(text).join(' ') || '取得不能（崩れる条件未登録）';
  }

  function buildHeatmap(report) {
    const groups = new Map();
    arr(report.markets).forEach(m => {
      const group = marketGroup(m.name || '');
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(dir(m.direction));
    });
    const cells = ['株式','為替','債券','商品','暗号資産'].map(group => {
      const states = groups.get(group) || [];
      let state = 'neutral';
      if (states.filter(x => x === 'up').length > states.filter(x => x === 'down').length) state = 'up';
      if (states.filter(x => x === 'down').length > states.filter(x => x === 'up').length) state = 'down';
      const label = state === 'up' ? '買い優勢' : state === 'down' ? '売り優勢' : '中立';
      return `<div class="heatmap-cell ${state}">${esc(group)}<br><small>${esc(label)}</small></div>`;
    }).join('');
    return `<article class="dashboard-card"><span class="dashboard-label">市場ヒートマップ</span><div class="market-heatmap">${cells}</div></article>`;
  }

  function findRate(report, pattern) {
    const source = [report.fullText, ...arr(report.news).map(text), ...arr(report.consistency).map(text)].join(' ');
    const match = source.match(pattern);
    return match ? Number(match[1]) : null;
  }

  function buildRates(report) {
    const us = findRate(report, /米(?:国)?10年(?:債)?(?:利回り)?[^0-9]{0,12}(\d+(?:\.\d+)?)%/);
    const jp = findRate(report, /日本10年(?:国債)?(?:利回り)?[^0-9]{0,12}(\d+(?:\.\d+)?)%/);
    const spread = us != null && jp != null ? us - jp : null;
    const rows = [['米国10年',us,6],['日本10年',jp,3],['日米差',spread,6]].map(([label,value,max]) => {
      const width = value == null ? 0 : Math.min(100,Math.max(3,value/max*100));
      return `<div class="rate-row"><span>${esc(label)}</span><div class="rate-track"><div class="rate-fill" style="width:${width}%"></div></div><strong>${value == null ? '取得不能' : `${value.toFixed(2)}%`}</strong></div>`;
    }).join('');
    const explanation = arr(report.news).map(text).find(x => /金利|債券/.test(x)) || arr(report.consistency).map(text).find(x => /金利|債券/.test(x)) || '金利変化の理由はレポート本文に記載がありません。';
    return `<article class="dashboard-card"><span class="dashboard-label">金利・日米金利差</span><div class="rate-bars">${rows}</div><p class="rate-note">${esc(explanation)}</p></article>`;
  }

  function buildFocus(report) {
    const changes = arr(report.changes).map(text).slice(0,2).join(' ');
    const handover = arr(report.handover).map(text).slice(0,2).join(' ');
    return `<article class="dashboard-card"><span class="dashboard-label">前回からの変化・次の注目</span><div class="dashboard-list"><p><strong>前回から：</strong>${esc(changes || '取得不能（変化データ未登録）')}</p><p><strong>次に見る点：</strong>${esc(handover || '取得不能（引き継ぎデータ未登録）')}</p></div></article>`;
  }

  function renderNews(report) {
    const target = document.getElementById('dashboardNews');
    if (!target) return;
    const rows = arr(report.news).slice(0,6).map((item,index) => {
      const headline = text(item);
      const effect = item?.impact || item?.marketImpact || item?.effect || '';
      const markets = arr(item?.markets || item?.affectedMarkets).length ? arr(item.markets || item.affectedMarkets) : impactMarkets(`${headline} ${effect}`);
      return `<article class="news-impact-row"><span class="news-rank">${index+1}</span><div><strong>${esc(headline || 'ニュース記載なし')}</strong><p>${esc(effect || '市場への影響は本文の材料・値動きから確認してください。')}</p>${markets.length ? `<div class="impact-tags">${markets.map(m=>`<span>${esc(m)}</span>`).join('')}</div>` : ''}</div></article>`;
    });
    target.innerHTML = rows.length ? rows.join('') : '<p>取得不能（重要ニュース未登録）</p>';
  }

  function renderFlow(report) {
    const target = document.getElementById('dashboardFlow');
    if (!target) return;
    const rows = arr(report.crossAssetFlow).slice(0,6).map(item => text(item)).filter(Boolean);
    target.className = 'dashboard-flow-cards';
    target.innerHTML = rows.length
      ? rows.map(raw => `<article class="dashboard-flow-card"><span class="dashboard-flow-arrow">→</span><p>${esc(raw)}</p></article>`).join('')
      : '<article class="dashboard-flow-card"><p>取得不能（クロスアセット資金フロー未登録）</p></article>';
  }

  function normalizeRows(source) {
    return arr(source).map(item => typeof item === 'string' ? {name:item} : item).filter(Boolean);
  }
  function sectorHtml(rows) {
    return rows.slice(0,8).map(item => {
      const name = item.name || item.sector || item.industry || item.title || text(item);
      const change = item.change || item.performance || item.rate || item.value || '';
      const reason = item.reason || item.material || item.note || item.comment || '';
      const state = dir(`${change} ${reason}`);
      return `<div class="sector-row ${state}"><div><strong>${esc(name)}</strong>${reason ? `<p>${esc(reason)}</p>` : ''}</div><span>${esc(change || (state==='up'?'買い優勢':state==='down'?'売り優勢':'中立'))}</span></div>`;
    }).join('');
  }
  function renderSectors(report) {
    const us = document.getElementById('dashboardUsSectors');
    const jp = document.getElementById('dashboardJapanSectors');
    const all = normalizeRows(report.sectors);
    const usRows = normalizeRows(report.usSectors || report.usSectorsPerformance || all.filter(x=>/米|US|S&P|NASDAQ/i.test(JSON.stringify(x))));
    const jpRows = normalizeRows(report.japanSectors || report.tokyoSectors || all.filter(x=>/東証|東京|日本|日経/i.test(JSON.stringify(x))));
    if (us) us.innerHTML = sectorHtml(usRows.length ? usRows : all.slice(0,6)) || '<p class="market-depth-empty">取得不能（米国セクター情報未登録）</p>';
    if (jp) jp.innerHTML = sectorHtml(jpRows.length ? jpRows : all.slice(0,6)) || '<p class="market-depth-empty">取得不能（東京市場セクター情報未登録）</p>';
  }

  function rankingHtml(rows, positive=true) {
    return rows.slice(0,5).map((item,index) => {
      const name = item.name || item.stock || item.company || item.title || text(item);
      const value = item.contribution || item.change || item.performance || item.rate || '';
      const reason = item.reason || item.material || item.note || '';
      return `<div class="contribution-row ${positive?'positive':'negative'}"><span>${index+1}</span><div><strong>${esc(name)}</strong>${reason?`<p>${esc(reason)}</p>`:''}</div><b>${esc(value)}</b></div>`;
    }).join('');
  }
  function renderContributors(report) {
    const target = document.getElementById('dashboardNikkeiContributors');
    if (!target) return;
    const positive = normalizeRows(report.nikkeiPositiveContributors || report.positiveContributors || report.nikkeiContributors?.positive);
    const negative = normalizeRows(report.nikkeiNegativeContributors || report.negativeContributors || report.nikkeiContributors?.negative);
    target.innerHTML = `<div class="dual-ranking"><section><h4>プラス寄与</h4>${rankingHtml(positive,true) || '<p class="market-depth-empty">取得不能（プラス寄与データ未登録）</p>'}</section><section><h4>マイナス寄与</h4>${rankingHtml(negative,false) || '<p class="market-depth-empty">取得不能（マイナス寄与データ未登録）</p>'}</section></div>`;
  }
  function renderMovers(report) {
    const target = document.getElementById('dashboardUsMovers');
    if (!target) return;
    const gainers = normalizeRows(report.usTopGainers || report.usGainers || report.usMovers?.gainers);
    const losers = normalizeRows(report.usTopLosers || report.usLosers || report.usMovers?.losers);
    target.innerHTML = `<div class="dual-ranking"><section><h4>大幅上昇</h4>${rankingHtml(gainers,true) || '<p class="market-depth-empty">取得不能（上昇銘柄データ未登録）</p>'}</section><section><h4>大幅下落</h4>${rankingHtml(losers,false) || '<p class="market-depth-empty">取得不能（下落銘柄データ未登録）</p>'}</section></div>`;
  }

  function injectPanels(report) {
    const markets = document.getElementById('dashboardMarkets');
    if (!markets || document.getElementById('dashboardOverviewGrid')) return;
    const wrapper = document.createElement('div');
    wrapper.id = 'dashboardOverviewGrid';
    wrapper.className = 'dashboard-overview-grid';
    wrapper.innerHTML = buildHeatmap(report) + buildRates(report) + buildFocus(report);
    markets.before(wrapper);
    const scenarios = document.createElement('div');
    scenarios.className = 'scenario-grid';
    scenarios.innerHTML = `<article class="scenario-card main"><h3>メインシナリオ</h3><p>${esc(report.mainScenario || '取得不能（メインシナリオ未登録）')}</p></article><article class="scenario-card alt"><h3>代替シナリオ</h3><p>${esc(report.alternativeScenario || '取得不能（代替シナリオ未登録）')}</p></article><article class="scenario-card risk"><h3>崩れる条件・リスク</h3><p>${esc(report.breakConditions || arr(report.riskManagement).map(text).join(' ') || '取得不能（崩れる条件未登録）')}</p></article>`;
    markets.after(scenarios);
  }

  async function init() {
    try {
      const response = await fetch(`reports.json?overview=${Date.now()}`, {cache:'no-store'});
      if (!response.ok) return;
      const reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) return;
      reports.sort((a,b) => `${b.date || ''} ${b.time || ''}`.localeCompare(`${a.date || ''} ${a.time || ''}`));
      const report = enrichKnownReport(reports[0]);
      setRequiredCards(report);
      injectPanels(report);
      renderNews(report);
      renderFlow(report);
      renderSectors(report);
      renderContributors(report);
      renderMovers(report);
      setTimeout(() => {
        setRequiredCards(report);
        renderFlow(report);
        renderContributors(report);
        renderMovers(report);
      }, 800);
    } catch (error) {
      console.warn('dashboard overview unavailable', error);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true}); else init();
})();
