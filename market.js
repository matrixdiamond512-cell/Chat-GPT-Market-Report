const marketPageTitle=document.getElementById("marketPageTitle");
const marketPageLead=document.getElementById("marketPageLead");
const marketReportCount=document.getElementById("marketReportCount");
const marketLatestDirection=document.getElementById("marketLatestDirection");
const marketTopTheme=document.getElementById("marketTopTheme");
const marketLatestDate=document.getElementById("marketLatestDate");
const directionHistory=document.getElementById("directionHistory");
const marketThemeRanking=document.getElementById("marketThemeRanking");
const marketArchive=document.getElementById("marketArchive");
const marketArchiveCount=document.getElementById("marketArchiveCount");
const marketEmpty=document.getElementById("marketEmpty");

const MARKET_ALIASES={
  "USD/JPY":["USD/JPY","USDJPY","ドル円"],
  "EUR/USD":["EUR/USD","EURUSD","ユーロドル"],
  "日経225先物":["日経225先物","日経先物","大阪取引所"],
  "金":["金","ゴールド","Gold","XAUUSD"],
  "原油":["原油","WTI","ブレント","Crude Oil"],
  "BTCUSD":["BTCUSD","BTC/USD","ビットコイン","Bitcoin"]
};

const THEMES=[
  ["米金利",["米金利","米長期金利","米10年債","国債利回り"]],
  ["金融政策",["FRB","FOMC","日銀","ECB","利上げ","利下げ"]],
  ["インフレ",["インフレ","CPI","PCE","物価","期待インフレ"]],
  ["地政学",["地政学","中東","ホルムズ","制裁","戦争","紛争"]],
  ["実需・需給",["実需","需給","ポジション","フロー","買い戻し","ショートカバー"]],
  ["オプション・先物",["オプション","SQ","MSQ","ガンマ","先物建玉"]],
  ["AI・半導体",["AI","半導体","NASDAQ","NVIDIA","エヌビディア"]],
  ["原油・エネルギー",["原油","WTI","ブレント","OPEC","エネルギー"]],
  ["暗号資産",["BTC","ビットコイン","暗号資産","ETF資金"]],
  ["リスク選好",["リスクオン","リスクオフ","安全資産","安全逃避"]]
];

