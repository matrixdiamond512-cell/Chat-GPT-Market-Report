(() => {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const arr = (v) => Array.isArray(v) ? v : (v ? [v] : []);
  const text = (v) => typeof v === 'string' ? v : (v?.text || v?.summary || v?.title || v?.name || '');
  const list = (items, max = 5) => {
    const values = arr(items).map(text).filter(Boolean).slice(0, max);
    return values.length ? `<ul>${values.map(v => `<li>${esc(v)}</li>`).join('')}</ul>` : '<p>構造化データがありません。</p>';
  };
  const rows = (items, positive) => arr(items).slice(0, 5).map(x => `<div class="row"><span>${esc(x.name || x.title || text(x))}</span><b class="${positive ? 'pos' : 'neg'}">${esc(x.contribution || x.change || x.rate || '')}</b></div>`).join('') || '<p>データがありません。</p>';

  const fallback = {
    date:'2026-07-29', time:'07:00', title:'マーケットレポート｜2026/07/29（水）07:00',
    theme:'米国株の強弱混在と日本株の急落、原油反発、ドル高基調が同時進行。東京市場では日経225先物の大幅下落後の自律反発余地と、ドル円163円台の高値圏推移が焦点。',
    changes:['米国市場ではDowとS&P 500が上昇した一方、Nasdaqは小幅安。日本株は米株より明確に弱く、日経225現物と大阪先物が約4%下落。'],
    consistency:['米国株の指数間格差は大型景気敏感株への資金移動とハイテク株の利益確定を示す。日本株の急落は先物需給、円安の副作用、過熱修正が重なった可能性。'],
    leadingMarket:'東京時間は日経225先物とUSD/JPYが主導。米金利高止まりと円安の副作用が株式の上値を抑える。',
    news:['米10年債利回りは4.62%近辺で高水準。','原油は80ドル台へ反発し、インフレ再加速懸念が残る。','日本市場では急落後の先物買い戻しと円安警戒が焦点。'],
    crossAssetFlow:['大型株の一部と原油、ドルへ選別流入。ハイテク、金、BTCからは資金流出。日本株は先物主導のリスク削減が優勢。'],
    positioning:['日経225先物はロング解消後の買い戻し余地。','ドル円は円ショートが残り、高値圏では介入・政策発言リスク。','金はロング調整、原油はショートカバー、BTCは戻り売り。'],
    events:['東京時間は寄り付き後30分の日経225先物、ドル円163円台維持、アジア株の反応を確認。','欧州時間以降は米金利、原油、米株先物の方向が重要。'],
    handover:['東京市場では先物の初動、ドル円、東証プライム騰落銘柄数を確認。欧州時間には米金利と原油の連動を引き継ぐ。'],
    mainScenario:'日経225先物は寄り後に自律反発を試すが、戻り売りで上値が抑えられる。ドル円は163円台中心、原油は底堅く、金とBTCは弱含み。',
    alternativeScenario:'米金利低下と米株先物上昇が同時に進めば、日経225先物の買い戻しが強まり、金・BTCも反発。',
    breakConditions:'日経225先物が前日安値を明確に割り込み、VIXが20を超えて上昇する場合は自律反発シナリオを撤回。',
    markets:[
      {name:'金',direction:'下落・弱気',price:'4,048.00',change:'-26.55（-0.65%）',material:'4,000近辺を維持できれば下げ止まり余地。米金利上昇なら下押し。',breakCondition:'4,000を明確に割り込む場合'},
      {name:'原油',direction:'上昇・強気',price:'80.93',change:'+0.68（+0.85%）',material:'80ドル台維持なら反発継続。',breakCondition:'80ドルを明確に割り込む場合'},
      {name:'日経225先物',direction:'下落・弱気',price:'62,400',change:'-2,770（-4.25%）',material:'急落後の反発余地はあるが戻り売り優勢。',breakCondition:'前日安値を明確に割り込む場合'},
      {name:'USD/JPY',direction:'中立・レンジ',price:'163.77',change:'-0.01（-0.01%）',material:'米金利が低下しなければ底堅いが政策発言に注意。',breakCondition:'163円台を維持できない場合'},
      {name:'EUR/USD',direction:'下落・弱気',price:'1.1393',change:'-0.0011（-0.10%）',material:'ドル高基調の中で上値が重い。',breakCondition:'1.14を明確に回復する場合'},
      {name:'BTCUSD',direction:'下落・弱気',price:'63,521',change:'-249（-0.39%）',material:'株安・流動性悪化が続けば戻り売り優勢。',breakCondition:'米株反発とともに上値回復する場合'}
    ],
    usSectors:[{name:'ヘルスケア',change:'買い優勢'},{name:'生活必需品',change:'買い優勢'},{name:'素材',change:'買い優勢'},{name:'半導体・AI',change:'売り優勢'}],
    japanSectors:[{name:'小売',change:'買い優勢'},{name:'空運',change:'買い優勢'},{name:'輸送用機器',change:'買い優勢'},{name:'電気機器',change:'売り優勢'}],
    nikkeiPositiveContributors:[{name:'ファーストリテイリング',contribution:'+207.57円'},{name:'KDDI',contribution:'+16.09円'},{name:'ソニーグループ',contribution:'+14.75円'}],
    nikkeiNegativeContributors:[{name:'アドバンテスト',contribution:'-692.70円'},{name:'東京エレクトロン',contribution:'-691.90円'},{name:'ソフトバンクグループ',contribution:'-189.87円'}],
    usTopGainers:[{name:'IQVIA',change:'約+14%'},{name:'Coca-Cola',change:'約+5%'},{name:'Boeing',change:'約+4.8%'}],
    usTopLosers:[{name:'Corning',change:'約-12%'},{name:'PHLX半導体指数',change:'-4.5%'},{name:'半導体関連株',change:'下落'}]
  };

  async function loadReport(){
    try {
      const res = await fetch('reports.json?ts=' + Date.now(), {cache:'no-store'});
      if (!res.ok) throw new Error('reports.json');
      const data = await res.json();
      const reports = Array.isArray(data) ? data : (data.reports || []);
      if (reports.length) return reports[0];
    } catch (_) {}
    return fallback;
  }

  function directionClass(v){
    return /上昇|強気|買い/.test(v) ? 'up' : /下落|弱気|売り/.test(v) ? 'down' : 'neutral';
  }

  function renderTabs(){
    const labels=['相場テーマ','市場概況','ニュース','金利','資金フロー','需給','6市場','セクター','寄与度','シナリオ','リスク'];
    $('#tabs').innerHTML=labels.map((x,i)=>`<a href="#s${i}">${i+1} ${x}</a>`).join('');
  }

  function marketSummary(r){
    const defs=[['株式','📈','日経225先物'],['為替','🌐','USD/JPY'],['債券（金利）','🏦',null],['商品','🛢','原油'],['暗号資産','₿','BTCUSD']];
    return defs.map(([label,icon,key])=>{
      const hit=key ? arr(r.markets).find(x=>(x.name||'').includes(key)) : null;
      const direction=hit?.direction || (label.includes('債券') ? '中立・高金利' : '中立');
      const note=hit?.material || (label.includes('債券') ? '米10年債利回りは高止まり。株式のバリュエーションを抑制。' : '構造化データなし');
      return `<article class="card summary-card ${directionClass(direction)}"><span class="summary-icon">${icon}</span><h3>${label}</h3><strong>${esc(direction)}</strong><small>${esc(note)}</small></article>`;
    }).join('');
  }

  function rateBars(){
    const items=[['米10年',4.62,100],['日本10年',1.86,40],['VIX',18.90,41]];
    return `<div class="bars">${items.map(([n,v,w])=>`<div class="bar"><span>${n}</span><div class="track"><div class="fill" style="width:${w}%"></div></div><b>${v}</b></div>`).join('')}</div>`;
  }

  function marketCards(r){
    return arr(r.markets).map((m,i)=>`<article class="card market-card" id="s6-${i}"><div class="market-head"><h3>${esc(m.name)}</h3><span class="chip ${directionClass(m.direction)==='up'?'green':directionClass(m.direction)==='down'?'red':'amber'}">${esc(m.direction)}</span></div><div class="market-price">${esc(m.price||'—')}</div><div class="market-change ${directionClass(m.direction)==='up'?'pos':directionClass(m.direction)==='down'?'neg':''}">${esc(m.change||'')}</div><div class="market-meta"><div><b>見通し</b><span>${esc(m.material||'')}</span></div><div><b>崩れる条件</b><span>${esc(m.breakCondition||r.breakConditions||'')}</span></div></div></article>`).join('');
  }

  function render(r){
    $('#updatedAt').innerHTML=`最終更新：${esc((r.date||'').replaceAll('-','/'))} ${esc(r.time||'')}<br>自動更新：ON`;
    $('#dashboard').innerHTML=`
      <section class="grid top-grid" id="s0">
        <article class="card accent-blue"><h2>今日の相場テーマ</h2><div class="theme-title">${esc(r.theme)}</div><span class="chip blue">結論</span><p>${esc(r.mainScenario)}</p></article>
        <article class="card accent-purple"><h2>根拠3点</h2>${list([...arr(r.news).slice(0,2),...arr(r.consistency).slice(0,1)],3)}</article>
        <article class="card accent-amber"><h2>今日の注目ポイント</h2>${list([r.leadingMarket,...arr(r.positioning).slice(0,2)],3)}</article>
        <article class="card accent-red"><h2>重要イベント</h2>${list(r.events,5)}</article>
      </section>
      <section class="grid summary-grid" id="s1">${marketSummary(r)}</section>
      <section class="grid middle-grid">
        <article class="card" id="s2"><h2>重要ニュース</h2>${list(r.news,5)}</article>
        <article class="card"><h2>前回からの変化</h2>${list(r.changes,4)}</article>
        <article class="card" id="s3"><h2>金利・ボラティリティ</h2>${rateBars()}</article>
        <article class="card" id="s4"><h2>クロスアセット資金フロー</h2><div class="flow"><div class="flow-box out">ハイテク・金・BTCから資金流出</div><div class="arrow">→</div><div class="flow-box in">原油・ドル・大型株の一部へ流入</div><div class="flow-note">${esc(arr(r.crossAssetFlow).map(text).join(' '))}</div></div></article>
        <article class="card" id="s5"><h2>需給・ポジション</h2>${list(r.positioning,5)}</article>
      </section>
      <section class="grid market-grid">${marketCards(r)}</section>
      <section class="grid depth-grid" id="s7">
        <article class="card"><h2>米国セクター</h2>${rows(r.usSectors,true)}</article>
        <article class="card"><h2>東京セクター</h2>${rows(r.japanSectors,true)}</article>
        <article class="card" id="s8"><h2>日経225寄与度</h2><div class="dual"><div><div class="subhead">プラス寄与</div>${rows(r.nikkeiPositiveContributors,true)}</div><div><div class="subhead">マイナス寄与</div>${rows(r.nikkeiNegativeContributors,false)}</div></div></article>
        <article class="card"><h2>米国大幅上昇・下落</h2><div class="dual"><div><div class="subhead">上昇</div>${rows(r.usTopGainers,true)}</div><div><div class="subhead">下落</div>${rows(r.usTopLosers,false)}</div></div></article>
      </section>
      <section class="grid bottom-grid" id="s9">
        <article class="card scenario main"><h2>メインシナリオ</h2><p>${esc(r.mainScenario)}</p></article>
        <article class="card scenario alt"><h2>代替シナリオ</h2><p>${esc(r.alternativeScenario)}</p></article>
        <article class="card scenario break"><h2>崩れる条件</h2><p>${esc(r.breakConditions)}</p></article>
        <article class="card"><h2>次の時間帯への引き継ぎ</h2>${list(r.handover,4)}</article>
        <article class="card" id="s10"><h2>主要リスク</h2>${list([r.breakConditions,...arr(r.positioning).slice(0,2)],3)}</article>
        <article class="card"><h2>重要イベント再確認</h2>${list(r.events,4)}</article>
      </section>
      <div class="footer-note"><span>${esc(r.title||'マーケットレポート')}</span><span>Dashboard V4</span></div>`;
  }

  async function init(){
    renderTabs();
    try { render(await loadReport()); }
    catch (e) { $('#dashboard').innerHTML=`<div class="error">ダッシュボードの描画に失敗しました。${esc(e.message)}</div>`; }
  }

  init();
})();
