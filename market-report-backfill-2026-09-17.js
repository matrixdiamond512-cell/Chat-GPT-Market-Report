/* 2026-09-17 missing-report recovery. The Google Docs linked below are the original full documents. The inline text is a clearly labeled portal digest, not a re-verification of market prices. */
(() => {
  'use strict';
  const docs = {
    '08:00': 'https://docs.google.com/document/d/1CeBSTb4lXQgvr-aR_N4eZjEp37bwatLXvi-ERraPNds/edit',
    '12:00': 'https://docs.google.com/document/d/1wNLK1tW1XKm6F33GzE3TSQ4cUFIxxy-98mFyEv1v92A/edit',
    '16:00': 'https://docs.google.com/document/d/1xgteQs4n-XiDGlaya9WRHlIu-9BTsUNPEJYFu9z2R-M/edit',
    '21:00': 'https://docs.google.com/document/d/13uqhi_VC_7leV6vDmupElCQIddH13N5rTOd_Ea2Z_qM/edit'
  };
  const slots = [
    {
      time:'08:00', summary:'FOMC通過後の米金利・ドル高と、日銀会合を控えた東京市場の焦点。',
      theme:'FOMC後の米長期金利と日銀会合を控えた円相場', leadingMarket:'米国債・ドル・日本金利',
      changes:['NY市場でFOMCが25bp利上げ','米10年債は約5%近辺','前日の日経平均は63,923.00円'],
      news:['FOMCで政策金利3.75～4.00%へ','日銀金融政策決定会合は9月17～18日'],
      crossAssetFlow:['金利高・ドル高の圧力','金・BTCと米景気敏感株に重さ','原油反落がインフレ警戒を一部緩和'],
      positioning:['FOMC後のヘッジ解消と日銀会合前の再構築','前日の日経VI 28.44'],
      markets:[['金','約4,240～4,264ドル（当時の参考レンジ）','中立～やや弱気'],['WTI原油','102.43ドル（当時の参考値）','中立～やや弱気'],['日経225先物（大阪取引所）','取得不能（08:00のOSE値未照合）','中立～やや弱気'],['USD/JPY','155円台（当時の概況）','中立～ややドル高'],['EUR/USD','1.15近辺（当時の概況）','弱気寄り'],['BTCUSD','約76,000ドル（当時の概況）','弱気～中立']],
      mainScenario:'金利高・ドル高の逆風が続く一方、原油反落と日本株の市場内部が下支えする選別相場。',
      alternativeScenario:'米10年債が5%を明確に下回り円高が進まなければ、半導体買い戻しと日経平均64,000円台試し。',
      breakConditions:'米10年5.05%超、WTI106ドル超、BTC75,000ドル割れ、日経VI30超が重なる場合。',
      handover:['日経平均とTOPIXの乖離','米10年債5%攻防','円相場と日銀会合観測'],
      conclusion:'FOMC通過後も全面リスクオンではない。米金利→ドル→日本株の伝播を確認。',
      digest:'【NY市場の時系列】小売売上高を消化→FOMCが25bp利上げ→追加利上げ余地と米金利上昇を消化→Dow・S&P500は下落、Nasdaqはほぼ横ばい→金・BTCには金利高が逆風。\n【クロスチェック】当時の原本では一部朝の確定値が取得不能と明記。現在の独立再検証は未実施。'
    },
    {
      time:'12:00', summary:'日経平均は高寄り後に上げ幅縮小。ただし東証プライムは値上がり銘柄が約8割。',
      theme:'指数の失速と市場内部の強さの乖離',leadingMarket:'日本株の市場内部・米金利・ドル',
      changes:['日経平均は寄り付き64,643.58円から前引け63,966.87円へ','東証プライム値上がり1,244・値下がり252・変わらず52','TOPIXは日経平均より相対的に堅調'],
      news:['FOMC25bp利上げ後のドル高','サウジ追加供給報道でWTIが101ドル台へ','日銀会合初日'],
      crossAssetFlow:['半導体・高PERの一角から幅広い日本株へ','ドルは高値圏','金は反発、WTIは反落'],
      positioning:['朝高からの利益確定と幅広い銘柄への買い','日銀会合前の円・先物ポジション調整'],
      markets:[['金','約4,310ドル（当時の参考値）','中立～やや強気'],['WTI原油','約101.29ドル（当時の参考値）','中立～やや弱気'],['日経225先物（大阪取引所）','取得不能（12:00のOSE値未照合）','中立'],['USD/JPY','155.88～156.32円（午前レンジ）','中立～ややドル高'],['EUR/USD','1.1454～1.1473（午前レンジ）','弱気寄り'],['BTCUSD','約76,562ドル（当時の参考値）','中立～やや弱気']],
      mainScenario:'後場は日経平均64,000円近辺でもみ合い、TOPIX優位と幅広い銘柄への買いが続く。',
      alternativeScenario:'米長期金利低下と半導体の買い戻しなら朝高値方向への再上昇。',
      breakConditions:'日経平均63,900円割れ、TOPIX失速、米10年5.05%超、WTI105ドル方向が複数重なる場合。',
      handover:['後場の64,000円攻防','TOPIX優位と半導体の下げ止まり','USD/JPY156円と米10年5%'],
      conclusion:'指数だけでは全面リスクオフと判断できず、東証プライムの市場内部を重視する。',
      digest:'【東京市場で起きたこと】9時の高寄り後、利益確定で日経平均は上げ幅を大幅に縮小。一方、東証プライムは値上がり銘柄が8割超。半導体の指数押し下げと広範な買いが併存した。\n【クロスチェック】大阪日経225先物と日本10年債の12:00同時刻値などは原本で取得不能。現在の独立再検証は未実施。'
    },
    {
      time:'16:00',summary:'東京後場で日経平均が64,000円台を回復。原油反落とTOPIX優位を材料に選別相場。',
      theme:'原油高一服が米金利・日本株に与える影響',leadingMarket:'米国債・ドル・日本金利',
      changes:['前引け63,966.87円→後場寄り64,178.65円へ回復','16:00発行時点では日経平均の確定終値を複数ソースで未照合','TOPIX型の幅広い買いと資源株の弱さが併存'],
      news:['Fedの追加利上げ余地と米10年債5%攻防','日銀会合が進行、翌18日の政策発表に注目','原油の供給不安一部緩和'],
      crossAssetFlow:['ドル・短期債・一部ディフェンシブに資金が向かいやすい','高PER株・暗号資産には逆風','原油反落で資源株の勢いが鈍化'],
      positioning:['FOMCヘッジ解消とBOJヘッジ構築が併存','日本株は指数売りと幅広い銘柄買い'],
      markets:[['金','約4,300ドル（当時の概況）','中立～やや強気'],['WTI原油','約102ドル（当時の概況）','中立～やや弱気'],['日経225先物（大阪取引所）','取得不能（16:00確定値未照合）','中立'],['USD/JPY','約156円（当時の概況）','中立～ややドル高'],['EUR/USD','約1.146（当時の概況）','弱気寄り'],['BTCUSD','約76,000ドル（当時の概況）','中立～やや弱気']],
      mainScenario:'日経平均64,000円、USD/JPY156円近辺を中心に、TOPIX優位のローテーションを基本とする。',
      alternativeScenario:'米10年が5%を下回りWTIが100ドル方向なら半導体の買い戻しも。',
      breakConditions:'米10年5.05%超・WTI105ドル超・日経先物63,900円割れ・日経VI30超などが重なる場合。',
      handover:['欧州HICPと英中銀政策発表','米21:30指標','米10年5%・WTI100～103ドル・USD/JPY156円'],
      conclusion:'12:00からの変化は後場寄りの64,000円台回復。原油反落と市場内部が金利ショックを緩和。',
      digest:'【東京市場の午後】後場寄りで64,178.65円を付け、医薬品・保険などが相対的に堅調。鉱業・石油石炭・非鉄は弱い。\n【クロスチェック】16:01時点の大引け確定値・日本10年債同時刻値は原本で取得不能。現在の独立再検証は未実施。'
    },
    {
      time:'21:00',summary:'欧州時間は原油安と米長期金利低下を受け、欧州株・米株先物が持ち直す。翌日の日銀会合に注目。',
      theme:'原油安がFOMC後の金利上昇圧力をどこまで緩和するか',leadingMarket:'WTI原油・米国債・ドル',
      changes:['日経平均終値64,136.25円（+213.25円）','TOPIX終値4,094.19（+32.47）','欧州時間は原油安と米長期金利低下で株が持ち直す'],
      news:['英中銀は政策金利3.75%据え置き、投票6対3と当時報告','米長期金利は5%を下回る場面','9月18日の日銀政策判断・総裁会見が焦点'],
      crossAssetFlow:['原油は下落、債券・欧州株・米株先物に買い戻し','ドルの上昇は一服','金は4,300ドル近辺、BTCは76,000ドル台と当時報告'],
      positioning:['東京市場はTOPIX優位で33業種中28業種上昇と当時報告','円ショート・銀行株・JGBに日銀会合前の調整余地'],
      markets:[['金','約4,300ドル（当時の概況）','中立～やや強気'],['WTI原油','約100～101ドル（当時の概況）','中立～やや弱気'],['日経225先物（大阪取引所）','取得不能（21:00同時刻値未照合）','中立～やや強気'],['USD/JPY','約156円（当時の概況）','中立～ややドル高'],['EUR/USD','約1.146（当時の概況）','中立～やや弱気'],['BTCUSD','約76,000ドル（当時の概況）','中立～やや弱気']],
      mainScenario:'WTI100～103ドル・米10年5%以下が続けば、NY株はFOMC後の売りから自律反発を試す。',
      alternativeScenario:'WTI105ドル超と米10年5.05%超ならインフレ警戒再燃。逆にWTI100ドル割れ・米10年4.90%割れなら金利警戒緩和。',
      breakConditions:'米10年5.05%超、WTI105ドル超、BTC75,000ドル割れ、米株先物上昇消失が重なる場合。',
      handover:['21:30の米新規失業保険申請件数ほか','NY市場の金利・株価反応','翌18日の日銀政策判断・USD/JPY'],
      conclusion:'16時版と異なり、欧州時間の原油安→米金利低下→欧米株の持ち直しを中心に整理する。',
      digest:'【16時以降の市場】原油が100ドル近辺へ低下しインフレ警戒が後退。米10年債は5%を下回る方向で欧州株・米株先物が反発。英中銀の政策据え置きとQT減速が報じられた。\n【クロスチェック】21:30の米指標は21:00時点未公表。OSE先物等の完全同時刻値は原本で取得不能。現在の独立再検証は未実施。'
    }
  ];
  const records = slots.map(s => ({
    date:'2026-09-17',time:s.time,title:`マーケットレポート｜2026/09/17（木）${s.time}`,
    createdAt:`2026-09-17 ${s.time} JST`,sourceDocUrl:docs[s.time],
    summary:s.summary,theme:s.theme,leadingMarket:s.leadingMarket,changes:s.changes,news:s.news,
    crossAssetFlow:s.crossAssetFlow,positioning:s.positioning,
    markets:s.markets.map(([name,price,direction]) => ({name,price,direction})),
    mainScenario:s.mainScenario,alternativeScenario:s.alternativeScenario,
    breakConditions:s.breakConditions,handover:s.handover,conclusion:s.conclusion,
    fullText:`マーケットレポート｜2026/09/17（木）${s.time}\n\n【ダッシュボード用要約】\n${s.summary}\n\n【今日の相場テーマ】\n${s.theme}\n\n【前回からの変化】\n${s.changes.join('\n')}\n\n【材料と値動き・重要ニュース】\n${s.news.join('\n')}\n\n【主導市場】\n${s.leadingMarket}\n\n【クロスアセット資金フロー】\n${s.crossAssetFlow.join('\n')}\n\n【需給・ポジション】\n${s.positioning.join('\n')}\n\n【6市場の見通し】\n${s.markets.map(m=>m.join('：')).join('\n')}\n\n【メインシナリオ】\n${s.mainScenario}\n\n【代替シナリオ】\n${s.alternativeScenario}\n\n【シナリオが崩れる条件】\n${s.breakConditions}\n\n【次の時間帯への引き継ぎ】\n${s.handover.join('\n')}\n\n【結論】\n${s.conclusion}\n\n${s.digest}\n\n【原本全文・出典】\n${docs[s.time]}\n※本表示は既存Google Docsに基づく復旧用の要約です。原本全文はリンク先で確認してください。市場数値は今回独立に再検証していません。`
  }));
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async function(input, init) {
    const response = await nativeFetch(input, init);
    const url = new URL(typeof input === 'string' ? input : input.url, location.href);
    if (!/\/reports\.json$/.test(url.pathname) || !response.ok) return response;
    try {
      const payload = await response.clone().json();
      const list = Array.isArray(payload) ? payload : Array.isArray(payload?.reports) ? payload.reports : [];
      const keyed = new Map(list.filter(x=>x&&x.date&&x.time).map(x=>[`${x.date} ${x.time}`,x]));
      records.forEach(r=>keyed.set(`${r.date} ${r.time}`,r));
      const merged = [...keyed.values()].sort((a,b)=>`${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));
      const body = JSON.stringify(Array.isArray(payload) ? merged : {...payload,reports:merged});
      const headers = new Headers(response.headers);
      headers.set('content-type','application/json; charset=utf-8');
      headers.delete('content-length');
      return new Response(body,{status:response.status,statusText:response.statusText,headers});
    } catch(err) { console.error('2026-09-17 reports recovery failed',err);return response; }
  };
  window.addEventListener('market-report-rendered',e=>{
    const r=e.detail?.report;
    if(r?.date!=='2026-09-17'||!docs[r.time])return;
    const status=document.getElementById('reportStatus');
    if(status)status.textContent='ダッシュボード用要約を表示中｜原本全文はGoogle Docs';
    const head=document.querySelector('#app .report-head');
    if(head&&!head.querySelector('.source-doc-link')){
      const a=document.createElement('a');a.className='source-doc-link';a.href=docs[r.time];a.target='_blank';a.rel='noopener noreferrer';a.textContent='Google Docsで原本全文を開く';head.appendChild(a);
    }
  });
  window.MarketReportRecovery20260917={slots:records.map(r=>r.time),count:records.length,source:'Google Docs recovery summaries'};
})();