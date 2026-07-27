const MARKET_ENHANCEMENT_ALIASES={
  "USD/JPY":["USD/JPY","USDJPY","ドル円"],
  "EUR/USD":["EUR/USD","EURUSD","ユーロドル"],
  "日経225先物":["日経225先物","日経先物","大阪取引所"],
  "金":["金","ゴールド","Gold","XAUUSD"],
  "原油":["原油","WTI","ブレント","Crude Oil"],
  "BTCUSD":["BTCUSD","BTC/USD","ビットコイン","Bitcoin"]
};
const OUTCOME_HORIZONS=[
  ["nextDay","翌営業日"],
  ["threeDays","3営業日後"],
  ["oneWeek","1週間後"],
  ["oneMonth","1か月後"]
];
function enhancementMarketName(raw=""){
  const decoded=decodeURIComponent(raw).trim();
  const match=Object.entries(MARKET_ENHANCEMENT_ALIASES).find(([,aliases])=>aliases.some(alias=>alias.toLowerCase()===decoded.toLowerCase()));
  return match?.[0]||decoded||"USD/JPY";
}
function enhancementMatchesMarket(market,name){
  const haystack=[market?.name,market?.symbol,market?.ticker].filter(Boolean).join(" ").toLowerCase();
  return (MARKET_ENHANCEMENT_ALIASES[name]||[name]).some(alias=>haystack.includes(alias.toLowerCase()));
}
function isVerifiedMarketRow(report,market){
  const text=[report?.theme,report?.leadingMarket,market?.direction,market?.price,market?.material,market?.outlook].filter(Boolean).join(" ");
  if(/サンプル|表示確認|実データ未掲載|未掲載|取得不能/.test(text))return false;
  return Boolean(market?.price||market?.material||market?.mainScenario||market?.positioning);
}
function buildQualityPanel(total,verified){
  if(document.querySelector(".data-quality-panel"))return;
  const panel=document.createElement("section");
  panel.className="data-quality-panel";
  const rate=total?Math.round(verified/total*100):0;
  const status=verified===0?"検証可能データなし":verified<total?"一部検証可能":"検証可能";
  panel.innerHTML=`
    <div>
      <span class="dashboard-label">DATA QUALITY</span>
      <strong>${status}</strong>
      <p>市場別レポート ${total}件のうち、価格・材料・シナリオのいずれかを確認できるものは ${verified}件です。</p>
    </div>
    <div class="quality-meter" aria-label="検証可能データ比率 ${rate}%">
      <span style="width:${rate}%"></span>
      <b>${rate}%</b>
    </div>`;
  document.querySelector(".market-summary-grid")?.before(panel);
}
function addMarketUtilities(){
  const header=document.querySelector(".market-page-header .wrap");
  if(!header||document.querySelector(".market-utility-bar"))return;
  const bar=document.createElement("div");
  bar.className="market-utility-bar";
  bar.innerHTML=`<button type="button" id="copyMarketUrl">この分析ページのURLをコピー</button><span id="copyMarketStatus" aria-live="polite"></span>`;
  header.appendChild(bar);
  bar.querySelector("button")?.addEventListener("click",async()=>{
    const status=bar.querySelector("#copyMarketStatus");
    try{await navigator.clipboard.writeText(location.href);status.textContent="コピーしました";}
    catch{status.textContent="コピーできませんでした";}
    setTimeout(()=>status.textContent="",2200);
  });
}
function restoreSearchFromUrl(){
  const params=new URLSearchParams(location.search),query=params.get("q");
  if(!query)return;
  const input=document.getElementById("marketSearchInput"),form=document.getElementById("marketSearchForm");
  if(!input||!form)return;
  input.value=query;
  setTimeout(()=>form.requestSubmit(),350);
}
function normalizeOutcome(value){
  if(!value)return null;
  if(typeof value==="string")return {result:value};
  return value;
}
function outcomeClass(result=""){
  if(/◎|的中|hit/i.test(result))return "hit";
  if(/○|一部|partial/i.test(result))return "partial";
  if(/×|不的中|外れ|miss/i.test(result))return "miss";
  return "pending";
}
function outcomeLabel(result=""){
  const cls=outcomeClass(result);
  return cls==="hit"?"◎ 的中":cls==="partial"?"○ 一部的中":cls==="miss"?"× 不的中":"判定待ち";
}
function latestOutcomeRow(rows){
  return rows.find(({market})=>market?.outcomes&&typeof market.outcomes==="object")||rows[0]||null;
}
function buildOutcomeReview(rows){
  if(document.querySelector(".outcome-review-panel"))return;
  const panel=document.createElement("section");
  panel.className="outcome-review-panel";
  const row=latestOutcomeRow(rows);
  const outcomes=row?.market?.outcomes||{};
  const available=OUTCOME_HORIZONS.filter(([key])=>normalizeOutcome(outcomes[key])).length;
  const reportDate=row?.report?.date?.replaceAll("-","/")||"—";
  panel.innerHTML=`
    <div class="outcome-review-head">
      <div><span class="dashboard-label">PRICE OUTCOME REVIEW</span><h2>実価格によるシナリオ検証</h2></div>
      <span class="outcome-review-status">対象レポート：${reportDate} ${row?.report?.time||""}</span>
    </div>
    <div class="outcome-grid">
      ${OUTCOME_HORIZONS.map(([key,label])=>{
        const item=normalizeOutcome(outcomes[key]);
        const cls=outcomeClass(item?.result);
        const price=item?.price||"—";
        const change=item?.change||item?.return||"価格データ待ち";
        return `<article class="outcome-card ${cls}"><span>${label}</span><strong>${outcomeLabel(item?.result)}</strong><small>${price}${price!=="—"?` ｜ ${change}`:` ｜ ${change}`}</small></article>`;
      }).join("")}
    </div>
    <p class="outcome-note">${available?`${available}期間の実績データを表示しています。判定は reports.json の outcomes に記録された確認済みデータだけを使用します。`:"現在の reports.json には将来価格の確認済みデータがありません。数値を推測せず、4期間とも判定待ちとして表示しています。"}</p>`;
  document.querySelector(".market-kpi-grid")?.after(panel);
}
async function initMarketEnhancements(){
  addMarketUtilities();
  restoreSearchFromUrl();
  try{
    const params=new URLSearchParams(location.search),name=enhancementMarketName(params.get("market")||params.get("name")||"");
    const response=await fetch(`reports.json?quality=${Date.now()}`,{cache:"no-store"});
    if(!response.ok)return;
    const reports=await response.json();
    if(!Array.isArray(reports))return;
    const rows=reports.flatMap(report=>(Array.isArray(report.markets)?report.markets:[]).filter(market=>enhancementMatchesMarket(market,name)).map(market=>({report,market}))).sort((a,b)=>`${b.report.date||""} ${b.report.time||""}`.localeCompare(`${a.report.date||""} ${a.report.time||""}`));
    buildQualityPanel(rows.length,rows.filter(({report,market})=>isVerifiedMarketRow(report,market)).length);
    buildOutcomeReview(rows);
  }catch(error){console.warn("Market enhancements could not be built",error);}
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",initMarketEnhancements);else initMarketEnhancements();
