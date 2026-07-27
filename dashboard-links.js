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
function addTokyoFlowEntry(){
  if(document.getElementById("tokyoFlowEntry"))return;
  const dashboard=document.querySelector(".dashboard-section");
  if(!dashboard)return;
  const section=document.createElement("section");
  section.id="tokyoFlowEntry";
  section.className="insight-section";
  section.setAttribute("aria-label","東京市場USDJPYフロー分析へのリンク");
  section.innerHTML=`
    <a href="tokyo-flow.html" class="insight-card" style="display:grid;grid-template-columns:1fr auto;gap:18px;align-items:center;color:inherit;text-decoration:none;background:linear-gradient(135deg,#eef7fb,#fff);border-color:#c7dfec">
      <span>
        <span class="dashboard-label">TOKYO USD/JPY FLOW</span>
        <strong style="display:block;font-size:21px;margin-bottom:4px">東京市場USD/JPYフロー分析</strong>
        <span style="display:block;color:var(--muted);font-size:14px">スポット出来高、前日比、20営業日平均との差、手入力ゴトー日をまとめて確認</span>
      </span>
      <span style="color:var(--accent);font-weight:900;white-space:nowrap">分析ページを開く →</span>
    </a>`;
  dashboard.insertAdjacentElement("afterend",section);
}
const dashboardObserver=new MutationObserver(activateDashboardMarketLinks);
const dashboardTarget=document.getElementById("dashboardMarkets");
if(dashboardTarget){dashboardObserver.observe(dashboardTarget,{childList:true});activateDashboardMarketLinks();}
addTokyoFlowEntry();
