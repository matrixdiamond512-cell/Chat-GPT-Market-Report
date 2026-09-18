/* Load all four original reports and restore the morning previous-close table. */
(()=>{
const original=window.fetch.bind(window);
const missing='取得不能（原文で同一基準日の確定値未照合）';
const row=(label,value=missing,change='—',rate='—',direction='確認不能')=>({label,value,change,rate,direction});
const morningRows=[
row('NYダウ','51,778.04','—','+0.61%','上昇'),
row('NASDAQ総合','26,418.30','—','+1.69%','上昇'),
row('S&P500','7,637.76','—','+1.14%','上昇'),
row('Russell 2000','2,874.63','—','+0.55%','上昇'),
row('日経225現物','64,136.25','+213.25','+0.33%','上昇'),
row('CME日経225先物・円建て'),row('CME日経225先物・ドル建て'),
row('日経225先物（大阪取引所）','64,840（9/18 06:14、12月限）','+640','約+1.00%','上昇・前営業日終値ではなく早朝参考値'),
row('USD/JPY','155.94（9/18 06:14参考値）','—','—','早朝参考値'),
row('EUR/USD','1.14840（9/18 06:14参考値）','—','—','早朝参考値'),
row('COMEX金先物'),
row('スポット金','4,380.60ドル（9/18 06:14参考値）','—','—','早朝参考値'),
row('WTI原油','101.09ドル（9/18 06:14参考値）','—','—','早朝参考値'),
row('BTCUSD','76,445ドル（9/18 06:14参考値）','—','—','早朝参考値'),
row('VIX','約15.5（9/17）','—','—','低下'),
row('日経VI','28.15（9/17）'),
row('Fear & Greed Index','29（9/18 05:55）','—','—','Fear'),
row('米10年債利回り','約4.93～4.95%（9/17終盤）','—','—','低下'),
row('日本10年国債利回り','3%近辺（9/17）'),
row('日経225予想PER'),row('日経225 PBR'),row('日経225予想EPS'),
row('日経225 25日移動平均乖離率'),row('日経225 200日移動平均乖離率'),
row('東証プライム売買代金'),row('東証プライム売買高'),
row('東証プライム値上がり銘柄数'),row('東証プライム値下がり銘柄数'),row('東証プライム25日騰落レシオ')
];
window.fetch=async function(input,init){
 const url=String(input instanceof Request?input.url:input);
 if(!/(?:^|\/)reports\.json(?:\?|$)/.test(url))return original(input,init);
 const response=await original(input,init);let payload;
 try{payload=await response.clone().json()}catch{payload=[]}
 const list=Array.isArray(payload)?payload:Array.isArray(payload?.reports)?payload.reports:[];
 const files=['08-00','12-00','16-00','21-00'];
 const full=await Promise.all(files.map(time=>original('reports/2026-09-18_'+time+'.json?ts='+Date.now(),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Full report HTTP '+r.status);return r.json()})));
 const morning=full.find(r=>r.time==='08:00');
 if(morning)morning.marketDataTable={semantics:'previous_close',dataDate:'2026-09-17',columns:['項目','終値・値','前日比','騰落率','方向感'],rows:morningRows};
 const merged=[...list.filter(r=>!full.some(f=>r.date===f.date&&r.time===f.time)),...full];
 return new Response(JSON.stringify(Array.isArray(payload)?merged:{...payload,reports:merged}),{status:200,headers:{'Content-Type':'application/json'}});
};
})();