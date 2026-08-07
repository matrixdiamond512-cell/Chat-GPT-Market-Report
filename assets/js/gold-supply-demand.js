(function(){
  'use strict';

  const root=document.querySelector('[data-gold-dashboard]');
  if(!root)return;

  const GOLD_URL='data/gold-supply-demand.json';
  const MARKET_URL='data/market/latest.json';
  const MISSING=new Set(['','取得不能','未確認','未連携','データ未連携','判定待ち','算定対象外','未判定','更新失敗']);

  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const raw=v=>v&&typeof v==='object'&&'value'in v?v.value:v;
  const val=(v,f='取得待ち')=>{const x=raw(v);return x===undefined||x===null||x===''?f:String(x)};
  const missing=v=>{const x=val(v,'');return MISSING.has(x)||/取得不能|未連携|未設定|連携後/.test(x)};
  const section=(d,needle)=>(d?.sections||[]).find(s=>(s.title||'').includes(needle));
  const findRow=(sec,key,needle)=>(sec?.rows||[]).find(r=>String(r?.[key]??'').includes(needle));
  const objStatus=v=>v&&typeof v==='object'?v.status:'';
  const statusClass=v=>{const s=objStatus(v);if(s==='unavailable'||s==='stale'||missing(v))return'muted';const x=val(v,'');if(/^\+|上昇|強|買い/.test(x))return'good';if(/^-|下落|弱|売り/.test(x))return'bad';return'warn'};
  const directionClass=n=>Number(n)>0?'up':Number(n)<0?'down':'';
  const fmt=n=>Number.isFinite(Number(n))?Number(n).toLocaleString('en-US',{maximumFractionDigits:2}):'取得待ち';
  const pct=n=>Number.isFinite(Number(n))?`${Number(n)>0?'+':''}${Number(n).toFixed(2)}%`:'取得待ち';
  const fmtTime=iso=>{if(!iso)return'取得待ち';try{const d=new Date(iso);const p=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(d).reduce((a,x)=>(a[x.type]=x.value,a),{});return`${p.year}/${p.month}/${p.day} ${p.hour}:${p.minute} JST`}catch(_){return String(iso)}};
  const fmtDate=iso=>{if(!iso)return'取得待ち';try{const d=new Date(iso);const p=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d).reduce((a,x)=>(a[x.type]=x.value,a),{});return`${p.year}/${p.month}/${p.day}`}catch(_){return String(iso)}};
  const badge=(text,kind='muted')=>`<span class="gold-badge ${kind}">${esc(text)}</span>`;
  const displayValue=(v,f='取得待ち')=>missing(v)?`<span class="gold-missing">${esc(f)}</span>`:`<span class="gold-value ${statusClass(v)==='good'?'up':statusClass(v)==='bad'?'down':''}">${esc(val(v))}</span>`;

  function connectedGoldSection(sec,key){
    if(!sec)return false;
    return (sec.rows||[]).some(r=>Object.values(r).some(v=>!missing(v)&&String(raw(v)||'').trim()!==String(r?.[key]||'').trim()));
  }

  function tableRows(sec,columns){
    if(!sec?.rows?.length)return`<tr><td colspan="${columns.length}" class="gold-missing">取得待ち</td></tr>`;
    return sec.rows.map(row=>`<tr>${columns.map((c,i)=>`<td class="${i>0?'num':''}">${displayValue(row[c])}</td>`).join('')}</tr>`).join('');
  }

  function render(gold,market){
    const mg=market?.markets?.gold||null;
    const usd=market?.markets?.usdjpy||null;
    const marketOk=!!(mg&&mg.verificationStatus==='verified'&&Number.isFinite(Number(mg.value)));
    const usdOk=!!(usd&&usd.verificationStatus==='verified'&&Number.isFinite(Number(usd.value)));

    const etf=section(gold,'金ETF');
    const cftc=section(gold,'CFTC建玉明細');
    const central=section(gold,'中央銀行');
    const physical=section(gold,'物理的需要');
    const matrixSec=section(gold,'価格・建玉');
    const summarySec=section(gold,'主要指標');

    const etfOk=connectedGoldSection(etf,'項目');
    const cftcOk=connectedGoldSection(cftc,'区分');
    const centralOk=connectedGoldSection(central,'項目');
    const physicalOk=connectedGoldSection(physical,'地域・項目');
    const comexOiOk=false;
    const envOk=usdOk;
    const connected=[marketOk,comexOiOk,cftcOk,etfOk,physicalOk,centralOk,envOk].filter(Boolean).length;

    const updatedAt=market?.generatedAt||gold?.updatedAt;
    const asOf=mg?.asOf||gold?.asOfDate;
    document.querySelector('[data-source-status]').textContent=`${connected}/7 ${connected===7?'連携済み':'一部連携'}`;
    document.querySelector('[data-updated]').textContent=fmtTime(updatedAt);
    document.querySelector('[data-as-of]').textContent=fmtDate(asOf);

    const priceLabel=mg?.marketType==='continuous_futures'?'金価格（COMEX先物）':'XAU/USD';
    const price=marketOk?fmt(mg.value):'取得待ち';
    const priceChange=marketOk?pct(mg.changePercent):'取得待ち';
    const priceDir=marketOk?directionClass(mg.changePercent):'';
    const shortLabel=!missing(gold?.overallAssessment?.label)?gold.overallAssessment.label:'判定待ち';
    const shortKind=/買い|強/.test(shortLabel)?'positive':/売り|弱/.test(shortLabel)?'neutral':'neutral';
    const structural=centralOk||physicalOk?'要確認':'判定待ち';
    const scoreRaw=gold?.overallAssessment?.score;
    const scoreNum=Number(String(scoreRaw||'').replace(/[^0-9.\-]/g,''));
    const hasScore=Number.isFinite(scoreNum)&&!missing(scoreRaw);
    const score=hasScore?Math.max(0,Math.min(100,scoreNum)):0;

    const cftcRows=cftc?.rows||[];
    const cLong=findRow(cftc,'区分','ロング');
    const cShort=findRow(cftc,'区分','ショート');
    const cNet=findRow(cftc,'区分','ネット');

    const china=findRow(physical,'地域・項目','中国');
    const india=findRow(physical,'地域・項目','インド');
    const centralRow=findRow(central,'項目','中央銀行');

    const envRows=[
      {name:'米10年実質金利',value:'取得待ち',impact:'低下なら金にプラス',kind:'muted'},
      {name:'DXY（ドル指数）',value:'取得待ち',impact:'低下なら金にプラス',kind:'muted'},
      {name:'FRB政策期待',value:'取得待ち',impact:'利下げ期待上昇は金にプラス',kind:'muted'},
      {name:'地政学・安全資産需要',value:'定量値なし',impact:'高まりは金にプラス',kind:'muted'},
      {name:'USD/JPY',value:usdOk?usd.displayValue||fmt(usd.value):'取得待ち',impact:'円建て金価格への影響を確認',kind:usdOk?'warn':'muted'}
    ];

    const ai=[];
    if(marketOk){
      ai.push(`金価格は${priceDir==='up'?'上昇':'down'===priceDir?'下落':'横ばい'}（${priceChange}）。ただしCOMEX出来高・建玉が未連携のため、新規買い・ショートカバー・ロング清算の判別は保留します。`);
    }else ai.push('金価格の検証済みデータを取得できていません。価格方向の判定は保留します。');
    ai.push(cftcOk?'CFTC投機筋ポジションは取得済みです。ネットポジションと前週比を短期需給判断に使います。':'CFTC Managed Moneyのロング・ショート・ネットポジションは未連携です。週次データ取得後に投機筋の偏りを判定します。');
    ai.push(etfOk?'金ETFフローは取得済みです。先物と同方向なら金融需要の裏付けとして重視します。':'GLD・IAU・世界金ETFの保有量/フローは未連携です。ETF流入の有無が短期需給判断の主要な不足項目です。');
    ai.push(physicalOk?'中国・インドの現物プレミアムを金融市場の値動きと分けて確認します。':'中国・インドの現物プレミアムは未連携です。現物需要主導か金融市場主導かの判定は保留します。');
    ai.push(centralOk?'中央銀行需要は構造的需給として短期データと分離して評価します。':'中央銀行需要は月次データとして別管理します。短期の売買シグナルとは混同しません。');

    root.innerHTML=`
      <section class="gold-overview" aria-label="需給サマリー">
        <article class="gold-card gold-summary-card accent">
          <div class="gold-summary-source">${esc(mg?.sourceName||'市場データ')}</div>
          <div class="gold-summary-label">${esc(priceLabel)}</div>
          <div class="gold-summary-value ${priceDir}">${esc(price)}</div>
          <div class="gold-summary-sub">${marketOk?`前日比 ${esc(priceChange)} / ${esc(mg.unit||'USD/oz')}`:'価格データ取得待ち'}</div>
        </article>
        <article class="gold-card gold-summary-card ${shortKind}">
          <div class="gold-summary-label">短期需給</div>
          <div class="gold-summary-value small ${/買い|強/.test(shortLabel)?'up':/売り|弱/.test(shortLabel)?'down':''}">${esc(shortLabel)}</div>
          <div class="gold-summary-sub">COMEX建玉・CFTC・ETFフローから判定</div>
        </article>
        <article class="gold-card gold-summary-card neutral">
          <div class="gold-summary-label">構造的需給</div>
          <div class="gold-summary-value small">${esc(structural)}</div>
          <div class="gold-summary-sub">中央銀行・中国/インド現物需要・世界需給</div>
        </article>
        <article class="gold-card gold-summary-card accent">
          <div class="gold-summary-label">総合判定（スコア）</div>
          <div class="gold-score-wrap">
            <div>
              <div class="gold-summary-value small">${hasScore?esc(scoreRaw):'—'}</div>
              <div class="gold-summary-sub">${hasScore?'複数需給指標の総合評価':'必要データが揃うまで採点しません'}</div>
            </div>
            <div class="gold-score-ring" style="--score-angle:${score*3.6}deg" aria-label="需給スコア"></div>
          </div>
        </article>
      </section>

      <div class="gold-content-grid">
        <div class="gold-stack">
          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">COMEX先物需給</h2><span class="gold-frequency">日次</span></div>
            <div class="gold-section-body gold-comex-grid">
              <div>
                <div class="gold-note" style="margin:0 0 8px">価格 × 建玉（OI）の組み合わせで、上昇・下落の中身を判定します。</div>
                <div class="gold-matrix-wrap">
                  <div class="gold-matrix-top">建玉（OI）　← 減少　｜　増加 →</div>
                  <div class="gold-matrix-side">価格　上昇 / 下落</div>
                  <div class="gold-matrix">
                    ${(matrixSec?.items?.length?matrixSec.items:[
                      {title:'価格上昇＋建玉減少',note:'ショートカバー中心の可能性'},
                      {title:'価格上昇＋建玉増加',note:'新規ロング流入の可能性'},
                      {title:'価格下落＋建玉減少',note:'ロング清算の可能性'},
                      {title:'価格下落＋建玉増加',note:'新規ショート流入の可能性'}
                    ]).map((x,i)=>`<div class="gold-matrix-cell ${i===1?'good':i===3?'bad':''}"><strong>${esc(x.title)}</strong><span>${esc(x.note)}</span></div>`).join('')}
                  </div>
                </div>
              </div>
              <div>
                <table class="gold-metric-table">
                  <tbody>
                    <tr><th>価格</th><td>${marketOk?`<span class="gold-value ${priceDir}">${esc(price)}</span>`:'<span class="gold-missing">取得待ち</span>'}</td><td>${marketOk?`<span class="gold-value ${priceDir}">${esc(priceChange)}</span>`:''}</td></tr>
                    <tr><th>出来高</th><td colspan="2"><span class="gold-missing">取得待ち</span></td></tr>
                    <tr><th>建玉（OI）</th><td colspan="2"><span class="gold-missing">取得待ち</span></td></tr>
                    <tr><th>建玉前日比</th><td colspan="2"><span class="gold-missing">取得待ち</span></td></tr>
                  </tbody>
                </table>
                <div class="gold-source-line">価格：${esc(mg?.sourceName||'未連携')}。出来高・建玉はCOMEX日次データ連携後に表示。</div>
              </div>
            </div>
          </article>

          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">CFTC投機筋ポジション</h2><span class="gold-frequency">週次</span></div>
            <div class="gold-section-body">
              <div class="gold-cot-strip">
                <div class="gold-cot-cell"><div class="label">区分</div><div class="value">Managed Money</div><div class="sub">CFTC Disaggregated COT</div></div>
                <div class="gold-cot-cell"><div class="label">Long</div><div class="value">${displayValue(cLong?.['枚数'])}</div><div class="sub">${cLong?`前週比 ${esc(val(cLong['前週比']))}`:'取得待ち'}</div></div>
                <div class="gold-cot-cell"><div class="label">Short</div><div class="value">${displayValue(cShort?.['枚数'])}</div><div class="sub">${cShort?`前週比 ${esc(val(cShort['前週比']))}`:'取得待ち'}</div></div>
                <div class="gold-cot-cell"><div class="label">Net</div><div class="value">${displayValue(cNet?.['枚数'])}</div><div class="sub">${cNet?`前週比 ${esc(val(cNet['前週比']))}`:'取得待ち'}</div></div>
                <div class="gold-cot-cell"><div class="label">評価</div><div class="value">${cftcOk?badge('取得済み','good'):badge('連携待ち','muted')}</div><div class="sub">基準日を必ず表示</div></div>
              </div>
            </div>
          </article>

          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">ETF資金フロー</h2><span class="gold-frequency">日次 / 週次</span></div>
            <div class="gold-section-body gold-table-scroll">
              <table class="gold-data-table">
                <thead><tr><th>ETF / 集計</th><th>保有量・値</th><th>変化</th><th>判定</th></tr></thead>
                <tbody>${tableRows(etf,['項目','値','変化','判定'])}</tbody>
              </table>
              <div class="gold-note">GLD・IAUは日次、世界金ETFは公表頻度に合わせて更新し、基準日の違いを混ぜません。</div>
            </div>
          </article>

          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">中国・インド現物需要</h2><span class="gold-frequency">週次</span></div>
            <div class="gold-section-body gold-physical-grid">
              <div class="gold-country">
                <div class="gold-country-head"><div class="gold-country-title">中国プレミアム（上海）</div>${physicalOk?badge('データあり','good'):badge('連携待ち','muted')}</div>
                <div class="gold-country-value">${displayValue(china?.['値'])}</div>
                <div class="gold-note">前回比：${esc(val(china?.['前回比']))}<br>評価：${esc(val(china?.['評価']))}</div>
              </div>
              <div class="gold-country">
                <div class="gold-country-head"><div class="gold-country-title">インドプレミアム</div>${physicalOk?badge('データあり','good'):badge('連携待ち','muted')}</div>
                <div class="gold-country-value">${displayValue(india?.['値'])}</div>
                <div class="gold-note">前回比：${esc(val(india?.['前回比']))}<br>評価：${esc(val(india?.['評価']))}</div>
              </div>
            </div>
          </article>
        </div>

        <aside class="gold-stack">
          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">価格環境</h2><span class="gold-frequency">日次</span></div>
            <div class="gold-section-body gold-env-list">
              ${envRows.map(r=>`<div class="gold-env-row"><div class="gold-env-name">${esc(r.name)}</div><div class="gold-env-value">${esc(r.value)}</div><div class="gold-env-impact ${r.kind==='good'?'up':r.kind==='bad'?'down':''}">${esc(r.impact)}</div></div>`).join('')}
              <div class="gold-note">価格ドライバーと需給データを分けて表示します。USD/JPYはドル建て金の直接需給ではなく、円建て金価格への影響確認用です。</div>
            </div>
          </article>

          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">先物カーブ（COMEX GC）</h2><span class="gold-frequency">日次</span></div>
            <div class="gold-section-body gold-curve">
              <div class="gold-curve-labels"><span>Backwardation</span><span>Flat</span><span>Contango</span></div>
              <div class="gold-curve-line"><span class="gold-curve-marker" style="left:50%;opacity:.35"></span></div>
              <div>${badge('連携待ち','muted')}</div>
              <div class="gold-note">期近・期先価格を取得後、コンタンゴ / フラット / バックワーデーションを判定します。</div>
            </div>
          </article>

          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">中央銀行</h2><span class="gold-frequency">月次</span></div>
            <div class="gold-section-body gold-central">
              <div><div class="gold-summary-label">中央銀行の金購入量</div><div class="gold-note">短期売買ではなく構造的需要として評価</div></div>
              <div class="gold-central-main">${displayValue(centralRow?.['値'])}</div>
            </div>
            <div class="gold-section-body" style="padding-top:0"><div class="gold-note">基準日：${esc(val(centralRow?.['基準日']))}　見方：${esc(val(centralRow?.['見方']))}</div></div>
          </article>

          <article class="gold-card">
            <div class="gold-section-head"><h2 class="gold-section-title">現物需給の更新頻度</h2></div>
            <div class="gold-section-body gold-frequency-list">
              <div class="gold-frequency-row"><b>日次</b><span>金価格 / COMEX出来高・建玉 / GLD・IAU / 価格環境</span></div>
              <div class="gold-frequency-row"><b>週次</b><span>CFTC投機筋 / 中国・インド現物プレミアム / 世界金ETF</span></div>
              <div class="gold-frequency-row"><b>月次</b><span>中央銀行の純購入・公的部門需要</span></div>
              <div class="gold-frequency-row"><b>四半期</b><span>世界の宝飾・地金/金貨・供給・リサイクル等</span></div>
            </div>
          </article>
        </aside>
      </div>

      <article class="gold-card gold-ai">
        <div class="gold-section-head"><h2 class="gold-section-title">AI総合解説</h2><span class="gold-frequency">需給と価格環境を分離</span></div>
        <div class="gold-section-body gold-ai-grid">
          ${ai.map((x,i)=>`<div class="gold-ai-point"><span class="gold-ai-num">${i+1}</span><span>${esc(x)}</span></div>`).join('')}
        </div>
      </article>

      <section class="gold-watchbar" aria-label="このページで見ること">
        <div class="gold-watch-item gold-watch-title">このページで見ること</div>
        <div class="gold-watch-item">誰が買っているか</div>
        <div class="gold-watch-item">短期需給と構造的需給の違い</div>
        <div class="gold-watch-item">価格ドライバーと需給の切り分け</div>
      </section>
    `;
  }

  function fail(err){
    root.innerHTML=`<section class="gold-error"><b>ゴールド需給ページの読み込みに失敗しました。</b><div class="gold-note">${esc(err?.message||err||'不明なエラー')}</div></section>`;
    document.querySelector('[data-source-status]').textContent='更新失敗';
    document.querySelector('[data-updated]').textContent='取得不能';
    document.querySelector('[data-as-of]').textContent='取得不能';
  }

  async function load(){
    try{
      const [g,m]=await Promise.all([
        fetch(GOLD_URL,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`gold JSON HTTP ${r.status}`);return r.json()}),
        fetch(MARKET_URL,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null)
      ]);
      render(g,m);
    }catch(e){fail(e)}
  }

  document.querySelector('[data-reload]')?.addEventListener('click',()=>location.reload());
  load();
})();