function esc(value=""){return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));}
function asArray(value){return Array.isArray(value)?value:(value?[value]:[]);}
function textOf(value){return typeof value==="string"?value:(value?.text||value?.summary||value?.title||"");}
function directionClass(value=""){
  const text=String(value).toLowerCase();
  if(/[上昇|強気|買い|反発|up|bull]/.test(text))return "up";
  if(/[下落|弱気|売り|反落|down|bear]/.test(text))return "down";
  return "neutral";
}
function normalizeMarketName(raw){
  const decoded=decodeURIComponent(raw||"").trim();
  const found=Object.entries(MARKET_ALIASES).find(([,aliases])=>aliases.some(alias=>alias.toLowerCase()===decoded.toLowerCase()));
  return found?found[0]:decoded||"USD/JPY";
}
function matchesMarket(market,name){
  const aliases=MARKET_ALIASES[name]||[name];
  const haystack=[market?.name,market?.symbol,market?.ticker].filter(Boolean).join(" ").toLowerCase();
  return aliases.some(alias=>haystack.includes(alias.toLowerCase()));
}
function findMarket(report,name){return asArray(report.markets).find(m=>matchesMarket(m,name));}
function reportText(report,market){
  return [report.theme,report.leadingMarket,...asArray(report.tags),...asArray(report.news),...asArray(report.crossAssetFlow),...asArray(report.positioning),market?.material,market?.positioning,market?.mainScenario,market?.alternativeScenario,market?.risk].map(textOf).join(" ").toLowerCase();
}
function themeCounts(rows){
  const counts=new Map();
  rows.forEach(({report,market})=>{
    const text=reportText(report,market);
    THEMES.forEach(([label,keywords])=>{
      if(keywords.some(keyword=>text.includes(keyword.toLowerCase())))counts.set(label,(counts.get(label)||0)+1);
    });
  });
  return [...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0],"ja"));
}
function renderStats(rows,marketName){
  const latest=rows[0];
  const ranking=themeCounts(rows);
  marketPageTitle.textContent=`${marketName}｜市場別分析`;
  marketPageLead.textContent=`${marketName}に関する過去レポートを横断し、方向感、材料、需給、シナリオの変化を確認します。`;
  document.title=`${marketName}｜市場別分析｜マーケットレポート`;
  marketReportCount.textContent=`${rows.length}件`;
  marketLatestDirection.innerHTML=latest?`<span class="direction ${directionClass(latest.market.direction)}">${esc(latest.market.direction||"中立")}</span>`:"—";
  marketTopTheme.textContent=ranking[0]?.[0]||"集計対象なし";
  marketLatestDate.textContent=latest?`${latest.report.date.replaceAll("-","/")} ${latest.report.time||""}`:"—";
}
function renderDirectionHistory(rows){
  const recent=rows.slice(0,12).reverse();
  directionHistory.innerHTML=recent.length?recent.map(({report,market})=>`
    <div class="history-item">
      <span class="history-date">${esc((report.date||"").slice(5).replace("-","/"))}<small>${esc(report.time||"")}</small></span>
      <span class="history-line"></span>
      <span class="direction ${directionClass(market.direction)}">${esc(market.direction||"中立")}</span>
    </div>`).join(""):"<p class='empty compact-empty'>履歴がありません。</p>";
}
function renderThemeRanking(rows){
  const ranking=themeCounts(rows).slice(0,8);
  const max=ranking[0]?.[1]||1;
  marketThemeRanking.innerHTML=ranking.length?ranking.map(([label,count],index)=>`
    <div class="ranking-row">
      <span class="ranking-number">${index+1}</span>
      <div class="ranking-main">
        <div class="ranking-label"><strong>${esc(label)}</strong><span>${count}回</span></div>
        <div class="ranking-bar"><span style="width:${Math.max(8,count/max*100)}%"></span></div>
      </div>
    </div>`).join(""):"<p class='empty compact-empty'>集計できる材料がありません。</p>";
}
function renderArchive(rows,marketName){
  marketArchiveCount.textContent=`${rows.length}件`;
  marketEmpty.hidden=rows.length!==0;
  marketArchive.innerHTML=rows.map(({report,market})=>`
    <article class="market-archive-card">
      <header>
        <div>
          <p class="archive-date">${esc((report.date||"").replaceAll("-","/"))} ${esc(report.time||"")}</p>
          <h3>${esc(report.title||`${marketName}見通し`)}</h3>
        </div>
        <span class="direction ${directionClass(market.direction)}">${esc(market.direction||"中立")}</span>
      </header>
      ${market.price?`<p class="archive-price"><strong>${esc(market.price)}</strong>${market.change?` <span>${esc(market.change)}</span>`:""}</p>`:""}
      <div class="archive-grid">
        <section><h4>材料</h4><p>${esc(market.material||market.outlook||"記載なし")}</p></section>
        <section><h4>需給・ポジション</h4><p>${esc(market.positioning||"記載なし")}</p></section>
        <section><h4>メインシナリオ</h4><p>${esc(market.mainScenario||"記載なし")}</p></section>
        <section><h4>崩れる条件</h4><p>${esc(market.breakCondition||"記載なし")}</p></section>
      </div>
      ${market.alternativeScenario?`<p class="archive-alt"><strong>代替シナリオ：</strong>${esc(market.alternativeScenario)}</p>`:""}
      ${market.risk?`<p class="archive-risk"><strong>リスク：</strong>${esc(market.risk)}</p>`:""}
      <p class="archive-theme"><strong>全体テーマ：</strong>${esc(report.theme||"記載なし")}</p>
    </article>`).join("");
}
async function init(){
  const params=new URLSearchParams(location.search);
  const marketName=normalizeMarketName(params.get("name")||params.get("market"));
  try{
    const response=await fetch(`reports.json?ts=${Date.now()}`,{cache:"no-store"});
    if(!response.ok)throw new Error("reports.jsonを取得できませんでした。");
    const data=await response.json();
    if(!Array.isArray(data))throw new Error("レポート一覧の形式が正しくありません。");
    const rows=data.filter(report=>/^\d{4}-\d{2}-\d{2}$/.test(report.date||"")).map(report=>({report,market:findMarket(report,marketName)})).filter(row=>row.market).sort((a,b)=>(`${b.report.date} ${b.report.time}`).localeCompare(`${a.report.date} ${a.report.time}`));
    renderStats(rows,marketName);
    renderDirectionHistory(rows);
    renderThemeRanking(rows);
    renderArchive(rows,marketName);
  }catch(error){
    marketPageTitle.textContent="市場別分析を表示できません";
    marketPageLead.textContent=error.message;
    marketArchive.innerHTML=`<p class="empty">${esc(error.message)}</p>`;
    marketEmpty.hidden=true;
  }
}

init();
