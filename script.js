const latestReport=document.getElementById("latestReport");
const reportList=document.getElementById("reportList");
const timeFilter=document.getElementById("timeFilter");
const searchInput=document.getElementById("searchInput");
const resultCount=document.getElementById("resultCount");
const emptyMessage=document.getElementById("emptyMessage");
let reports=[];

function esc(value=""){return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));}
function listText(items=[]){return items.map(x=>`<p>・${esc(x)}</p>`).join("");}

function reportCard(item){
  const markets=(item.markets||[]).map(m=>`
    <div class="market-item">
      <h5>${esc(m.name)}</h5>
      <p><strong>${esc(m.direction)}</strong></p>
      <p>${esc(m.outlook)}</p>
      <p>崩れる条件：${esc(m.breakCondition)}</p>
    </div>`).join("");

  return `<article class="report-card">
    <header class="report-head">
      <h3>${esc(item.title)}</h3>
      <p class="meta">${esc(item.date.replaceAll("-","/"))} ${esc(item.time)}｜${esc((item.tags||[]).join("・"))}</p>
    </header>
    <div class="report-body">
      <div class="theme"><strong>今日の相場テーマ</strong>${esc(item.theme)}</div>
      <div class="section-grid">
        <section class="panel"><h4>前回からの変化</h4>${listText(item.changes)}</section>
        <section class="panel"><h4>材料と値動きの整合性</h4>${listText(item.consistency)}</section>
        <section class="panel"><h4>今日の主導市場</h4><p>${esc(item.leadingMarket)}</p></section>
        <section class="panel"><h4>ポジションの偏り</h4>${listText(item.positioning)}</section>
        <section class="panel"><h4>重要ニュース</h4>${listText(item.news)}</section>
        <section class="panel"><h4>次の時間帯への引き継ぎ</h4>${listText(item.handover)}</section>
      </div>
      <div class="market-grid">${markets}</div>
    </div>
  </article>`;
}

function render(){
  const t=timeFilter.value;
  const q=searchInput.value.trim().toLowerCase();
  const filtered=reports.filter(r=>{
    const haystack=JSON.stringify(r).toLowerCase();
    return (t==="all"||r.time===t)&&(!q||haystack.includes(q));
  });
  reportList.innerHTML=filtered.map(reportCard).join("");
  resultCount.textContent=`${filtered.length}件`;
  emptyMessage.hidden=filtered.length!==0;
}

async function init(){
  try{
    const response=await fetch("reports.json",{cache:"no-store"});
    if(!response.ok)throw new Error("reports.jsonを取得できませんでした。");
    reports=await response.json();
    reports.sort((a,b)=>(`${b.date} ${b.time}`).localeCompare(`${a.date} ${a.time}`));
    latestReport.innerHTML=reports[0]?reportCard(reports[0]):"<p class='empty'>レポートがありません。</p>";
    render();
  }catch(error){latestReport.innerHTML=`<p class="empty">${esc(error.message)}</p>`;}
}
timeFilter.addEventListener("change",render);
searchInput.addEventListener("input",render);
init();
