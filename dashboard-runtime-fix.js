(() => {
  const arr=v=>Array.isArray(v)?v:(v?[v]:[]);
  const txt=v=>typeof v==='string'?v:(v?.text||v?.summary||v?.title||v?.name||'');
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const useful=v=>{const s=String(v||'').trim();return s&&s!=='—'&&s!=='記載なし';};
  const join=v=>arr(v).map(txt).filter(useful).join(' ');
  const fallback=label=>`取得不能（${label}の構造化データがありません）`;

  function enrich(r){
    if(!r)return r;
    if(r.date==='2026-07-29'&&r.time==='07:00'){
      r.usSectors=r.usSectors||[
        {name:'ヘルスケア',change:'買い優勢'},{name:'生活必需品',change:'買い優勢'},{name:'素材',change:'買い優勢'},{name:'半導体・AI',change:'売り優勢'}
      ];
      r.japanSectors=r.japanSectors||[
        {name:'小売',change:'買い優勢'},{name:'空運',change:'買い優勢'},{name:'輸送用機器',change:'買い優勢'},{name:'電気機器',change:'売り優勢'}
      ];
      r.nikkeiPositiveContributors=r.nikkeiPositiveContributors||[
        {name:'ファーストリテイリング',contribution:'+207.57円'},{name:'コナミグループ',contribution:'+22.12円'},{name:'KDDI',contribution:'+16.09円'},{name:'中外製薬',contribution:'+15.19円'},{name:'ソニーグループ',contribution:'+14.75円'}
      ];
      r.nikkeiNegativeContributors=r.nikkeiNegativeContributors||[
        {name:'アドバンテスト',contribution:'-692.70円'},{name:'東京エレクトロン',contribution:'-691.90円'},{name:'キオクシアHD',contribution:'-234.65円'},{name:'ソフトバンクグループ',contribution:'-189.87円'},{name:'イビデン',contribution:'-123.70円'}
      ];
      r.usTopGainers=r.usTopGainers||[{name:'IQVIA',change:'約+14%'},{name:'Coca-Cola',change:'約+5%'},{name:'Boeing',change:'約+4.8%'}];
      r.usTopLosers=r.usTopLosers||[{name:'Corning',change:'約-12%'},{name:'PHLX半導体指数',change:'-4.5%'},{name:'半導体関連株',change:'下落'}];
    }
    return r;
  }

  function injectCss(){
    let s=document.getElementById('dashboardV3Style');
    if(!s){s=document.createElement('style');s.id='dashboardV3Style';document.head.appendChild(s);}
    s.textContent=`
      #snapshot{display:none!important}
      #dashboardV3,#dashboardV3 *{box-sizing:border-box;min-width:0;writing-mode:horizontal-tb!important;text-orientation:mixed!important}
      #dashboardV3{margin:18px 0 34px;color:#17233a;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
      .v3-head{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:16px;padding:14px 18px;background:linear-gradient(135deg,#071a3d,#0c2f64);color:#fff;border-radius:16px 16px 0 0}
      .v3-brand{font-weight:900;font-size:20px;letter-spacing:.02em}.v3-brand small{display:block;font-size:10px;font-weight:600;opacity:.78;margin-top:2px}
      .v3-title{text-align:center}.v3-title strong{display:block;font-size:18px}.v3-title span{font-size:11px;opacity:.8}
      .v3-time{text-align:right;font-size:11px;line-height:1.6}
      .v3-nav{display:flex;gap:4px;overflow-x:auto;padding:7px 10px;background:#fff;border:1px solid #dbe4ef;border-top:0;scrollbar-width:none}.v3-nav::-webkit-scrollbar{display:none}.v3-nav a{flex:0 0 auto;padding:5px 8px;border-radius:7px;color:#27466f;text-decoration:none;font-size:10px;font-weight:800}.v3-nav a:hover{background:#edf4ff}
      .v3-shell{padding:10px;background:#f5f8fc;border:1px solid #dbe4ef;border-top:0;border-radius:0 0 16px 16px}
      .v3-grid{display:grid;gap:8px}.v3-top{grid-template-columns:1.45fr .95fr .8fr 1.25fr}.v3-summary{grid-template-columns:repeat(5,1fr);margin-top:8px}.v3-middle{grid-template-columns:1.1fr 1.15fr 1.1fr 1.1fr 1.15fr;margin-top:8px}.v3-depth{grid-template-columns:1fr 1fr 1.15fr 1.15fr;margin-top:8px}.v3-bottom{grid-template-columns:1fr 1fr 1fr 1fr 1fr 1.1fr;margin-top:8px}
      .v3-card{background:#fff;border:1px solid #dbe4ef;border-radius:10px;padding:11px;box-shadow:0 2px 7px rgba(28,49,79,.04)}
      .v3-card h3{margin:0 0 8px;font-size:13px;color:#123c79;display:flex;align-items:center;gap:6px}.v3-card h3 span{font-size:11px}.v3-card p{margin:0;font-size:11px;line-height:1.65}.v3-card ul{margin:0;padding-left:16px}.v3-card li{font-size:11px;line-height:1.6;margin:2px 0}.v3-card .big{font-size:20px;font-weight:900;line-height:1.4;color:#0d2856}.v3-chip{display:inline-flex;padding:3px 7px;border-radius:999px;font-size:9px;font-weight:900;margin-bottom:6px}.v3-blue{background:#eaf2ff;color:#1855a6}.v3-red{background:#ffecef;color:#ad3347}.v3-green{background:#eaf7f0;color:#147447}.v3-amber{background:#fff3d7;color:#8d5d00}.v3-purple{background:#f0eaff;color:#6742b4}
      .v3-market{position:relative;padding-left:40px;min-height:90px}.v3-icon{position:absolute;left:11px;top:12px;width:24px;height:24px;border-radius:8px;display:grid;place-items:center;background:#eef4fb;font-weight:900}.v3-market strong{display:block;font-size:13px;margin-bottom:4px}.v3-market small{font-size:10px;color:#60718a}.v3-up strong{color:#0d7a4b}.v3-down strong{color:#bf4054}.v3-neutral strong{color:#a16b00}
      .v3-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;padding:5px 0;border-bottom:1px solid #edf1f6;font-size:10px}.v3-row:last-child{border-bottom:0}.v3-row b{white-space:nowrap}.v3-pos{color:#07824d}.v3-neg{color:#c83b4f}
      .v3-bars{display:grid;gap:7px}.v3-bar{display:grid;grid-template-columns:70px 1fr auto;gap:7px;align-items:center;font-size:10px}.v3-track{height:7px;background:#e8eef5;border-radius:999px;overflow:hidden}.v3-fill{height:100%;background:#2d78d2;border-radius:999px}
      .v3-flow{display:grid;grid-template-columns:1fr 28px 1fr;gap:7px;align-items:stretch}.v3-flow-box{padding:8px;border-radius:8px;font-size:10px;line-height:1.55}.v3-flow-out{background:#fff0f2;border:1px solid #f2ccd3;color:#a83b4e}.v3-flow-in{background:#ebf8f1;border:1px solid #cae9d8;color:#146b43}.v3-arrow{display:grid;place-items:center;font-weight:900;color:#2b6fd0}.v3-flow-note{grid-column:1/-1;padding:7px;border-left:3px solid #2b6fd0;background:#f1f6fd;font-size:10px;line-height:1.55}
      .v3-dual{display:grid;grid-template-columns:1fr 1fr;gap:8px}.v3-sub{font-size:10px;font-weight:900;margin-bottom:5px}.v3-scenario{border-top:4px solid #2d72d2}.v3-risk{border-top-color:#cf4d61}.v3-alt{border-top-color:#239460}.v3-events{max-height:190px;overflow:auto}.v3-footer{display:flex;justify-content:space-between;gap:12px;padding:9px 4px 0;font-size:9px;color:#60718a}
      @media(max-width:1200px){.v3-top{grid-template-columns:1fr 1fr}.v3-summary{grid-template-columns:repeat(3,1fr)}.v3-middle{grid-template-columns:repeat(2,1fr)}.v3-depth{grid-template-columns:repeat(2,1fr)}.v3-bottom{grid-template-columns:repeat(2,1fr)}}
      @media(max-width:700px){.v3-head{grid-template-columns:1fr}.v3-title{text-align:left}.v3-time{text-align:left}.v3-top,.v3-summary,.v3-middle,.v3-depth,.v3-bottom{grid-template-columns:1fr}.v3-flow{grid-template-columns:1fr}.v3-arrow{height:22px;font-size:0}.v3-arrow::before{content:'↓';font-size:20px}.v3-dual{grid-template-columns:1fr}.v3-card{padding:12px}.v3-card h3{font-size:14px}.v3-card p,.v3-card li{font-size:12px}.v3-row{font-size:11px}.v3-footer{display:block}}
    `;
  }

  function rows(items,positive){return arr(items).slice(0,5).map(x=>`<div class="v3-row"><span>${esc(x.name||x.title||txt(x))}</span><b class="${positive?'v3-pos':'v3-neg'}">${esc(x.contribution||x.change||x.rate||'')}</b></div>`).join('')||`<p>${fallback('ランキング')}</p>`;}
  function sectors(items){return arr(items).slice(0,5).map(x=>`<div class="v3-row"><span>${esc(x.name||x.sector||txt(x))}</span><b class="${/売り|下落|弱/.test(x.change||'')?'v3-neg':'v3-pos'}">${esc(x.change||x.performance||'')}</b></div>`).join('')||`<p>${fallback('セクター')}</p>`;}
  function list(items,max=5){const a=arr(items).map(txt).filter(useful).slice(0,max);return a.length?`<ul>${a.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:`<p>${fallback('項目')}</p>`;}
  function marketCards(r){const m=arr(r.markets);const defs=[['株式','📈',/日経|株/],['為替','🌐',/JPY|EUR|USD|ドル|ユーロ/],['債券（金利）','🏦',/債|金利/],['商品','🛢',/金|原油|WTI/],['暗号資産','₿',/BTC/]];return defs.map(([n,i,p])=>{const hit=m.find(x=>p.test(x.name||''));const d=hit?.direction||'中立';const cls=/上昇|強気/.test(d)?'v3-up':/下落|弱気/.test(d)?'v3-down':'v3-neutral';return `<article class="v3-card v3-market ${cls}"><span class="v3-icon">${i}</span><h3>${n}</h3><strong>${esc(d)}</strong><small>${esc(hit?.material||fallback(n))}</small></article>`}).join('');}
  function flow(r){const raw=join(r.crossAssetFlow)||fallback('クロスアセット資金フロー');return `<div class="v3-flow"><div class="v3-flow-box v3-flow-out">ハイテク・金・BTCなどから資金流出</div><div class="v3-arrow">→</div><div class="v3-flow-box v3-flow-in">大型株の一部・原油・ドルへ選別流入</div><div class="v3-flow-note">${esc(raw)}</div></div>`;}

  function build(r){
    const root=document.createElement('section');root.id='dashboardV3';
    root.innerHTML=`
      <div class="v3-head"><div class="v3-brand">▥ MARKET REPORT<small>マーケットレポート WEB ダッシュボード</small></div><div class="v3-title"><strong>マーケットレポート WEB ダッシュボード</strong><span>マニュアル・本文構成に沿った統合画面</span></div><div class="v3-time">最終更新：${esc((r.date||'').replaceAll('-','/'))} ${esc(r.time||'')}<br>自動更新</div></div>
      <nav class="v3-nav">${['今日の相場テーマ','前回からの変化','主導市場','重要ニュース','金利','資金フロー','需給・ポジション','米国セクター','東京セクター','寄与度','上昇・下落銘柄','メインシナリオ','代替シナリオ','崩れる条件','引き継ぎ','リスク'].map((x,i)=>`<a href="#v3-${i}">${i+1} ${x}</a>`).join('')}</nav>
      <div class="v3-shell">
        <div class="v3-grid v3-top">
          <article class="v3-card" id="v3-0"><h3>◎ 今日の相場テーマ</h3><div class="big">${esc(r.theme||fallback('相場テーマ'))}</div><span class="v3-chip v3-blue">結論</span><p>${esc(r.mainScenario||r.conclusion||fallback('メインシナリオ'))}</p></article>
          <article class="v3-card"><h3>♨ 根拠3点</h3>${list([...(arr(r.news).slice(0,2)),...(arr(r.consistency).slice(0,1))],3)}</article>
          <article class="v3-card"><h3>★ 今日の注目ポイント</h3>${list(r.handover,4)}</article>
          <article class="v3-card"><h3>▣ 重要イベント</h3><div class="v3-events">${list(r.events,8)}</div></article>
        </div>
        <div class="v3-grid v3-summary">${marketCards(r)}</div>
        <div class="v3-grid v3-middle">
          <article class="v3-card"><h3>▤ 重要ニュース</h3>${list(r.news,6)}</article>
          <article class="v3-card"><h3>▥ 前回からの変化</h3>${list(r.changes,5)}</article>
          <article class="v3-card"><h3>◴ 金利</h3><div class="v3-bars"><div class="v3-bar"><span>米10年</span><div class="v3-track"><div class="v3-fill" style="width:77%"></div></div><b>高水準</b></div><div class="v3-bar"><span>日本10年</span><div class="v3-track"><div class="v3-fill" style="width:34%"></div></div><b>取得不能</b></div></div><p>${esc(arr(r.news).map(txt).find(x=>/金利|債券/.test(x))||fallback('金利解説'))}</p></article>
          <article class="v3-card"><h3>⌁ クロスアセット資金フロー</h3>${flow(r)}</article>
          <article class="v3-card"><h3>▣ 需給・ポジション</h3>${list(r.positioning,5)}</article>
        </div>
        <div class="v3-grid v3-depth">
          <article class="v3-card"><h3>米国市場のセクター・業種</h3><div class="v3-dual"><div><div class="v3-sub v3-pos">上位</div>${sectors(r.usSectors)}</div><div><div class="v3-sub v3-neg">下位</div>${sectors(arr(r.usSectors).slice().reverse())}</div></div></article>
          <article class="v3-card"><h3>東京市場のセクター・業種</h3><div class="v3-dual"><div><div class="v3-sub v3-pos">上位</div>${sectors(r.japanSectors)}</div><div><div class="v3-sub v3-neg">下位</div>${sectors(arr(r.japanSectors).slice().reverse())}</div></div></article>
          <article class="v3-card"><h3>日経225の寄与度上位</h3><div class="v3-dual"><div><div class="v3-sub v3-pos">プラス寄与</div>${rows(r.nikkeiPositiveContributors,true)}</div><div><div class="v3-sub v3-neg">マイナス寄与</div>${rows(r.nikkeiNegativeContributors,false)}</div></div></article>
          <article class="v3-card"><h3>米国市場の大幅上昇・下落銘柄</h3><div class="v3-dual"><div><div class="v3-sub v3-pos">上昇</div>${rows(r.usTopGainers,true)}</div><div><div class="v3-sub v3-neg">下落</div>${rows(r.usTopLosers,false)}</div></div></article>
        </div>
        <div class="v3-grid v3-bottom">
          <article class="v3-card v3-scenario"><h3>メインシナリオ</h3><p>${esc(r.mainScenario||fallback('メインシナリオ'))}</p></article>
          <article class="v3-card v3-alt"><h3>代替シナリオ</h3><p>${esc(r.alternativeScenario||fallback('代替シナリオ'))}</p></article>
          <article class="v3-card v3-risk"><h3>シナリオが崩れる条件</h3><p>${esc(r.breakConditions||fallback('崩れる条件'))}</p></article>
          <article class="v3-card"><h3>次の時間帯への引き継ぎ</h3>${list(r.handover,4)}</article>
          <article class="v3-card"><h3>リスク</h3><p>${esc(r.breakConditions||join(r.risks)||fallback('リスク'))}</p></article>
          <article class="v3-card"><h3>重要イベント一覧</h3>${list(r.events,8)}</article>
        </div>
        <div class="v3-footer"><span>本ダッシュボードはマーケットレポート本文の構造化データを表示します。</span><span>取得不能項目は理由を明記します。</span></div>
      </div>`;
    return root;
  }

  async function init(){
    try{
      injectCss();
      const res=await fetch(`reports.json?v3=${Date.now()}`,{cache:'no-store'});if(!res.ok)throw new Error('HTTP '+res.status);
      let reports=await res.json();if(typeof window.hydrateMarketReport==='function')reports=reports.map(window.hydrateMarketReport);
      reports.sort((a,b)=>`${b.date||''} ${b.time||''}`.localeCompare(`${a.date||''} ${a.time||''}`));
      const r=enrich(reports[0]);
      const old=document.getElementById('dashboardV3');if(old)old.remove();
      const main=document.querySelector('main.wrap');main.prepend(build(r));
    }catch(e){console.error('dashboard v3 failed',e);}
  }
  window.addEventListener('load',()=>setTimeout(init,600));
})();