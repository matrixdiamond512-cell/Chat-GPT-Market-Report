const latestReport=document.getElementById("latestReport");
const latestTimestamp=document.getElementById("latestTimestamp");
const reportList=document.getElementById("reportList");
const timeFilter=document.getElementById("timeFilter");
const monthFilter=document.getElementById("monthFilter");
const marketFilter=document.getElementById("marketFilter");
const searchInput=document.getElementById("searchInput");
const resultCount=document.getElementById("resultCount");
const emptyMessage=document.getElementById("emptyMessage");
let reports=[];

function esc(value=""){return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));}
function asArray(value){return Array.isArray(value)?value:(value?[value]:[]);}
function listText(items=[]){const rows=asArray(items);return rows.length?rows.map(x=>`<p>・${esc(typeof x==="string"?x:(x.text||x.summary||JSON.stringify(x)))}</p>`).join(""):"<p>記載なし</p>";}
function directionClass(value=""){
  const text=String(value).toLowerCase();
  if(/[上昇|強気|買い|反発|up|bull]/.test(text))return "up";
  if(/[下落|弱気|売り|反落|down|bear]/.test(text))return "down";
  return "neutral";
}
function formatMonth(value=""){const [y,m]=value.split("-");return `${y}年${Number(m)}月`;}
function optionalPanel(title,content){return content?`<section class="panel"><h4>${esc(title)}</h4>${content}</section>`:"";}
function sourceList(items=[]){
  const rows=asArray(items);
  if(!rows.length)return "";
  return `<section class="sources"><h4>主な情報源</h4><ul>${rows.map(source=>{
    if(typeof source==="string")return `<li>${esc(source)}</li>`;
    const name=esc(source.name||source.title||"情報源");
    const url=source.url?`<a href="${esc(source.url)}" target="_blank" rel="noopener noreferrer">${name}</a>`:name;
    return `<li>${url}${source.note?` — ${esc(source.note)}`:""}</li>`;
  }).join("")}</ul></section>`;
}

function marketCards(item,marketName="all"){
  return asArray(item.markets).filter(m=>marketName==="all"||m.name===marketName).map(m=>`
    <div class="market-item">
      <div class="market-title-row"><h5>${esc(m.name)}</h5><span class="direction ${directionClass(m.direction)}">${esc(m.direction||"方向感なし")}</span></div>
      ${m.price?`<p class="price-line"><strong>${esc(m.price)}</strong>${m.change?` <span>${esc(m.change)}</span>`:""}</p>`:""}
      <p><strong>材料：</strong>${esc(m.material||m.outlook||"記載なし")}</p>
      ${m.positioning?`<p><strong>需給：</strong>${esc(m.positioning)}</p>`:""}
      ${m.levels?`<p><strong>注目水準：</strong>${esc(m.levels)}</p>`:""}
      ${m.mainScenario?`<p><strong>メイン：</strong>${esc(m.mainScenario)}</p>`:""}
      ${m.alternativeScenario?`<p><strong>代替：</strong>${esc(m.alternativeScenario)}</p>`:""}
      <p><strong>崩れる条件：</strong>${esc(m.breakCondition||"記載なし")}</p>
      ${m.risk?`<p><strong>リスク：</strong>${esc(m.risk)}</p>`:""}
    </div>`).join("");
}

function reportCard(item,marketName="all"){
  const markets=marketCards(item,marketName);
  const scenarios=optionalPanel("全体シナリオ",`${item.mainScenario?`<p><strong>メイン：</strong>${esc(item.mainScenario)}</p>`:""}${item.alternativeScenario?`<p><strong>代替：</strong>${esc(item.alternativeScenario)}</p>`:""}${item.breakConditions?`<p><strong>崩れる条件：</strong>${esc(item.breakConditions)}</p>`:""}`);
  const events=optionalPanel("今後のイベント",listText(item.events));
  const sectors=optionalPanel("セクター・業種動向",listText(item.sectors));
  const flows=optionalPanel("クロスアセット資金フロー",listText(item.crossAssetFlow));
  const risk=optionalPanel("リスク管理",listText(item.riskManagement));

  return `<article class="report-card">
    <header class="report-head">
      <h3>${esc(item.title)}</h3>
      <p class="meta">${esc((item.date||"").replaceAll("-","/"))} ${esc(item.time)}｜${esc(asArray(item.tags).join("・"))}</p>
    </header>
    <div class="report-body">
      <div class="theme"><strong>今日の相場テーマ</strong>${esc(item.theme||"記載なし")}</div>
      <div class="section-grid">
        <section class="panel"><h4>前回からの変化</h4>${listText(item.changes)}</section>
        <section class="panel"><h4>材料と値動きの整合性</h4>${listText(item.consistency)}</section>
        <section class="panel"><h4>今日の主導市場</h4><p>${esc(item.leadingMarket||"記載なし")}</p></section>
        <section class="panel"><h4>ポジションの偏り</h4>${listText(item.positioning)}</section>
        <section class="panel"><h4>重要ニュース</h4>${listText(item.news)}</section>
        <section class="panel"><h4>次の時間帯への引き継ぎ</h4>${listText(item.handover)}</section>
        ${flows}${sectors}${events}${scenarios}${risk}
      </div>
      <h4 class="market-heading">個別市場見通し</h4>
      <div class="market-grid">${markets||"<p>該当市場の記載がありません。</p>"}</div>
      ${sourceList(item.sources)}
    </div>
  </article>`;
}

function populateMonths(){
  const months=[...new Set(reports.map(r=>(r.date||"").slice(0,7)).filter(Boolean))].sort().reverse();
  monthFilter.innerHTML='<option value="all">すべて</option>'+months.map(m=>`<option value="${esc(m)}">${esc(formatMonth(m))}</option>`).join("");
}
function filteredReports(){
  const time=timeFilter.value,month=monthFilter.value,market=marketFilter.value,query=searchInput.value.trim().toLowerCase();
  return reports.filter(report=>{
    const hasMarket=market==="all"||asArray(report.markets).some(m=>m.name===market)||asArray(report.tags).includes(market);
    const haystack=JSON.stringify(report).toLowerCase();
    return (time==="all"||report.time===time)&&(month==="all"||(report.date||"").startsWith(month))&&hasMarket&&(!query||haystack.includes(query));
  });
}
function render(){
  const filtered=filteredReports(),market=marketFilter.value;
  reportList.innerHTML=filtered.map(item=>reportCard(item,market)).join("");
  resultCount.textContent=`${filtered.length}件`;
  emptyMessage.hidden=filtered.length!==0;
}
async function init(){
  try{
    const response=await fetch(`reports.json?ts=${Date.now()}`,{cache:"no-store"});
    if(!response.ok)throw new Error("reports.jsonを取得できませんでした。");
    const data=await response.json();
    if(!Array.isArray(data))throw new Error("レポート一覧の形式が正しくありません。");
    reports=data.sort((a,b)=>(`${b.date} ${b.time}`).localeCompare(`${a.date} ${a.time}`));
    populateMonths();
    if(reports[0]){latestReport.innerHTML=reportCard(reports[0]);latestTimestamp.textContent=`最終更新 ${reports[0].date.replaceAll("-","/")} ${reports[0].time}`;}
    else latestReport.innerHTML="<p class='empty'>レポートがありません。</p>";
    render();
  }catch(error){latestReport.innerHTML=`<p class="empty">${esc(error.message)}</p>`;reportList.innerHTML="";resultCount.textContent="0件";}
}
[timeFilter,monthFilter,marketFilter].forEach(element=>element.addEventListener("change",render));
searchInput.addEventListener("input",render);
init();
