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
function listText(items=[]){return items.length?items.map(x=>`<p>・${esc(x)}</p>`).join(""):"<p>記載なし</p>";}
function directionClass(value=""){
  const text=String(value).toLowerCase();
  if(/[上昇|強気|買い|反発|up|bull]/.test(text))return "up";
  if(/[下落|弱気|売り|反落|down|bear]/.test(text))return "down";
  return "neutral";
}
function formatMonth(value=""){const [y,m]=value.split("-");return `${y}年${Number(m)}月`;}

function reportCard(item,marketName="all"){
  const selectedMarkets=(item.markets||[]).filter(m=>marketName==="all"||m.name===marketName);
  const markets=selectedMarkets.map(m=>`
    <div class="market-item">
      <h5>${esc(m.name)}</h5>
      <p><span class="direction ${directionClass(m.direction)}">${esc(m.direction||"方向感なし")}</span></p>
      <p>${esc(m.outlook||"見通しの記載なし")}</p>
      <p><strong>崩れる条件：</strong>${esc(m.breakCondition||"記載なし")}</p>
    </div>`).join("");

  return `<article class="report-card">
    <header class="report-head">
      <h3>${esc(item.title)}</h3>
      <p class="meta">${esc((item.date||"").replaceAll("-","/"))} ${esc(item.time)}｜${esc((item.tags||[]).join("・"))}</p>
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
      </div>
      <div class="market-grid">${markets||"<p>該当市場の記載がありません。</p>"}</div>
    </div>
  </article>`;
}

function populateMonths(){
  const months=[...new Set(reports.map(r=>(r.date||"").slice(0,7)).filter(Boolean))].sort().reverse();
  monthFilter.innerHTML='<option value="all">すべて</option>'+months.map(m=>`<option value="${esc(m)}">${esc(formatMonth(m))}</option>`).join("");
}

function filteredReports(){
  const time=timeFilter.value;
  const month=monthFilter.value;
  const market=marketFilter.value;
  const query=searchInput.value.trim().toLowerCase();
  return reports.filter(report=>{
    const hasMarket=market==="all"||(report.markets||[]).some(m=>m.name===market)||(report.tags||[]).includes(market);
    const haystack=JSON.stringify(report).toLowerCase();
    return (time==="all"||report.time===time)
      &&(month==="all"||(report.date||"").startsWith(month))
      &&hasMarket
      &&(!query||haystack.includes(query));
  });
}

function render(){
  const filtered=filteredReports();
  const market=marketFilter.value;
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
    if(reports[0]){
      latestReport.innerHTML=reportCard(reports[0]);
      latestTimestamp.textContent=`最終更新 ${reports[0].date.replaceAll("-","/")} ${reports[0].time}`;
    }else{
      latestReport.innerHTML="<p class='empty'>レポートがありません。</p>";
    }
    render();
  }catch(error){
    latestReport.innerHTML=`<p class="empty">${esc(error.message)}</p>`;
    reportList.innerHTML="";
    resultCount.textContent="0件";
  }
}

[timeFilter,monthFilter,marketFilter].forEach(element=>element.addEventListener("change",render));
searchInput.addEventListener("input",render);
init();
