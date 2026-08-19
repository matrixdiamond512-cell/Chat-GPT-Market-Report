(function(){
'use strict';

const ROOT=document.querySelector('[data-gold-dashboard]');
if(!ROOT)return;

const URL='data/gold-supply-demand.json';
const CARD_ATTR='data-gold-macro-comparison';
const CONTRACT_OZ=100;
const OZ_PER_TONNE=32150.7466;

const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=v=>{const x=Number(v);return Number.isFinite(x)?x:null;};
const signed=(v,d=1)=>num(v)===null?'取得不能':`${Number(v)>0?'+':''}${Number(v).toLocaleString('ja-JP',{maximumFractionDigits:d,minimumFractionDigits:d})}`;
const date=v=>v?String(v).slice(0,10).replaceAll('-','/'):'取得不能';
const updated=v=>{
  if(!v)return'取得不能';
  try{
    return new Intl.DateTimeFormat('ja-JP',{
      timeZone:'Asia/Tokyo',
      year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',hour12:false
    }).format(new Date(v))+' JST';
  }catch(_){
    return String(v);
  }
};

const biasLabel={
  strong_bullish:'強気',
  bullish:'やや強気',
  neutral:'中立',
  bearish:'やや弱気',
  strong_bearish:'弱気'
};
const biasClass=b=>b.includes('bullish')?'bullish':b.includes('bearish')?'bearish':'neutral';
const statusText=s=>s==='stale'?'前回確認値':s==='verified'?'確認済み':'取得不能';

function usable(x){
  return x && ['verified','stale','preserved_after_fetch_error'].includes(x.status);
}

function judgement(score){
  if(num(score)===null)return'neutral';
  if(score>=0.65)return'strong_bullish';
  if(score>=0.20)return'bullish';
  if(score<=-0.65)return'strong_bearish';
  if(score<=-0.20)return'bearish';
  return'neutral';
}

function row(o){
  return Object.assign({
    group:'',
    key:'',
    label:'',
    direction:'取得不能',
    value:null,
    unit:'—',
    period:'取得不能',
    baseDate:null,
    updatedAt:null,
    score:null,
    status:'unavailable',
    comment:'取得不能（データ未連携）'
  },o||{});
}

function weeksDelta(history,weeks,key){
  const rows=(Array.isArray(history)?history:[])
    .filter(x=>num(x[key])!==null && x.asOfDate)
    .slice()
    .sort((a,b)=>String(a.asOfDate).localeCompare(String(b.asOfDate)));

  if(rows.length<2)return null;

  const last=rows[rows.length-1];
  const base=rows[Math.max(0,rows.length-1-weeks)];
  return {
    current:Number(last[key]),
    value:Number(last[key])-Number(base[key]),
    baseDate:last.asOfDate,
    period:`${date(base.asOfDate)}〜${date(last.asOfDate)}`
  };
}

function combineSummary(discoveryScore,sustainedScore){
  const d=judgement(discoveryScore);
  const s=judgement(sustainedScore);

  const dBull=['bullish','strong_bullish'].includes(d);
  const sBull=['bullish','strong_bullish'].includes(s);
  const dBear=['bearish','strong_bearish'].includes(d);
  const sBear=['bearish','strong_bearish'].includes(s);

  if(num(discoveryScore)===null && num(sustainedScore)===null){
    return {
      label:'判定保留',
      cls:'neutral',
      text:'両系列とも十分な確認済みデータが揃っていません。'
    };
  }
  if(dBull && sBull){
    return {
      label:'上昇を支持',
      cls:'bullish',
      text:'価格発見フローと持続需給フローがともに買い方向です。'
    };
  }
  if(dBear && sBear){
    return {
      label:'下落を支持',
      cls:'bearish',
      text:'価格発見フローと持続需給フローがともに売り方向です。'
    };
  }
  return {
    label:'強弱混在',
    cls:'neutral',
    text:'短期の価格発見と中期の持続需給が一致していません。'
  };
}

function score(rows){
  const xs=rows.filter(x=>num(x.score)!==null);
  return xs.length?xs.reduce((a,x)=>a+Number(x.score),0)/xs.length:null;
}

function build(data,months){
  const weeks={1:4,3:13,6:26}[months]||4;

  const etf=data.etf||{};
  const cot=data.cftc||{};
  const comex=data.comex||{};
  const cb=data.centralBank||{};
  const physical=data.physical||{};
  const env=data.environment||{};

  const gld=etf.gld||{};
  const iau=etf.iau||{};
  const global=etf.global||{};
  const china=physical.china||{};
  const india=physical.india||{};
  const realYield=env.realYield10y||{};
  const dollar=env.dollarBroad||{};

  const sustained=[];

  if(usable(global) && num(global.changeTonnes)!==null){
    sustained.push(row({
      group:'持続需給',
      key:'world_etf',
      label:'世界金ETF',
      direction:Number(global.changeTonnes)>=0?'流入':'流出',
      value:Number(global.changeTonnes),
      unit:'t',
      period:global.period||'最新公表月',
      baseDate:global.asOfDate||global.period,
      updatedAt:global.fetchedAt||data.generatedAt,
      score:Math.sign(Number(global.changeTonnes)),
      status:global.status,
      comment:'主指標。世界ETF全体の流入出を使用します。'
    }));
  }else{
    sustained.push(row({
      group:'持続需給',
      key:'world_etf',
      label:'世界金ETF',
      comment:`取得不能（${global.error||'世界ETFデータ未連携'}）`
    }));
  }

  sustained.push(row({
    group:'持続需給',
    key:'gld',
    label:'GLD（補助）',
    direction:num(gld.changeTonnes)===null?'取得不能':Number(gld.changeTonnes)>=0?'流入':'流出',
    value:num(gld.changeTonnes),
    unit:'t',
    period:'最新日次',
    baseDate:gld.asOfDate,
    updatedAt:gld.fetchedAt||data.generatedAt,
    score:null,
    status:gld.status||'unavailable',
    comment:'補助表示。世界金ETFと重複するため採点対象外です。'
  }));

  sustained.push(row({
    group:'持続需給',
    key:'iau',
    label:'IAU（補助）',
    direction:num(iau.changeTonnes)===null?'取得不能':Number(iau.changeTonnes)>=0?'流入':'流出',
    value:num(iau.changeTonnes),
    unit:'t',
    period:'最新日次',
    baseDate:iau.asOfDate,
    updatedAt:iau.fetchedAt||data.generatedAt,
    score:null,
    status:iau.status||'unavailable',
    comment:'補助表示。世界金ETFと重複するため採点対象外です。'
  }));

  if(usable(cb) && num(cb.netPurchasesTonnes)!==null){
    sustained.push(row({
      group:'持続需給',
      key:'central_banks',
      label:'中央銀行',
      direction:Number(cb.netPurchasesTonnes)>=0?'純購入':'純売却',
      value:Number(cb.netPurchasesTonnes),
      unit:'t',
      period:months===1?'最新公表月':'最新公表月（累計未連携）',
      baseDate:cb.period,
      updatedAt:data.generatedAt,
      score:Math.sign(Number(cb.netPurchasesTonnes)),
      status:cb.status,
      comment:'公的部門の構造的需要です。短期の価格発見よりも中期の下支え確認に使います。'
    }));
  }else{
    sustained.push(row({
      group:'持続需給',
      key:'central_banks',
      label:'中央銀行',
      comment:`取得不能（${cb.error||'中央銀行データ未連携'}）`
    }));
  }

  sustained.push(row({
    group:'持続需給',
    key:'china',
    label:'中国プレミアム',
    direction:num(china.premiumUsdOz)===null?'取得不能':Number(china.premiumUsdOz)>=0?'買い需要寄り':'需要弱め',
    value:num(china.premiumUsdOz),
    unit:'$/oz',
    period:'最新週次',
    baseDate:china.asOfDate||physical.asOfDate,
    updatedAt:data.generatedAt,
    score:num(china.premiumUsdOz)===null?null:Math.sign(Number(china.premiumUsdOz))*0.5,
    status:china.status||physical.status||'unavailable',
    comment:'現物需要の温度感です。プラス幅拡大は現物需要の強さを示します。'
  }));

  sustained.push(row({
    group:'持続需給',
    key:'india',
    label:'インドプレミアム',
    direction:num(india.premiumUsdOz)===null?'取得不能':Number(india.premiumUsdOz)>=0?'買い需要寄り':'需要弱め',
    value:num(india.premiumUsdOz),
    unit:'$/oz',
    period:'最新週次',
    baseDate:india.asOfDate||physical.asOfDate,
    updatedAt:data.generatedAt,
    score:num(india.premiumUsdOz)===null?null:Math.sign(Number(india.premiumUsdOz))*0.5,
    status:india.status||physical.status||'unavailable',
    comment:'現物需要の温度感です。割高でも買われるかを確認します。'
  }));

  const discovery=[];

  const mm=weeksDelta(cot.historyWeeks,weeks,'net');
  if(mm){
    const tonnesEq=mm.value*CONTRACT_OZ/OZ_PER_TONNE;
    discovery.push(row({
      group:'価格発見',
      key:'managed_money_tonnes',
      label:'COMEX投機筋ネット変化',
      direction:mm.value>=0?'ネットロング増加':'ネットロング縮小',
      value:tonnesEq,
      unit:'t相当',
      period:mm.period,
      baseDate:mm.baseDate,
      updatedAt:cot.fetchedAt||data.generatedAt,
      score:Math.sign(mm.value),
      status:cot.status||'unavailable',
      comment:`Managed Money 期間差 ${signed(mm.value,0)}枚 = ${signed(tonnesEq,1)}t相当。ETFと比較しやすいようトン換算で表示。`
    }));
  }else{
    discovery.push(row({
      group:'価格発見',
      key:'managed_money_tonnes',
      label:'COMEX投機筋ネット変化',
      comment:'取得不能（CFTC履歴不足）'
    }));
  }

  const oi=weeksDelta(cot.historyWeeks,weeks,'openInterest');
  if(oi){
    let oiScore=null;
    let oiComment=`対象期間の建玉変化 ${signed(oi.value,0)}枚。`;
    if(months===1 && num(comex.alignedPriceChangePercent)!==null && num(comex.openInterestChange)!==null){
      const p=Number(comex.alignedPriceChangePercent);
      const o=Number(comex.openInterestChange);
      if(p>0 && o>0){ oiScore=0.5; oiComment+=' 価格上昇＋建玉増加で新規ロング流入の可能性。'; }
      else if(p<0 && o>0){ oiScore=-0.5; oiComment+=' 価格下落＋建玉増加で新規ショート流入の可能性。'; }
      else if(p>0 && o<0){ oiScore=0.2; oiComment+=' 価格上昇＋建玉減少でショートカバー優勢の可能性。'; }
      else if(p<0 && o<0){ oiScore=-0.2; oiComment+=' 価格下落＋建玉減少でロング清算優勢の可能性。'; }
      else { oiScore=0; }
    }else{
      oiComment+=' 同日価格が揃わない期間では方向採点を行いません。';
    }

    discovery.push(row({
      group:'価格発見',
      key:'open_interest',
      label:'COMEX建玉',
      direction:oi.value>=0?'増加':'減少',
      value:oi.value,
      unit:'枚',
      period:oi.period,
      baseDate:oi.baseDate,
      updatedAt:cot.fetchedAt||data.generatedAt,
      score:oiScore,
      status:cot.status||'unavailable',
      comment:oiComment
    }));
  }else{
    discovery.push(row({
      group:'価格発見',
      key:'open_interest',
      label:'COMEX建玉',
      comment:'取得不能（建玉履歴不足）'
    }));
  }

  discovery.push(row({
    group:'価格発見',
    key:'real_yield',
    label:'米10年実質金利',
    direction:num(realYield.change)===null?'取得不能':Number(realYield.change)<0?'低下（追い風）':'上昇（逆風）',
    value:num(realYield.change),
    unit:'pt',
    period:'最新日次',
    baseDate:realYield.asOfDate,
    updatedAt:realYield.fetchedAt||data.generatedAt,
    score:num(realYield.change)===null?null:Math.sign(-Number(realYield.change)),
    status:realYield.status||'unavailable',
    comment:'実質金利低下は金に追い風、上昇は逆風です。'
  }));

  discovery.push(row({
    group:'価格発見',
    key:'dollar',
    label:'米ドル実効指数',
    direction:num(dollar.change)===null?'取得不能':Number(dollar.change)<0?'ドル安（追い風）':'ドル高（逆風）',
    value:num(dollar.change),
    unit:'',
    period:'最新日次',
    baseDate:dollar.asOfDate,
    updatedAt:dollar.fetchedAt||data.generatedAt,
    score:num(dollar.change)===null?null:Math.sign(-Number(dollar.change)),
    status:dollar.status||'unavailable',
    comment:'ドル安は金に追い風、ドル高は逆風です。'
  }));

  return {discovery,sustained};
}

function bar(row,max){
  if(num(row.score)===null){
    return `<div class="gmc-unavailable">${esc(row.comment)}</div>`;
  }
  const base=num(row.value)===null?1:Math.abs(Number(row.value));
  const width=Math.max(3,Math.min(48,base/(max||1)*48));
  return `<div class="gmc-track"><span class="gmc-bar ${Number(row.score)>0?'buy':Number(row.score)<0?'sell':'neutral'}" style="width:${width}%"></span></div>`;
}

function rowsHtml(rows){
  const available=rows.filter(x=>num(x.value)!==null);
  const max=Math.max(1,...available.map(x=>Math.abs(Number(x.value))));
  return rows.map(x=>`
    <div class="gmc-row">
      <div class="gmc-row-head">
        <b>${esc(x.label)}</b>
        <span>${num(x.value)===null?'取得不能':`${signed(x.value,x.unit==='枚'?0:(x.unit==='t相当'||x.unit==='t'||x.unit==='$/oz'?1:2))} ${esc(x.unit)}`}</span>
      </div>
      ${bar(x,max)}
      <div class="gmc-meta">
        対象期間 ${esc(x.period)} / 基準日 ${esc(date(x.baseDate))} / 更新日時 ${esc(updated(x.updatedAt))} /
        <span class="${x.status==='stale'?'gmc-stale':x.status==='verified'?'gmc-live':''}">${esc(statusText(x.status))}</span>
      </div>
    </div>
  `).join('');
}

function tableRow(x){
  const b=num(x.score)===null?'neutral':judgement(Number(x.score));
  const digits=x.unit==='枚'?0:(x.unit==='t相当'||x.unit==='t'||x.unit==='$/oz'?1:2);
  return `
    <tr>
      <td>${esc(x.group)}</td>
      <td><b>${esc(x.label)}</b></td>
      <td>${esc(x.direction||'取得不能')}</td>
      <td class="num">${num(x.value)===null?'取得不能':signed(x.value,digits)}</td>
      <td>${esc(x.unit)}</td>
      <td>${esc(x.period)}</td>
      <td>${esc(date(x.baseDate))}</td>
      <td>${esc(updated(x.updatedAt))}<br><span class="${x.status==='stale'?'gmc-stale':x.status==='verified'?'gmc-live':''}">${esc(statusText(x.status))}</span></td>
      <td><span class="gmc-bias ${biasClass(b)}">${num(x.score)===null?'採点対象外 / 判定保留':biasLabel[b]}</span></td>
      <td>${esc(x.comment)}</td>
    </tr>
  `;
}

function render(data,months){
  const built=build(data,months);
  const discoveryScore=score(built.discovery);
  const sustainedScore=score(built.sustained);
  const discoveryBias=judgement(discoveryScore);
  const sustainedBias=judgement(sustainedScore);
  const summary=combineSummary(discoveryScore,sustainedScore);
  const all=[...built.discovery,...built.sustained];

  const html=`
    <section class="gold-card gmc" ${CARD_ATTR}>
      <div class="gmc-head">
        <div>
          <h2>ゴールド需給全体比較</h2>
          <p>「誰が売買しているか」を、価格発見フローと持続需給フローに分けて確認</p>
        </div>
        <div class="gmc-periods" aria-label="表示期間">
          ${[1,3,6].map(x=>`<button class="gmc-period" data-gmc-period="${x}" aria-pressed="${x===months}">${x}か月</button>`).join('')}
        </div>
      </div>

      <div class="gmc-body">
        <div class="gmc-verdict">
          <div class="gmc-verdict-main">
            <span class="gmc-kicker">総合整理</span>
            <strong class="${summary.cls}">${summary.label}</strong>
            <p>${esc(summary.text)}</p>
            <p>※ これは単純な合成スコアではありません。2系列の一致・不一致を整理しています。</p>
          </div>

          <div class="gmc-verdict-part">
            <span class="gmc-kicker">価格発見フロー</span>
            <strong class="${biasClass(discoveryBias)}">${num(discoveryScore)===null?'判定保留':biasLabel[discoveryBias]}</strong>
            <p>先物・投機筋・実質金利・ドルを中心に、短期の値動きを見ます。</p>
          </div>

          <div class="gmc-verdict-part">
            <span class="gmc-kicker">持続需給フロー</span>
            <strong class="${biasClass(sustainedBias)}">${num(sustainedScore)===null?'判定保留':biasLabel[sustainedBias]}</strong>
            <p>ETF・中央銀行・現物需要を中心に、中期の下支え / 売り圧力を見ます。</p>
          </div>
        </div>

        <div class="gmc-columns">
          <div class="gmc-panel">
            <h3>価格発見フロー比較</h3>
            <div class="gmc-axis"><span>売り圧力</span><span>0</span><span>買い圧力</span></div>
            <div class="gmc-bars">${rowsHtml(built.discovery)}</div>
          </div>

          <div class="gmc-panel">
            <h3>持続需給フロー比較</h3>
            <div class="gmc-axis"><span>売り圧力</span><span>0</span><span>買い圧力</span></div>
            <div class="gmc-bars">${rowsHtml(built.sustained)}</div>
          </div>
        </div>

        <div class="gmc-table-wrap">
          <table class="gmc-table">
            <thead>
              <tr>
                <th>区分</th>
                <th>指標</th>
                <th>方向</th>
                <th>数値</th>
                <th>単位</th>
                <th>対象期間</th>
                <th>基準日</th>
                <th>更新日時</th>
                <th>判定</th>
                <th>コメント</th>
              </tr>
            </thead>
            <tbody>${all.map(tableRow).join('')}</tbody>
          </table>
        </div>

        <div class="gmc-memo">
          <h3>解釈メモ</h3>
          <ul>
            <li>世界金ETFを主指標とし、GLD・IAUは補助表示のみとしました。これによりETFの二重カウントを避けています。</li>
            <li>ETFは「その日に価格を直接動かした主体」とは限らず、資金流入 / 流出の確認指標として扱います。</li>
            <li>CFTCは週次、ETFは日次 / 週次、中央銀行は月次で更新頻度が異なるため、同列比較ではなく役割分担で見ます。</li>
            <li>COMEX投機筋は枚数だけでなくトン換算も表示し、ETFフローと比較しやすくしました。</li>
          </ul>
          <div class="gmc-method">
            判定方法：価格発見フローと持続需給フローを別々に採点し、単純加重平均は行いません。
            両方が同方向なら支持、逆方向なら「強弱混在」と整理します。
          </div>
        </div>
      </div>
    </section>
  `;

  const existing=document.querySelector(`[${CARD_ATTR}]`);
  if(existing){
    existing.outerHTML=html;
  }else{
    const cards=[...document.querySelectorAll('.gold-card')];
    const anchor=cards.find(card=>{
      const title=card.querySelector('.gold-section-title');
      return title && title.textContent.trim()==='中国・インド現物需要';
    });
    if(anchor){
      anchor.insertAdjacentHTML('afterend',html);
    }else{
      ROOT.insertAdjacentHTML('beforeend',html);
    }
  }

  document.querySelectorAll('.gmc-period').forEach(btn=>{
    btn.addEventListener('click',()=>{
      const next=Number(btn.getAttribute('data-gmc-period'))||1;
      render(data,next);
    });
  });
}

async function init(){
  try{
    const r=await fetch(`${URL}?ts=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    render(data,1);
  }catch(err){
    const existing=document.querySelector(`[${CARD_ATTR}]`);
    const html=`
      <section class="gold-card gmc" ${CARD_ATTR}>
        <div class="gmc-head">
          <div>
            <h2>ゴールド需給全体比較</h2>
            <p>読み込みエラー</p>
          </div>
        </div>
        <div class="gmc-body">
          <div class="gmc-unavailable">需給全体比較の読み込みに失敗しました。再読込してください。</div>
        </div>
      </section>
    `;
    if(existing) existing.outerHTML=html;
    else ROOT.insertAdjacentHTML('beforeend',html);
  }
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',init,{once:true});
}else{
  init();
}
})();