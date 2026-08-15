(()=>{
'use strict';
const root=document.querySelector('[data-arbitrage]');
if(!root)return;

const DATA_URL='data/nikkei225-arbitrage.json';
const PANEL_ID='arbTradeDecisionPanel';
const n=v=>v===null||v===undefined||v===''?null:(Number.isFinite(Number(String(v).replace(/,/g,'')))?Number(String(v).replace(/,/g,'')):null);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,d=0)=>n(v)===null?'取得不能':n(v).toLocaleString('ja-JP',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(v,d=0,suffix='')=>n(v)===null?'取得不能':`${n(v)>0?'+':''}${fmt(v,d)}${suffix}`;
const oku=v=>n(v)===null?'取得不能':`${fmt(n(v)/100000,2)}億株`;
const signedOku=v=>n(v)===null?'取得不能':`${n(v)>0?'+':''}${fmt(n(v)/100000,2)}億株`;
const yen=v=>n(v)===null?'取得不能':`${fmt(v,0)}円`;
const iso=v=>{const s=String(v||'').slice(0,10).replaceAll('/','-');return /^\d{4}-\d{2}-\d{2}$/.test(s)?s:''};
const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
const sign=(v,weight=1)=>n(v)===null?0:n(v)>0?weight:n(v)<0?-weight:0;
const tone=v=>n(v)>0?'trade-up':n(v)<0?'trade-down':'trade-flat';

function normalize(d){
  const rows=(Array.isArray(d?.history)?d.history:[])
    .map(x=>({date:iso(x.date),buy:n(x.buyBalance),sell:n(x.sellBalance),price:n(x.nikkei225Close)}))
    .filter(x=>x.date&&x.buy!==null&&x.sell!==null)
    .map(x=>({...x,net:x.buy-x.sell}))
    .sort((a,b)=>a.date.localeCompare(b.date));
  return rows.filter((x,i)=>i===rows.length-1||x.date!==rows[i+1].date);
}

function percentile(value,values){
  const clean=values.filter(v=>n(v)!==null).map(Number).sort((a,b)=>a-b);
  if(n(value)===null||!clean.length)return null;
  const below=clean.filter(v=>v<=value).length;
  return below/clean.length*100;
}

function pairScore(priceChange,netChange){
  if(n(priceChange)===null||n(netChange)===null)return 0;
  if(priceChange>0&&netChange>0)return 1;
  if(priceChange>0&&netChange<0)return 2;
  if(priceChange<0&&netChange>0)return -2;
  if(priceChange<0&&netChange<0)return -1;
  return 0;
}

function pairLabel(priceChange,netChange){
  if(n(priceChange)===null||n(netChange)===null)return'比較値不足';
  if(priceChange>0&&netChange>0)return'株価上昇＋裁定残増加';
  if(priceChange>0&&netChange<0)return'株価上昇＋裁定残減少';
  if(priceChange<0&&netChange>0)return'株価下落＋裁定残増加';
  if(priceChange<0&&netChange<0)return'株価下落＋裁定残減少';
  return'方向感限定';
}

function analyze(d){
  const rows=normalize(d);
  const asOf=iso(d?.asOfDate);
  let index=rows.findIndex(x=>x.date===asOf);
  if(index<0&&asOf)index=rows.map(x=>x.date).findLastIndex(date=>date<=asOf);
  if(index<0)index=rows.length-1;
  const current=index>=0?rows[index]:null;
  const prior=k=>index>=k?rows[index-k]:null;
  const previous=prior(1),p5=prior(5),p20=prior(20);

  const buy=n(d?.latest?.buyBalance)??current?.buy??null;
  const sell=n(d?.latest?.sellBalance)??current?.sell??null;
  const net=buy!==null&&sell!==null?buy-sell:null;
  const buyDay=n(d?.latest?.buyChange)??(previous&&buy!==null?buy-previous.buy:null);
  const sellDay=n(d?.latest?.sellChange)??(previous&&sell!==null?sell-previous.sell:null);
  const netDay=buyDay!==null&&sellDay!==null?buyDay-sellDay:(previous&&net!==null?net-previous.net:null);
  const net5=p5&&net!==null?net-p5.net:null;
  const net20=p20&&net!==null?net-p20.net:null;
  const price=current?.price??null;
  const price5=p5&&price!==null&&p5.price!==null?price-p5.price:null;
  const price20=p20&&price!==null&&p20.price!==null?price-p20.price:null;
  const price5Pct=p5?.price?price5/p5.price*100:null;
  const price20Pct=p20?.price?price20/p20.price*100:null;

  const recentStart=Math.max(1,index-4);
  const recentMoves=[];
  for(let i=recentStart;i<=index;i++)recentMoves.push(rows[i].net-rows[i-1].net);
  const upDays=recentMoves.filter(v=>v>0).length;
  const downDays=recentMoves.filter(v=>v<0).length;

  const gross=buy!==null&&sell!==null?buy+sell:null;
  const buyWeight=gross?buy/gross*100:null;
  const trailing52=rows.slice(Math.max(0,index-259),index+1);
  const netPctile=percentile(net,trailing52.map(x=>x.net));

  let directionScore=sign(netDay,2)+sign(net5,3)+sign(net20,3);
  if(upDays>downDays)directionScore+=1;
  if(downDays>upDays)directionScore-=1;
  if(buyWeight!==null&&buyWeight>=85&&net5!==null){
    if(net5>0)directionScore+=1;
    if(net5<0)directionScore-=1;
  }
  directionScore=clamp(directionScore,-10,10);

  let consistencyScore=pairScore(price5,net5)+pairScore(price20,net20);
  consistencyScore=clamp(consistencyScore,-5,5);

  let riskScore=0;
  if(net===null)riskScore=0;
  else if(net<0)riskScore=1;
  else if(net<250000)riskScore=2;
  else if(net<500000)riskScore=4;
  else if(net<1000000)riskScore=7;
  else riskScore=9;
  if(netPctile!==null&&netPctile>=80)riskScore+=1;
  if(netPctile!==null&&netPctile>=90)riskScore+=1;
  if(net5!==null&&net20!==null&&net5>0&&net20>0)riskScore+=1;
  riskScore=clamp(riskScore,0,10);

  const riskPenalty=riskScore>=9?3:riskScore>=7?2:riskScore>=4?1:0;
  const totalScore=clamp(directionScore+consistencyScore-riskPenalty,-15,15);
  const bias=totalScore>=6?'強気':totalScore>=3?'やや強気':totalScore<=-6?'弱気':totalScore<=-3?'やや弱気':'中立';
  const biasClass=totalScore>=3?'bull':totalScore<=-3?'bear':'neutral';

  let action='様子見';
  if(totalScore>=3&&riskScore>=7)action='押し目買い優勢・高値追い慎重';
  else if(totalScore>=3)action='押し目買い優勢';
  else if(totalScore<=-3)action='戻り売り優勢';
  else if(directionScore>0)action='売りはまだ早い';

  const prior5=rows.slice(Math.max(0,index-5),index).map(x=>x.price).filter(v=>v!==null);
  const prior20=rows.slice(Math.max(0,index-20),index).map(x=>x.price).filter(v=>v!==null);
  const high5=prior5.length?Math.max(...prior5):null;
  const low5=prior5.length?Math.min(...prior5):null;
  const high20=prior20.length?Math.max(...prior20):null;
  const low20=prior20.length?Math.min(...prior20):null;

  const level=net===null?'判定不能':net>=1000000?'10億株超・強い警戒':net>=500000?'5億株超・警戒':net>=250000?'中程度':'低水準';
  const flow=net5===null||net20===null?'期間比較不足':net5>0&&net20>0?'短期・中期とも積み上がり':net5<0&&net20<0?'短期・中期とも解消':net5>0?'短期で再積み上がり':'短期で解消へ転換';
  const driver=netDay===null?'内訳比較不足':netDay>0?(buyDay>0&&sellDay<=0?'買い残増＋売り残減':buyDay>sellDay?'買い残増が主因':'売り残も増加しネット増は限定的'):(netDay<0?(buyDay<0&&sellDay>=0?'買い残減＋売り残増':Math.abs(buyDay||0)>Math.abs(sellDay||0)?'買い残減が主因':'売り残変化が主因'):'買い残・売り残が相殺');
  const divergence=pairLabel(price5,net5);

  const bullish=(totalScore>=3);
  const bearish=(totalScore<=-3);
  let summary='裁定需給だけでは一方向の優位性は弱く、株価のブレイク確認を優先します。';
  if(bullish&&riskScore>=7)summary='裁定需給は上向きですが、買い残の蓄積も大きい状態です。基本は押し目買い優勢、ただし高値追いよりも押しを待つ方が安全です。';
  else if(bullish)summary='裁定需給は日経225の支えになりやすい状態です。直近安値を維持する限り、押し目買いを優先します。';
  else if(bearish)summary='裁定需給は日経225の上値を抑えやすい状態です。戻り局面では売り優勢ですが、安値追いより戻りを待つ判断を優先します。';
  else if(directionScore>0)summary='裁定残は増加方向ですが、株価との整合性または残高リスクが十分ではありません。売り急がず、上抜け確認を待つ局面です。';

  const buyConditions=[];
  const sellConditions=[];
  const waitConditions=[];
  if(high5!==null)buyConditions.push(`日経225終値が直近5日高値 ${yen(high5)} を上抜く`);
  buyConditions.push('ネット裁定残の5日変化がプラスを維持または再びプラスへ転換');
  buyConditions.push('裁定買い残の増加が裁定売り残の増加を上回る');
  if(low5!==null)sellConditions.push(`日経225終値が直近5日安値 ${yen(low5)} を下回る`);
  sellConditions.push('ネット裁定残の5日変化がマイナスへ転換・拡大');
  sellConditions.push('裁定買い残減少または裁定売り残増加がネット残を押し下げる');
  waitConditions.push('日経225とネット裁定残が逆方向に動き、整合性が崩れている');
  waitConditions.push('5日変化と20日変化の方向が逆で、短期転換か一時変動か判別しにくい');

  let mainScenario='',altScenario='',breakdown='';
  if(bullish){
    mainScenario=`ネット裁定残の積み上がり・高止まりが続き、${low5!==null?`日経225終値が ${yen(low5)} を維持する`: '日経225が直近安値を維持する'}なら、裁定需給は押し目を支えやすい。${riskScore>=7?'ただし高水準の買い残があるため、上昇加速局面の追随買いは抑える。':''}`;
    altScenario=`ネット裁定残が5日比で減少へ転じ、${low5!==null?`${yen(low5)} を終値で割り込む`:'日経225が直近安値を割る'}場合、裁定買いの解消が現物売り圧力へ変わる可能性を優先する。`;
    breakdown=`強気判断の撤回条件は「ネット裁定残5日比マイナス」かつ「${low5!==null?`日経225終値 ${yen(low5)} 未満`:'日経225の直近5日安値割れ'}」。両方が揃えば押し目買い優先を解除する。`;
  }else if(bearish){
    mainScenario=`ネット裁定残の解消または株価との弱い整合性が続き、${high5!==null?`日経225終値が ${yen(high5)} を回復できない`:'直近高値を回復できない'}限り、戻り売りを優先する。`;
    altScenario=`ネット裁定残が再び5日比プラスへ転じ、${high5!==null?`${yen(high5)} を終値で上抜く`:'日経225が直近高値を上抜く'}場合、弱気判断を解除し買い戻し優勢へ切り替える。`;
    breakdown=`弱気判断の撤回条件は「ネット裁定残5日比プラス」かつ「${high5!==null?`日経225終値 ${yen(high5)} 超`:'日経225の直近5日高値超え'}」。`;
  }else{
    mainScenario=`現状は裁定需給だけで方向を決めにくい。${high5!==null&&low5!==null?`${yen(low5)}〜${yen(high5)} の直近レンジ`: '直近5日レンジ'}のどちらを終値で抜けるかを待ち、裁定残の5日変化が同方向に揃うか確認する。`;
    altScenario='価格だけが先にブレイクして裁定残が追随しない場合は、裁定需給由来のシグナルとしては信頼度を下げる。';
    breakdown='中立判断は、日経225のレンジブレイクとネット裁定残5日変化が同方向に揃った時点で解除する。';
  }

  const confidence=Math.round(clamp(45+Math.abs(totalScore)*4+(Math.abs(directionScore)>=5?8:0)-(net5===null?15:0)-(price5===null?10:0),30,90));

  return{asOf:asOf||current?.date||'',buy,sell,net,buyDay,sellDay,netDay,net5,net20,price,price5,price20,price5Pct,price20Pct,upDays,downDays,buyWeight,netPctile,directionScore,consistencyScore,riskScore,totalScore,bias,biasClass,action,level,flow,driver,divergence,summary,buyConditions,sellConditions,waitConditions,mainScenario,altScenario,breakdown,high5,low5,high20,low20,confidence};
}

function scoreCard(label,value,min,max,caption,klass=''){
  const pct=clamp((value-min)/(max-min)*100,0,100);
  return`<article class="arb-trade-score ${klass}"><div class="arb-trade-score-head"><span>${esc(label)}</span><strong>${value>0?'+':''}${fmt(value,0)}</strong></div><div class="arb-trade-meter"><i style="width:${pct}%"></i></div><p>${esc(caption)}</p></article>`;
}

function list(items){return`<ul>${items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`}

function render(a){
  const riskLabel=a.riskScore>=8?'強い警戒':a.riskScore>=6?'警戒':a.riskScore>=3?'通常':'低い';
  const dirLabel=a.directionScore>=6?'強い追い風':a.directionScore>=3?'やや追い風':a.directionScore<=-6?'強い逆風':a.directionScore<=-3?'やや逆風':'中立';
  const consistencyLabel=a.consistencyScore>=3?'良好':a.consistencyScore<=-3?'弱い':'混在';
  const netTrendTone=tone(a.net5);
  return`<section id="${PANEL_ID}" class="arb-trade-decision ${a.biasClass}" aria-label="裁定需給から見た日経225売買判断">
    <div class="arb-trade-hero">
      <div>
        <span class="arb-trade-kicker">裁定需給から見た日経225売買判断</span>
        <div class="arb-trade-bias-line"><strong class="arb-trade-bias">${esc(a.bias)}</strong><span class="arb-trade-action">${esc(a.action)}</span><span class="arb-trade-confidence">信頼度 ${a.confidence}%</span></div>
        <p class="arb-trade-summary">${esc(a.summary)}</p>
      </div>
      <div class="arb-trade-hero-stats">
        <div><span>ネット裁定残</span><b>${oku(a.net)}</b><small>${esc(a.level)}</small></div>
        <div><span>5日変化</span><b class="${netTrendTone}">${signedOku(a.net5)}</b><small>${esc(a.flow)}</small></div>
        <div><span>日経225</span><b>${yen(a.price)}</b><small>5日 ${signed(a.price5Pct,1,'%')}</small></div>
      </div>
    </div>

    <div class="arb-trade-score-grid">
      ${scoreCard('方向スコア',a.directionScore,-10,10,`${dirLabel}｜裁定残の1日・5日・20日の方向を集約`,'direction')}
      ${scoreCard('株価との整合性',a.consistencyScore,-5,5,`${consistencyLabel}｜${a.divergence}`,'consistency')}
      ${scoreCard('買い残巻き戻しリスク',a.riskScore,0,10,`${riskLabel}｜残高水準・52週位置・積み上がりを評価`,'risk')}
    </div>

    <div class="arb-trade-facts">
      <article><span>最新ネット変化</span><b class="${tone(a.netDay)}">${signedOku(a.netDay)}</b><small>${esc(a.driver)}</small></article>
      <article><span>20日ネット変化</span><b class="${tone(a.net20)}">${signedOku(a.net20)}</b><small>中期の積み上がり／解消方向</small></article>
      <article><span>買い残構成比</span><b>${a.buyWeight===null?'取得不能':`${fmt(a.buyWeight,1)}%`}</b><small>総裁定残に占める買い残</small></article>
      <article><span>52週位置</span><b>${a.netPctile===null?'取得不能':`上位 ${fmt(100-a.netPctile,0)}%圏`}</b><small>ネット裁定残の相対水準</small></article>
    </div>

    <div class="arb-trade-action-grid">
      <article class="arb-trade-plan buy"><h3>買いを優先する確認条件</h3>${list(a.buyConditions)}</article>
      <article class="arb-trade-plan sell"><h3>売りを優先する確認条件</h3>${list(a.sellConditions)}</article>
      <article class="arb-trade-plan wait"><h3>様子見へ切り替える条件</h3>${list(a.waitConditions)}</article>
    </div>

    <div class="arb-trade-levels">
      <h3>裁定データと合わせて見る日経225終値水準</h3>
      <div>
        <span>直近5日高値<b>${yen(a.high5)}</b></span>
        <span>直近5日安値<b>${yen(a.low5)}</b></span>
        <span>直近20日高値<b>${yen(a.high20)}</b></span>
        <span>直近20日安値<b>${yen(a.low20)}</b></span>
      </div>
      <small>※ 裁定取引データはリアルタイム売買シグナルではありません。上記水準は日経225終値ベースの確認ラインとして使い、先物の実際のエントリー価格とは分けて判断します。</small>
    </div>

    <div class="arb-trade-scenarios">
      <article class="main"><span>メインシナリオ</span><p>${esc(a.mainScenario)}</p></article>
      <article class="alternate"><span>代替シナリオ</span><p>${esc(a.altScenario)}</p></article>
      <article class="break"><span>シナリオが崩れる条件</span><p>${esc(a.breakdown)}</p></article>
    </div>

    <div class="arb-trade-note"><b>使い方：</b>この判定は「裁定需給から見た日経225の売買バイアス」です。裁定残だけで最終売買を決めず、日経225先物の価格、金利、為替、海外株、オプション・SQ需給と組み合わせて使います。<span>基準日 ${esc(a.asOf||'取得不能')}</span></div>
  </section>`;
}

async function load(){
  const r=await fetch(`${DATA_URL}?tradeDecision=${Date.now()}`,{cache:'no-store'});
  if(!r.ok)throw new Error(`裁定取引データ HTTP ${r.status}`);
  return r.json();
}

function mount(html){
  const ready=()=>!root.querySelector('.loading-card');
  const insert=()=>{
    if(document.getElementById(PANEL_ID)||!ready())return false;
    root.insertAdjacentHTML('afterbegin',html);
    return true;
  };
  if(insert())return;
  const obs=new MutationObserver(()=>{if(insert())obs.disconnect()});
  obs.observe(root,{childList:true,subtree:false});
  setTimeout(()=>{insert();obs.disconnect()},10000);
}

load().then(d=>mount(render(analyze(d)))).catch(err=>{
  console.error('[arbitrage-trade-decision]',err);
  const msg=`<section id="${PANEL_ID}" class="arb-trade-decision error"><b>売買判断分析を表示できませんでした。</b><span>${esc(err?.message||err)}</span></section>`;
  mount(msg);
});
})();
