(function(){
  const root=document.querySelector('[data-arbitrage]');if(!root)return;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num=v=>Number.isFinite(Number(v))?Number(v).toLocaleString('ja-JP'):'取得不能';
  const latest=(d,key)=>Number.isFinite(Number(d.latest?.[key]))?Number(d.latest[key]):null;
  const change=v=>!Number.isFinite(Number(v))?'<b class="unavailable">取得不能</b>':`<b class="${v<0?'negative':'positive'}">${v>0?'+':''}${num(v)}千株</b>`;
  const weekKey=date=>{const d=new Date(`${date}T00:00:00Z`),m=new Date(d);m.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return m.toISOString().slice(0,10)};
  const weekly=history=>[...new Map((history||[]).filter(x=>x.date).map(x=>[weekKey(x.date),x])).values()];
  function metric(kind,title,icon,value,diff,note){return `<article class="arb-card ${kind}"><div class="kpi-head"><span class="kpi-icon">${icon}</span><div><div class="kpi-title">${title}</div><div class="kpi-value">${value===null?'取得不能':num(value)+'<small>千株</small>'}</div></div></div><div class="change"><span>前回比</span>${change(diff)}</div><div class="signal">● ${esc(note)}</div></article>`}
  function chart(title,history,key,tone){
    const valueFor=row=>key==='net'?Number(row.buyBalance)-Number(row.sellBalance):Number(row[key]);
    const rows=weekly(history).filter(x=>Number.isFinite(valueFor(x))&&Number.isFinite(Number(x.nikkei225Close)));
    if(rows.length<2)return `<article class="chart-card"><h2 class="card-title">${esc(title)}</h2><div class="empty-chart">比較に必要な週次データを取得中です。</div></article>`;
    const values=rows.map(valueFor),deltas=values.map((v,i)=>i?v-values[i-1]:0),prices=rows.map(x=>Number(x.nikkei225Close));
    const left=72,right=1360,top=38,bottom=205,zero=122,span=Math.max(...deltas.map(Math.abs))||1,pMin=Math.min(...prices),pMax=Math.max(...prices),pSpan=pMax-pMin||1;
    const x=i=>left+i*((right-left)/(rows.length-1)),priceY=p=>bottom-(p-pMin)/pSpan*(bottom-top),barWidth=Math.max(5,(right-left)/rows.length*.56);
    const bars=deltas.map((d,i)=>{if(!i)return'';const h=Math.abs(d)/span*72,y=d>=0?zero-h:zero;return `<rect x="${x(i)-barWidth/2}" y="${y}" width="${barWidth}" height="${h}" rx="2" fill="${d>=0?'#078f80':'#df4e52'}"/>`}).join('');
    const ticks=rows.map((row,i)=>`<text class="week-label" x="${x(i)}" y="242" text-anchor="end" transform="rotate(-45 ${x(i)} 242)">${esc(row.date.slice(5).replace('-','/'))}</text>`).join('');
    const line=prices.map((p,i)=>`${x(i)},${priceY(p)}`).join(' '),midPrice=Math.round((pMin+pMax)/2);
    return `<article class="chart-card" style="--chart-tone:${tone}"><h2 class="card-title">${esc(title)}｜過去52週</h2><p class="chart-meta"><span class="legend up">■ 前週比プラス</span><span class="legend down">■ 前週比マイナス</span><span class="legend price">━ 日経225終値（右軸）</span></p><svg class="chart combined-chart" viewBox="0 0 1430 260" role="img" aria-label="${esc(title)}の前週比と日経225終値"><line class="grid" x1="${left}" y1="${top}" x2="${right}" y2="${top}"/><line class="grid" x1="${left}" y1="${zero}" x2="${right}" y2="${zero}"/><line class="axis" x1="${left}" y1="${bottom}" x2="${right}" y2="${bottom}"/><text x="${left}" y="22" text-anchor="start">前週比（千株）</text><text x="${right}" y="22" text-anchor="end">日経225終値（円）</text><text x="${left-8}" y="${top+4}" text-anchor="end">+${num(Math.round(span))}</text><text x="${left-8}" y="${zero+4}" text-anchor="end">0</text><text x="${left-8}" y="${bottom}" text-anchor="end">-${num(Math.round(span))}</text><text x="${right+8}" y="${top+4}">${num(Math.round(pMax))}</text><text x="${right+8}" y="${zero+4}">${num(midPrice)}</text><text x="${right+8}" y="${bottom}">${num(Math.round(pMin))}</text>${bars}<polyline class="price-line" points="${line}"/><circle cx="${x(rows.length-1)}" cy="${priceY(prices.at(-1))}" r="4" fill="#173f7a"/>${ticks}</svg></article>`;
  }
  function addKiyoharaLine(d){
    const card=root.querySelector('.dashboard-grid .chart-card:nth-child(3)');
    const net=Number(d.latest?.buyBalance)-Number(d.latest?.sellBalance);if(!card||!Number.isFinite(net))return;
    const level=net>=1000000?'danger':net>=500000?'warning':'normal';
    const label=level==='danger'?'危険信号（10億株超）':level==='warning'?'注意信号（5億株超）':'平常圏（5億株未満）';
    const position=Math.min(100,net/1000000*100);
    card.classList.add('kiyohara-card');
    card.insertAdjacentHTML('afterbegin',`<section class="kiyohara-line ${level}" aria-label="清原ライン"><div><b>清原ライン（ネット裁定残）</b><span>${num(net)}千株：${label}</span></div><div class="kiyohara-meter"><i class="current" style="left:${position}%"></i><em class="warn">5億株・注意</em><em class="danger">10億株・危険</em></div></section>`);
  }
  function render(d){
    const buy=latest(d,'buyBalance'),sell=latest(d,'sellBalance'),net=buy===null||sell===null?null:buy-sell,buyDiff=latest(d,'buyChange'),sellDiff=latest(d,'sellChange');
    document.querySelector('[data-as-of]').textContent=d.asOfDate||'取得不能';document.querySelector('[data-status]').textContent=d.sourceStatus||'取得不能';
    root.innerHTML=`<section class="mechanism"><p class="lead">裁定取引は、先物と現物の価格差（ベーシス）に着目し、指数の需給に影響を与える取引です。</p><div class="flow"><div class="flow-step"><span class="flow-icon">↗</span><div><strong>日経225先物</strong><small>先物価格の変動</small></div></div><b class="arrow">→</b><div class="flow-step"><span class="flow-icon">⚖</span><div><strong>先物と現物の価格差</strong><small>理論的な差が発生</small></div></div><b class="arrow">→</b><div class="flow-step focus"><span class="flow-icon">⟳</span><div><strong>裁定取引</strong><small>差を埋めるポジションを構築</small></div></div><b class="arrow">→</b><div class="flow-step"><span class="flow-icon">▦</span><div><strong>現物225銘柄</strong><small>機械的な買い・売り</small></div></div><b class="arrow">→</b><div class="flow-step"><span class="flow-icon">▥</span><div><strong>日経225の需給</strong><small>需給と価格形成に作用</small></div></div></div></section><section class="kpi-grid">${metric('buy','裁定買い残','↗',buy,buyDiff,buyDiff<0?'減少し、裁定解消が進行':'残高の積み上がりを確認')}${metric('sell','裁定売り残','↓',sell,sellDiff,sellDiff>0?'直近は増加':'買い戻し余地を確認')}${metric('net','ネット裁定残','⇄',net,buyDiff===null||sellDiff===null?null:buyDiff-sellDiff,'買い圧力の残高を確認')}<article class="arb-card judge"><div class="kpi-head"><span class="kpi-icon">!</span><div><div class="kpi-title">需給判断</div><div class="judge-text">買い残縮小＝裁定解消の可能性</div></div></div><p>現物売り圧力の高まりに注意</p><div class="signal">● 先物・ベーシス・海外投資家と併読</div></article></section><section class="dashboard-grid">${chart('裁定買い残',d.history,'buyBalance','#2865e8')}${chart('裁定売り残',d.history,'sellBalance','#7b43c5')}${chart('ネット裁定残',d.history,'net','#078f80')}</section><aside class="read-card"><h2 class="card-title">このグラフの読み方</h2><ul><li>棒は裁定残の前週比です。青緑は増加、赤は減少を示します。</li><li>薄い紺色の線は日経225終値で、右側の目盛りで読みます。</li><li>残高が減る週と日経225の動きを、同じ横軸で比較できます。</li></ul></aside><p class="source">出典：<a href="${esc(d.sourcePageUrl||'https://www.jpx.co.jp/markets/statistics-equities/program/')}" target="_blank" rel="noopener">JPX 裁定取引の状況</a> ／ 日経225終値：<a href="${esc(d.nikkei225PriceSourceUrl||'https://finance.yahoo.com/quote/%5EN225/history/')}" target="_blank" rel="noopener">${esc(d.nikkei225PriceSourceName||'Yahoo Finance')}</a></p>`;
  }
  fetch('data/nikkei225-arbitrage.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(d=>{render(d);addKiyoharaLine(d)}).catch(()=>render({sourceStatus:'取得不能',latest:{},history:[]}));
})();

