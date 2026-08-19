(function(){
'use strict';

const DATA_URL='data/gold-supply-demand.json';
const CARD_ATTR='data-gold-supply-summary';
const CONTRACT_OZ=100;
const OZ_PER_TONNE=32150.7466;
let installing=false;

const n=v=>{const x=Number(v);return Number.isFinite(x)?x:null};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=2)=>n(v)===null?'取得待ち':Number(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=2,suffix='')=>n(v)===null?'取得待ち':`${Number(v)>0?'+':''}${fmt(v,d)}${suffix}`;
const dateText=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得待ち';
const sameDate=(a,b)=>Boolean(a&&b&&String(a).slice(0,10)===String(b).slice(0,10));

function findCardByTitle(title){
  const heads=[...document.querySelectorAll('.gold-section-title')];
  const head=heads.find(el=>el.textContent.trim()===title);
  return head?head.closest('.gold-card'):null;
}

function classifyDirection(value,positiveIsBuy=true,mildThreshold=null){
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

function classifyFlow(value,mildThreshold=null){
  if(n(value)===null)return {label:'判定待ち',cls:'neutral'};
  const v=Number(value);
  if(v===0)return {label:'横ばい',cls:'neutral'};
  const mild=mildThreshold!==null&&Math.abs(v)<mildThreshold;
  return {
    label:`${mild?'小幅':''}${v>0?'流入':'流出'}`,
    cls:v>0?'buy':'sell'
  };
}

function priceDiscoveryVerdict(cotChange,realYieldChange,dollarChange){
  const signals=[];
  if(n(cotChange)!==null&&Number(cotChange)!==0)signals.push(Math.sign(Number(cotChange)));
  if(n(realYieldChange)!==null&&Number(realYieldChange)!==0)signals.push(Math.sign(-Number(realYieldChange)));
  if(n(dollarChange)!==null&&Number(dollarChange)!==0)signals.push(Math.sign(-Number(dollarChange)));
  if(!signals.length)return {label:'判定待ち',cls:'neutral',detail:'CFTC・実質金利・ドルの確認済み変化が揃うまで判定を保留します。'};
  const score=signals.reduce((a,x)=>a+x,0)/signals.length;
  if(score>=0.5)return {label:'買い優勢',cls:'buy',detail:'CFTC・実質金利・ドルの確認済み項目では、短期の価格発見環境は買い方向が優勢です。'};
  if(score<=-0.5)return {label:'売り優勢',cls:'sell',detail:'CFTC・実質金利・ドルの確認済み項目では、短期の価格発見環境は売り方向が優勢です。'};
  return {label:'強弱混在',cls:'neutral',detail:'CFTC・実質金利・ドルの方向が揃っておらず、短期の価格発見環境は強弱混在です。'};
}

function buildCard(data){
  const cot=data.cftc||{};
  const etf=data.etf||{};
  const env=data.environment||{};
  const gld=etf.gld||{};
  const iau=etf.iau||{};
  const ry=env.realYield10y||{};
  const db=env.dollarBroad||{};

  const cftcClass=classifyDirection(cot.managedMoneyNetChange,true);
  const etfAligned=sameDate(gld.asOfDate,iau.asOfDate);
  const etfTotal=etfAligned&&n(gld.changeTonnes)!==null&&n(iau.changeTonnes)!==null
    ?Number(gld.changeTonnes)+Number(iau.changeTonnes)
    :null;
  const etfClass=classifyFlow(etfTotal,2);
  const ryClass=classifyDirection(ry.change,false);
  const dbClass=classifyDirection(db.change,false);
  const discovery=priceDiscoveryVerdict(cot.managedMoneyNetChange,ry.change,db.change);
  const cftcTonnes=n(cot.managedMoneyNetChange)===null?null:Number(cot.managedMoneyNetChange)*CONTRACT_OZ/OZ_PER_TONNE;

  const cftcReason=n(cot.managedMoneyNetChange)===null
    ?'CFTCの前週差を取得できていないため判定を保留します。'
    :(Number(cot.managedMoneyNetChange)>0
      ?'Managed Moneyのネットロングが前週から拡大しており、短期の価格発見側では買い圧力の増加を示します。'
      :Number(cot.managedMoneyNetChange)<0
        ?'Managed Moneyのネットロングが前週から縮小しており、短期の価格発見側では買い圧力の低下を示します。'
        :'Managed Moneyのネットポジションは前週からほぼ横ばいです。');

  const etfReason=!etfAligned
    ?`GLD（${dateText(gld.asOfDate)}）とIAU（${dateText(iau.asOfDate)}）の基準日が一致しないため、日次合計と方向判定を保留します。ETFは価格を直接動かした主体の判定ではなく、持続需給の確認に使います。`
    :n(etfTotal)===null
      ?'GLD・IAUの前回比が揃っていないため判定を保留します。ETFは持続需給の確認指標として扱います。'
      :(etfTotal>0
        ?'同一基準日のGLD・IAU保有量が合計で増加しています。金融需要の流入を示しますが、その日の価格をETFが直接動かしたことを意味するわけではありません。'
        :etfTotal<0
          ?'同一基準日のGLD・IAU保有量が合計で減少しています。金融需要の流出を示しますが、その日の価格下落をETFだけで説明するものではありません。'
          :'同一基準日のGLD・IAU保有量は合計で横ばいです。ETFは持続需給の確認材料として扱います。');

  const ryReason=n(ry.change)===null
    ?'実質金利の前回比を取得できていないため判定を保留します。'
    :(Number(ry.change)>0
      ?'実質金利上昇は、利息を生まない金の相対的な魅力を低下させるため、短期の価格環境では逆風です。'
      :Number(ry.change)<0
        ?'実質金利低下は、利息を生まない金の相対的な魅力を高めるため、短期の価格環境では追い風です。'
        :'実質金利は横ばいで、短期の価格環境への影響は中立です。');

  const dbReason=n(db.change)===null
    ?'米ドル実効指数の前回比を取得できていないため判定を保留します。'
    :(Number(db.change)>0
      ?'ドル高方向はドル建て金価格の重しになりやすく、短期の価格環境では逆風です。'
      :Number(db.change)<0
        ?'ドル安方向はドル建て金価格を支えやすく、短期の価格環境では追い風です。'
        :'米ドル実効指数は横ばいで、短期の価格環境への影響は中立です。');

  return `
  <article class="gold-card gold-supply-summary-card" ${CARD_ATTR}>
    <div class="gold-supply-summary-head">
      <h2>需給サマリ</h2>
      <span>価格発見と持続需給を分けて確認</span>
    </div>
    <div class="gold-supply-summary-body">
      <div class="gold-supply-summary-verdict">
        <span>短期の価格発見環境</span>
        <strong class="${discovery.cls}">${esc(discovery.label)}</strong>
        <p>${esc(discovery.detail)}</p>
      </div>
      <ol class="gold-supply-summary-list">
        <li>
          <div class="gold-supply-summary-line"><b>CFTC（価格発見）</b><em class="${cftcClass.cls}">${esc(cftcClass.label)}</em></div>
          <div class="gold-supply-summary-data">Managed Money Net：<strong>${signed(cot.managedMoneyNet,0,'枚')}</strong> ／ 前週比：<strong>${signed(cot.managedMoneyNetChange,0,'枚')}</strong>${n(cftcTonnes)===null?'':` ／ 金換算：<strong>${signed(cftcTonnes,1,'t相当')}</strong>`}</div>
          <p>${esc(cftcReason)}</p>
        </li>
        <li>
          <div class="gold-supply-summary-line"><b>ETF（持続需給）</b><em class="${etfClass.cls}">${esc(etfClass.label)}</em></div>
          <div class="gold-supply-summary-data">GLD：<strong>${signed(gld.changeTonnes,2,'t')}</strong>（${dateText(gld.asOfDate)}） ／ IAU：<strong>${signed(iau.changeTonnes,2,'t')}</strong>（${dateText(iau.asOfDate)}） ／ 日次合計：<strong>${n(etfTotal)===null?'算出保留':signed(etfTotal,2,'t')}</strong></div>
          <p>${esc(etfReason)}</p>
        </li>
        <li>
          <div class="gold-supply-summary-line"><b>米10年実質金利（価格環境）</b><em class="${ryClass.cls}">${esc(ryClass.label)}</em></div>
          <div class="gold-supply-summary-data"><strong>${n(ry.value)===null?'取得待ち':fmt(ry.value,2)+'%'}</strong> ／ 前回比：<strong>${signed(ry.change,2,'pt')}</strong></div>
          <p>${esc(ryReason)}</p>
        </li>
        <li>
          <div class="gold-supply-summary-line"><b>米ドル実効指数（価格環境）</b><em class="${dbClass.cls}">${esc(dbClass.label)}</em></div>
          <div class="gold-supply-summary-data"><strong>${n(db.value)===null?'取得待ち':fmt(db.value,4)}</strong> ／ 前回比：<strong>${signed(db.change,4,'')}</strong></div>
          <p>${esc(dbReason)}</p>
        </li>
      </ol>
      <div class="gold-supply-summary-foot">見方：CFTC・実質金利・ドルは短期の価格発見環境、ETFは持続需給の確認材料として分けて表示します。ETFの日次合計はGLDとIAUの基準日が一致した場合のみ算出します。更新頻度が異なるため、ETF流入・流出をその日の価格変動の直接原因とは扱いません。</div>
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
      priceCard.insertAdjacentHTML('beforebegin',`<article class="gold-card gold-supply-summary-card" ${CARD_ATTR}><div class="gold-supply-summary-head"><h2>需給サマリ</h2><span>価格発見と持続需給を分けて確認</span></div><div class="gold-supply-summary-body"><div class="gold-supply-summary-error">需給サマリの読み込みに失敗しました。再読込してください。</div></div></article>`);
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
