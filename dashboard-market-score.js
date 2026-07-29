(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const text = value => typeof value === 'string' ? value : (value?.text || value?.summary || value?.title || '');
  const first = (...values) => values.find(v => typeof v === 'string' && v.trim()) || '';
  const positive = /上昇|強気|買い|反発|改善|流入|買い戻し|ショートカバー|追い風|支持|底堅|リスクオン|低下/gi;
  const negative = /下落|弱気|売り|反落|悪化|流出|利食い|逆風|警戒|上値重|リスクオフ|上昇/gi;
  const categories = [
    ['方向感', m => m.direction],
    ['材料', m => `${first(m.material,m.outlook)} ${first(m.boughtReason,m.buyReason,m.bullishReason,m.positiveDriver)} ${first(m.soldReason,m.sellReason,m.bearishReason,m.negativeDriver)}`],
    ['需給', m => first(m.positioning,m.supplyDemand,m.flow)],
    ['短期見通し', m => first(m.shortTermOutlook,m.shortOutlook,m.outlook,m.mainScenario)],
    ['中期見通し', m => first(m.mediumTermOutlook,m.mediumOutlook,m.mainScenario)],
  ];
  const count = (source, re) => (String(source || '').match(re) || []).length;
  function evaluate(label, source) {
    const s = String(source || '');
    if (!s.trim()) return {label, score:0, state:'neutral', note:'記載なし'};
    let score = count(s,positive) - count(s,negative);
    if (/方向感/.test(label)) {
      if (/強気|上昇|買い/.test(s)) score += 2;
      if (/弱気|下落|売り/.test(s)) score -= 2;
    }
    score = Math.max(-3,Math.min(3,score));
    return {label,score,state:score>0?'up':score<0?'down':'neutral',note:s};
  }
  function marketScore(market) {
    const factors = categories.map(([label,get]) => evaluate(label,get(market)));
    const explicit = Number(market.score ?? market.decisionScore);
    const total = Number.isFinite(explicit) ? Math.max(-100,Math.min(100,explicit)) : Math.round(factors.reduce((sum,x)=>sum+x.score,0) / (factors.length*3) * 100);
    const state = total >= 20 ? 'up' : total <= -20 ? 'down' : 'neutral';
    const judgement = state === 'up' ? '強気' : state === 'down' ? '弱気' : '中立';
    const confidence = Math.min(100,Math.max(35,Math.abs(total)+35));
    return {total,state,judgement,confidence,factors};
  }
  function factorRows(factors) {
    return factors.map(f => `<div class="score-factor"><span>${esc(f.label)}</span><div class="score-factor-track"><i class="${f.state}" style="width:${Math.max(8,Math.abs(f.score)/3*100)}%"></i></div><b class="state-${f.state}">${f.state==='up'?'＋':f.state==='down'?'－':'±'}</b></div>`).join('');
  }
  function buildCard(market) {
    const score = marketScore(market);
    const invalidation = first(market.breakCondition,market.invalidation,market.breakConditions) || 'レポートに記載なし';
    return `<article class="decision-score-card score-${score.state}">
      <div class="score-card-head"><div><span class="dashboard-label">総合判断</span><h3>${esc(market.name || '市場')}</h3></div><div class="score-number"><strong>${score.total>0?'+':''}${score.total}</strong><small>/100</small></div></div>
      <div class="score-verdict"><span>${score.judgement}</span><small>判断確度 ${score.confidence}%</small></div>
      <div class="score-meter"><i style="left:${(score.total+100)/2}%"></i></div>
      <div class="score-factors">${factorRows(score.factors)}</div>
      <p class="score-invalidation"><b>見方を変える条件：</b>${esc(invalidation)}</p>
    </article>`;
  }
  async function init() {
    try {
      const response = await fetch(`reports.json?score=${Date.now()}`,{cache:'no-store'});
      if (!response.ok) return;
      const reports = await response.json();
      if (!Array.isArray(reports) || !reports.length) return;
      reports.sort((a,b)=>`${b.date||''} ${b.time||''}`.localeCompare(`${a.date||''} ${a.time||''}`));
      const report = reports[0];
      const markets = arr(report.markets).slice(0,6);
      const anchor = document.getElementById('dashboardMarkets');
      if (!anchor || document.getElementById('marketDecisionScores')) return;
      const section = document.createElement('section');
      section.id = 'marketDecisionScores';
      section.className = 'market-score-section';
      section.innerHTML = `<div class="section-heading"><div><p class="section-kicker">DECISION MATRIX</p><h2>6市場の総合判断</h2></div><p>レポート内の方向感・材料・需給・短中期見通しをルールベースで点数化</p></div><div class="decision-score-grid">${markets.map(buildCard).join('')}</div><p class="score-method-note">この点数は価格予測の確率ではなく、レポート本文に含まれる強気・弱気材料の偏りを可視化したものです。売買判断では必ず「見方を変える条件」とイベントリスクも確認してください。</p>`;
      anchor.insertAdjacentElement('beforebegin',section);
    } catch (_) {}
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',init,{once:true}); else init();
})();