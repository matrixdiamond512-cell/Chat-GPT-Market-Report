(function(){
'use strict';

const DATA_URL='data/gold-supply-demand.json';
const CARD_ATTR='data-gold-supply-summary';
let installing=false;

const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=2)=>n(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=2,suffix='')=>n(v)===null?'取得待ち':`${Number(v)>0?'+':''}${fmt(v,d)}${suffix}`;

function findCardByTitle(title){
  const heads=[...document.querySelectorAll('.gold-section-title')];
  const head=heads.find(el=>el.textContent.trim()===title);
  return head?head.closest('.gold-card'):null;
}

function classifyDirection(value, positiveIsBuy=true, mildThreshold=null){
  if(n(value)===null)return {label:'判定待ち',cls:'neutral'};
  const v=Number(value);
  if(v===0)return {label:'中立',cls:'neutral'};
  const buy=positiveIsBuy?v>0:v<0;
  const mild=mildThreshold!==null&&Math.abs(v)<mildThreshold;
  return {
    label:`${mild?'やや':''}${buy?'買い材料':'売り材料'}`,
    cls:buy?'buy':'sell'
  };
}

function buildCard(data){
  const cot=data.cftc||{};
  const etf=data.etf||{};
  const env=data.environment||{};
  const a=data.assessment||{};
  const gld=etf.gld||{};
  const iau=etf.iau||{};
  const ry=env.realYield10y||{};
  const db=env.dollarBroad||{};

  const cftcClass=classifyDirection(cot.managedMoneyNetChange,true);
  const etfParts=[gld.changeTonnes,iau.changeTonnes].filter(v=>n(v)!==null).map(Number);
  const etfTotal=etfParts.length?etfParts.reduce((s,v)=>s+v,0):null;
  const etfClass=classifyDirection(etfTotal,true,2);
  const ryClass=classifyDirection(ry.change,false);
  const dbClass=classifyDirection(db.change,false);

  const cftcReason=n(cot.managedMoneyNetChange)===null
    ?'CFTCの前週差を取得できていないため判定を保留します。'
    :(Number(cot.managedMoneyNetChange)>0
      ?'投機筋の買い越しが前週から拡大しており、金にはプラスです。'
      :Number(cot.managedMoneyNetChange)<0
        ?'投機筋の買い越しが前週から縮小しており、金にはマイナスです。'
        :'投機筋のネットポジションは前週からほぼ横ばいです。');

  const etfReason=n(etfTotal)===null
    ?'GLD・IAUの前回比が揃っていないため判定を保留します。'
    :(etfTotal>0
      ?'主要金ETFの保有量が合計で増えており、金融需要の流入を示します。'
      :etfTotal<0
        ?'主要金ETFの保有量が合計で減っており、金融需要は小幅流出です。'
        :'主要金ETFの保有量は合計で横ばいです。');

  const ryReason=n(ry.change)===null
    ?'実質金利の前回比を取得できていないため判定を保留します。'
    :(Number(ry.change)>0
      ?'実質金利上昇は、利息を生まない金の相対的な魅力を低下させるため逆風です。'
      :Number(ry.change)<0
        ?'実質金利低下は、利息を生まない金の相対的な魅力を高めるため追い風です。'
        :'実質金利は横ばいで、金への影響は中立です。');

  const dbReason=n(db.change)===null
    ?'米ドル実効指数の前回比を取得できていないため判定を保留します。'
    :(Number(db.change)>0
      ?'ドル高方向はドル建て金価格の重しになりやすく、金には逆風です。'
      :Number(db.change)<0
        ?'ドル安方向はドル建て金価格を支えやすく、金には追い風です。'
        :'米ドル実効指数は横ばいで、金への影響は中立です。');

  return `
  <article class="gold-card gold-supply-summary-card" ${CARD_ATTR}>
    <div class="gold-supply-summary-head">
      <h2>需給サマリ</h2>
      <span>短期需給の内訳</span>
    </div>
    <div class="gold-supply-summary-body">
      <div class="gold-supply-summary-verdict">
        <span>現在の短期需給</span>
        <strong>${esc(a.shortTerm||'判定待ち')}</strong>
      </div>
      <ol class="gold-supply-summary-list">
        <li>
          <div class="gold-supply-summary-line"><b>CFTC</b><em class="${cftcClass.cls}">${esc(cftcClass.label)}</em></div>
          <div class="gold-supply-summary-data">Managed Money Net：<strong>${signed(cot.managedMoneyNet,0,'枚')}</strong> ／ 前週比：<strong>${signed(cot.managedMoneyNetChange,0,'枚')}</strong></div>
          <p>${esc(cftcReason)}</p>
        </li>
        <li>
          <div class="gold-supply-summary-line"><b>ETF</b><em class="${etfClass.cls}">${esc(etfClass.label)}</em></div>
          <div class="gold-supply-summary-data">GLD：<strong>${signed(gld.changeTonnes,2,'t')}</strong> ／ IAU：<strong>${signed(iau.changeTonnes,2,'t')}</strong> ／ 合計：<strong>${n(etfTotal)===null?'取得待ち':signed(etfTotal,2,'t')}</strong></div>
          <p>${esc(etfReason)}</p>
        </li>
        <li>
          <div class="gold-supply-summary-line"><b>米10年実質金利</b><em class="${ryClass.cls}">${esc(ryClass.label)}</em></div>
          <div class="gold-supply-summary-data"><strong>${n(ry.value)===null?'取得待ち':fmt(ry.value,2)+'%'}</strong> ／ 前回比：<strong>${signed(ry.change,2,'pt')}</strong></div>
          <p>${esc(ryReason)}</p>
        </li>
        <li>
          <div class="gold-supply-summary-line"><b>米ドル実効指数</b><em class="${dbClass.cls}">${esc(dbClass.label)}</em></div>
          <div class="gold-supply-summary-data"><strong>${n(db.value)===null?'取得待ち':fmt(db.value,4)}</strong> ／ 前回比：<strong>${signed(db.change,4,'')}</strong></div>
          <p>${esc(dbReason)}</p>
        </li>
      </ol>
      <div class="gold-supply-summary-foot">判定方法：CFTC・ETF・実質金利・ドルを分解して表示。各データの基準日・更新頻度が異なるため、方向だけでなく変化の大きさと鮮度も併せて確認します。</div>
    </div>
  </article>`;
}

async function install(){
  const existing=[...document.querySelectorAll(`[${CARD_ATTR}]`)];
  if(existing.length){
    existing.slice(1).forEach(el=>el.remove());
    return true;
  }
  if(installing)return false;
  const priceCard=findCardByTitle('価格環境');
  if(!priceCard||!priceCard.parentElement)return false;
  installing=true;
  try{
    const r=await fetch(`${DATA_URL}?ts=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    if(!document.querySelector(`[${CARD_ATTR}]`)){
      priceCard.insertAdjacentHTML('beforebegin',buildCard(data));
    }
  }catch(err){
    if(!document.querySelector(`[${CARD_ATTR}]`)){
      priceCard.insertAdjacentHTML('beforebegin',`<article class="gold-card gold-supply-summary-card" ${CARD_ATTR}><div class="gold-supply-summary-head"><h2>需給サマリ</h2><span>短期需給の内訳</span></div><div class="gold-supply-summary-body"><div class="gold-supply-summary-error">需給サマリの読み込みに失敗しました。再読込してください。</div></div></article>`);
    }
  }finally{
    installing=false;
  }
  return true;
}

async function waitForRender(){
  if(await install())return;
  const root=document.querySelector('[data-gold-dashboard]')||document.body;
  const observer=new MutationObserver(async()=>{if(await install())observer.disconnect();});
  observer.observe(root,{childList:true,subtree:true});
  setTimeout(()=>observer.disconnect(),15000);
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{void waitForRender();},{once:true});
else void waitForRender();
})();
