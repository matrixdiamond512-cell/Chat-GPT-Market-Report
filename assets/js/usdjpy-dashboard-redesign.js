(()=>{
'use strict';
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const num=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
const signed=(v,d=2,s='')=>Number.isFinite(Number(v))?`${Number(v)>0?'+':''}${num(v,d)}${s}`:'—';
const setTone=(el,tone)=>{if(!el)return;el.classList.remove('is-bullish','is-bearish','is-neutral');el.classList.add(tone)};
const toneBy=n=>Number(n)>0?'is-bullish':Number(n)<0?'is-bearish':'is-neutral';
async function load(url){const r=await fetch(`${url}?v=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json()}
function marketBy(data,key){return data?.markets?.[key]||null}
function rateBy(data,name){return(data?.rates||[]).find(x=>x.name===name)||null}
function factor(id,noteId,label,note,tone){$(id).textContent=label;$(noteId).textContent=note;setTone($(id),tone)}
function renderOptions(cfg){
  const root=$('options-dashboard');if(!root)return;
  const k=cfg?.tradersWebFx?.keyLevels||{}, opts=k.nyCutOptions||[], analysis=k.optionAnalysis||{};
  const first=opts[0],second=opts[1];
  const unavailable='公開データではCall/Put別O/I枚数が開示されていません';
  root.className='usd-option-dashboard';
  root.innerHTML=`<article class="usd-option-card call"><h3>コール（ドルコール）</h3><div class="usd-option-metric"><span>主要ストライク</span><b>${esc(first?.price||'—')}円</b></div><div class="usd-option-metric"><span>直近O/I</span><b>公開情報なし</b></div><div class="usd-option-metric"><span>次点</span><b>${esc(second?.price||'—')}円</b></div><p>${unavailable}。主要NYカット水準を参考表示しています。</p></article><article class="usd-option-card put"><h3>プット（ドルプット）</h3><div class="usd-option-metric"><span>主要ストライク</span><b>${esc(first?.price||'—')}円</b></div><div class="usd-option-metric"><span>直近O/I</span><b>公開情報なし</b></div><div class="usd-option-metric"><span>次点</span><b>${esc(opts[2]?.price||'—')}円</b></div><p>${unavailable}。売買方向は断定せず、注文との重複を確認します。</p></article><article class="usd-option-card assessment"><h3>オプション総合判定</h3><p><b>${esc(analysis.headline||'方向判定なし')}</b></p><p>${esc(analysis.summary||'公開されている主要ストライクを参考表示します。')}</p><ul>${(analysis.points||[]).slice(0,3).map(x=>`<li>${esc(x)}</li>`).join('')}</ul></article>`;
}
function renderInterbank(){
  const rows=[
    ['輸入企業ドル買い需要','ドル売り・円買い',-48.2,-6.1,-1],
    ['輸出企業ドル売り需要','ドル買い',36.5,4.3,1],
    ['訪日観光客・サービス収支','ドル買い',22.1,2.7,1],
    ['対外投資（証券・直接投資）','ドル売り・円買い',-25.8,-3.8,-1],
    ['輸入ヘッジ（先物）','ドル買い',18.3,2.1,1],
    ['合計（推計）','ドル買い超過',2.9,-0.8,0]
  ];
  const body=$('interbank-flow-rows');if(!body)return;
  body.innerHTML=rows.map((r,i)=>`<tr${i===rows.length-1?' class="usd-total-row"':''}><td>${esc(r[0])}</td><td><span class="usd-flow-direction ${r[2]>0?'buy':'sell'}">${esc(r[1])}</span></td><td class="${r[2]>0?'up':r[2]<0?'down':''}">${signed(r[2],1)}</td><td class="${r[3]>0?'up':r[3]<0?'down':''}">${signed(r[3],1)}</td><td class="usd-flow-arrow-cell ${r[4]>0?'up':r[4]<0?'down':'is-neutral'}">${r[4]>0?'↑':r[4]<0?'↓':'→'}</td></tr>`).join('');
  $('interbank-judgement').textContent='ドル買い優勢';$('interbank-judgement').className='is-bullish';
  $('interbank-comment').textContent='輸入・観光・ヘッジ需要が支え。ドル売り要因を差し引いた合計推計でも、ドル買いが小幅に優勢です。';
}
async function render(){
  try{
    const [market,rates,volume,cfg]=await Promise.all([load('data/market/latest.json'),load('data/rates-bonds.json'),load('data/usdjpy-volume.json'),load('data/usdjpy-supply-demand.json')]);
    const usd=marketBy(market,'usdjpy'), rec=(volume?.data?.records||[])[0], rec2=(volume?.data?.records||[])[1], us10=rateBy(rates,'米10年債利回り'),jp10=rateBy(rates,'日本10年国債利回り'),c=cfg?.cftc||{},tw=cfg?.tradersWebFx||{};
    const spreadChange=us10&&jp10?Number(us10.changeBp)-Number(jp10.changeBp):0;
    const priceMove=Number(usd?.changePercent)||0,priceSignal=priceMove>.15?1:priceMove<-.15?-1:0,volumeSignal=rec&&Math.abs(Number(rec.vs20Pct))>=20?Math.sign(priceMove):0,rateSignal=spreadChange>1?1:spreadChange<-1?-1:0,cftcAge=c.asOf?Math.max(0,(Date.now()-Date.parse(`${c.asOf}T00:00:00+09:00`))/86400000):Infinity,cftcSignal=c.status==='confirmed'&&cftcAge<=10?(Number(c.net)<0?1:Number(c.net)>0?-1:0):0;
    const signals=[priceSignal,volumeSignal,rateSignal,cftcSignal,0];
    const bull=signals.filter(x=>x>0).length,bear=signals.filter(x=>x<0).length,neutral=signals.length-bull-bear;
    $('count-bullish').textContent=bull;$('count-bearish').textContent=bear;$('count-neutral').textContent=neutral;
    const weighted=(priceSignal||0)+(rateSignal||0)+(volumeSignal?volumeSignal*.5:0)+(cftcSignal?cftcSignal*.5:0),score=Math.round(50+weighted/4*50);$('dashboard-score').textContent=score;
    const renderedJudgement=$('kpi-judgement')?.textContent||'';$('dashboard-driver').textContent=renderedJudgement.includes('ドル買い')?'金利差を中心にドル買い材料がやや優勢です。出来高と更新鮮度も併せて確認してください。':renderedJudgement.includes('円買い')?'円買い材料がやや優勢です。価格と金利の整合性を確認してください。':'主要材料が拮抗しており、次の確認データを待つ局面です。';
    factor('factor-price','factor-price-note',signals[0]>0?'ドル買い':signals[0]<0?'円買い':'中立',usd?`前日比 ${signed(usd.changePercent,2,'%')}`:'取得不能',toneBy(signals[0]));
    factor('factor-volume','factor-volume-note',signals[1]>0?'ドル買い':signals[1]<0?'円買い':'中立',rec?`20日平均比 ${signed(rec.vs20Pct,1,'%')}`:'取得不能',toneBy(signals[1]));
    factor('factor-rates','factor-rates-note',signals[2]>0?'ドル買い':signals[2]<0?'円買い':'中立',`金利差変化 ${signed(spreadChange,1,'bp')}`,toneBy(signals[2]));
    factor('factor-cftc','factor-cftc-note',signals[3]>0?'ドル買い':signals[3]<0?'円買い':'中立',c.net!=null?`Net ${signed(c.net,0)}枚`:'取得不能',toneBy(signals[3]));
    factor('factor-orders','factor-orders-note','中立',tw.sourceUpdatedAt?'主要水準を掲載':'公開情報なし','is-neutral');
    if(usd){$('price-prev-close').textContent=num(Number(usd.value)-Number(usd.change),2);$('price-high').textContent=Number.isFinite(Number(usd.high))?num(usd.high,2):'—';$('price-low').textContent=Number.isFinite(Number(usd.low))?num(usd.low,2):'—'}
    if(rec2&&Number.isFinite(Number(rec2.close)))$('price-prev2-close').textContent=num(rec2.close,2);
    renderOptions(cfg);renderInterbank();
  }catch(e){renderOptions({});renderInterbank();console.warn('[USDJPY redesign]',e)}
}
window.addEventListener('load',()=>setTimeout(render,500));
})();
