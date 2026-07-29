(() => {
  const root = document.querySelector('.dashboard-card--events');
  const list = document.getElementById('dashboardEvents');
  if (!root || !list || document.getElementById('eventSurpriseSummary')) return;
  const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const num = v => {
    if (v == null || v === '') return null;
    const n = Number(String(v).replace(/,/g,'').replace(/[%$¥€]/g,''));
    return Number.isFinite(n) ? n : null;
  };
  const fmt = (v,u='') => v == null || v === '' ? '—' : `${esc(v)}${esc(u)}`;
  const direction = event => {
    const a=num(event.actual), f=num(event.forecast);
    if (a == null || f == null) return {state:'pending',label:'結果待ち',diff:null};
    const diff=a-f, base=Math.max(Math.abs(f),1e-9), ratio=Math.abs(diff/base);
    const size=ratio>=.1?'大':ratio>=.03?'中':'小';
    if (Math.abs(diff)<1e-12) return {state:'neutral',label:'予想一致',diff:0,size:'小'};
    return {state:diff>0?'positive':'negative',label:`${diff>0?'上振れ':'下振れ'}（${size}）`,diff,size};
  };
  const marketRead = (event,state) => {
    const title=String(event.title||'');
    if (state==='pending'||state==='neutral') return state==='pending'?'発表後に市場反応を確認':'予想通りで、初動は需給や同時刻の材料が主導しやすい';
    const up=state==='positive';
    if (/CPI|PCE|PPI|雇用|失業|賃金|GDP|小売|ISM|PMI/i.test(title)) return up?'米金利・ドル上昇、株・金・BTCには逆風となる可能性':'米金利・ドル低下、株・金・BTCには追い風となる可能性';
    if (/原油|EIA|API|在庫/i.test(title)) return up?'在庫増なら原油に下押し圧力。需要指標の場合は内容を個別確認':'在庫減なら原油に上昇圧力。需要指標の場合は内容を個別確認';
    if (/日銀|日本|東京/i.test(title)) return up?'円金利上昇・円高方向を警戒':'円金利低下・円安方向を警戒';
    return 'イベントの性質により影響方向が異なるため、初動と金利・為替の反応を確認';
  };
  async function init(){
    try{
      const r=await fetch(`economic-calendar.json?surprise=${Date.now()}`,{cache:'no-store'});
      if(!r.ok) return;
      const payload=await r.json();
      const events=Array.isArray(payload?.events)?payload.events:[];
      const now=new Date();
      const dated=events.map(e=>({
        ...e,
        title:e.title||e.event||e.name||'',
        forecast:e.forecast??e.estimate??e.consensus,
        previous:e.previous??e.prev,
        actual:e.actual,
        unit:e.unit||'',
        dt:new Date(e.datetimeJst||`${e.date}T${e.time}:00+09:00`)
      })).filter(e=>e.title && !Number.isNaN(e.dt.getTime())).sort((a,b)=>a.dt-b.dt);
      const completed=dated.filter(e=>e.dt<=now && e.actual!=null && e.actual!=='').slice(-3).reverse();
      const upcoming=dated.find(e=>e.dt>now);
      const panel=document.createElement('section');
      panel.id='eventSurpriseSummary';
      panel.className='event-surprise-summary';
      const completedHtml=completed.length?completed.map(e=>{
        const d=direction(e); const diff=d.diff==null?'—':`${d.diff>0?'+':''}${d.diff.toLocaleString('ja-JP')}${esc(e.unit||'')}`;
        return `<article class="event-surprise-card is-${d.state}"><div class="surprise-head"><strong>${esc(e.title)}</strong><span>${d.label}</span></div><div class="surprise-values"><span>予想<b>${fmt(e.forecast,e.unit)}</b></span><span>結果<b>${fmt(e.actual,e.unit)}</b></span><span>予想差<b>${diff}</b></span></div><p>${esc(marketRead(e,d.state))}</p></article>`;
      }).join(''):'<p class="event-surprise-empty">発表済みで予想と結果がそろったイベントはありません。</p>';
      const nextHtml=upcoming?`<div class="next-event-compact"><span>次の発表</span><strong>${esc(upcoming.time||'')} ${esc(upcoming.title)}</strong><small>予想 ${fmt(upcoming.forecast,upcoming.unit)}｜前回 ${fmt(upcoming.previous,upcoming.unit)}</small></div>`:'';
      panel.innerHTML=`<div class="surprise-title"><div><span class="dashboard-label">発表結果・サプライズ</span><h3>予想との差と市場への意味</h3></div>${nextHtml}</div><div class="event-surprise-grid">${completedHtml}</div>`;
      list.insertAdjacentElement('beforebegin',panel);
    }catch(e){console.warn('Event surprise panel unavailable:',e);}
  }
  init();
})();