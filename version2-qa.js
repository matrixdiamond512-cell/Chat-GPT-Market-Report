(()=>{
  const REQUIRED=[
    [".decision-support-panel","売買判断支援"],
    [".report-review-panel","レポートレビュー"],
    [".report-assistant-panel","レポート作成支援"],
    [".theme-transition-panel","テーマ遷移"],
    [".accuracy-improvement-panel","精度改善"],
    [".trade-checklist-panel","売買前チェック"],
    [".natural-search-section","自然言語検索"],
    ["#scenarioReview","シナリオ検証"],
    ["#marketSimilarReports","類似相場"],
    ["#marketNetwork","クロスアセット分析"]
  ];
  const runtimeErrors=[];
  window.addEventListener("error",event=>runtimeErrors.push(event.message||"JavaScript error"));
  window.addEventListener("unhandledrejection",event=>runtimeErrors.push(String(event.reason||"Unhandled promise rejection")));

  function render(){
    if(document.querySelector(".v2-release-status"))return;
    const missing=REQUIRED.filter(([selector])=>!document.querySelector(selector));
    const header=document.querySelector(".market-page-header .wrap");
    if(!header)return;
    const box=document.createElement("div");
    const ok=!missing.length&&!runtimeErrors.length;
    box.className=`v2-release-status ${ok?"ready":"warning"}`;
    box.innerHTML=`<div><span>PLATFORM VERSION</span><strong>Version 2.0</strong></div><div><b>${ok?"稼働中":"要確認"}</b><small>${ok?"主要10機能を読み込み済み":`${missing.length}機能未読込・エラー${runtimeErrors.length}件`}</small></div>`;
    if(!ok){
      const details=document.createElement("details");
      details.innerHTML=`<summary>診断内容</summary><ul>${missing.map(([,name])=>`<li>${name}が見つかりません</li>`).join("")}${runtimeErrors.map(error=>`<li>${String(error).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]))}</li>`).join("")}</ul>`;
      box.append(details);
    }
    header.append(box);
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",()=>setTimeout(render,1200));else setTimeout(render,1200);
})();
