const MARKET_LINK_ALIASES={
  "USD/JPY":"USD/JPY","USDJPY":"USD/JPY","ドル円":"USD/JPY",
  "EUR/USD":"EUR/USD","EURUSD":"EUR/USD","ユーロドル":"EUR/USD",
  "日経225先物":"日経225先物","日経先物":"日経225先物",
  "金":"金","ゴールド":"金","Gold":"金","XAUUSD":"金",
  "原油":"原油","WTI":"原油","ブレント":"原油",
  "BTCUSD":"BTCUSD","BTC/USD":"BTCUSD","ビットコイン":"BTCUSD"
};
function normalizeDashboardMarket(label=""){
  const text=String(label).trim();
  return MARKET_LINK_ALIASES[text]||Object.entries(MARKET_LINK_ALIASES).find(([key])=>text.includes(key))?.[1]||text;
}
function activateDashboardMarketLinks(){
  document.querySelectorAll("#dashboardMarkets .ticker-card").forEach(card=>{
    if(card.dataset.marketLinked==="true")return;
    const title=card.querySelector("h3")?.textContent||"";
    const market=normalizeDashboardMarket(title);
    if(!market)return;
    card.dataset.marketLinked="true";
    card.setAttribute("role","link");
    card.setAttribute("tabindex","0");
    card.setAttribute("aria-label",`${title}の市場別分析を開く`);
    const note=document.createElement("span");
    note.className="ticker-link-note";
    note.textContent="市場別分析を見る →";
    card.appendChild(note);
    const open=()=>{location.href=`market.html?market=${encodeURIComponent(market)}`;};
    card.addEventListener("click",open);
    card.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();open();}});
  });
}
const dashboardObserver=new MutationObserver(activateDashboardMarketLinks);
const dashboardTarget=document.getElementById("dashboardMarkets");
if(dashboardTarget){dashboardObserver.observe(dashboardTarget,{childList:true});activateDashboardMarketLinks();}
