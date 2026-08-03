const WEB_REPORT_CONFIG={owner:'matrixdiamond512-cell',repo:'Chat-GPT-Market-Report',branch:'main',targetPath:'reports.json',pagesUrl:'https://matrixdiamond512-cell.github.io/Chat-GPT-Market-Report/',prefix:'マーケットレポート_'};

function showWebReportSidebar(){SpreadsheetApp.getUi().showSidebar(HtmlService.createHtmlOutputFromFile('MarketReportSidebar').setTitle('WEB版レポート登録'));}
function publishWebReport(text){return publishWebReportObject_(parseAndValidateWebReport_(text));}
function previewWebReport(text){return parseAndValidateWebReport_(text);}

function publishLatestMarketReportFromDrive(){
  const file=findLatestMarketReportDoc_();
  const report=buildWebReportFromGoogleDoc_(file);
  const result=publishWebReportObject_(report);
  SpreadsheetApp.getUi().alert(
    'WEB版へ反映しました。\n' +
    '元文書: '+file.getName()+'\n' +
    'レポート: '+result.commitSha+'\n' +
    'ダッシュボード: '+(result.dashboardCommitSha || '未更新')
  );
  return result;
}

function previewLatestMarketReportFromDrive(){
  const file=findLatestMarketReportDoc_();
  const report=buildWebReportFromGoogleDoc_(file);
  const html=HtmlService.createHtmlOutput('<p><b>元文書:</b> '+escapeWebHtml_(file.getName())+'</p><pre style="white-space:pre-wrap;font-size:12px">'+escapeWebHtml_(JSON.stringify(report,null,2))+'</pre>').setWidth(840).setHeight(680);
  SpreadsheetApp.getUi().showModalDialog(html,'最新Google Docs → WEB版プレビュー');
}

function publishMarketReportFromDocUrlPrompt(){
  const ui=SpreadsheetApp.getUi();
  const res=ui.prompt('Google DocsからWEB版へ反映','Google Docs URLまたはファイルIDを入力してください。',ui.ButtonSet.OK_CANCEL);
  if(res.getSelectedButton()!==ui.Button.OK)return;
  const file=DriveApp.getFileById(extractDriveId_(res.getResponseText()));
  const result=publishWebReportObject_(buildWebReportFromGoogleDoc_(file));
  ui.alert('WEB版へ反映しました。\n元文書: '+file.getName()+'\nコミット: '+result.commitSha);
}

function publishWebReportObject_(report){
  report=validateWebReportObject_(report);
  const lock=LockService.getScriptLock();lock.waitLock(30000);
  try{
    const current=getGitHubJsonFile_(WEB_REPORT_CONFIG.targetPath);
    const reports=normalizeWebReportList_(current.data);
    const key=report.date+' '+report.time;
    const next=upsertWebReportList_(reports,report);
    const result=putGitHubJsonFile_(WEB_REPORT_CONFIG.targetPath,JSON.stringify(next,null,2)+'\n',current.sha,'Publish market report '+key);
    const dashboardResult=typeof syncDashboardJsonToGitHubFromReports_==='function'
      ? syncDashboardJsonToGitHubFromReports_(next)
      : null;
    return{ok:true,title:report.title,date:report.date,time:report.time,commitSha:result.commit.sha,dashboardCommitSha:dashboardResult?dashboardResult.commitSha:'',pagesUrl:WEB_REPORT_CONFIG.pagesUrl};
  }finally{lock.releaseLock();}
}

function normalizeWebReportList_(data){
  let list=[];
  if(Array.isArray(data)){
    list=data;
  }else if(data&&Array.isArray(data.reports)){
    list=data.reports;
  }else if(data&&data.latestReport){
    list=[data.latestReport];
  }else if(data&&data.date&&data.time){
    list=[data];
  }
  return list.filter(x=>x&&/^\d{4}-\d{2}-\d{2}$/.test(String(x.date||''))&&/^\d{2}:\d{2}$/.test(String(x.time||'')));
}

function upsertWebReportList_(reports,report){
  const key=report.date+' '+report.time;
  const next=normalizeWebReportList_(reports).filter(x=>(x.date+' '+x.time)!==key);
  next.push(report);
  next.sort((a,b)=>(b.date+' '+b.time).localeCompare(a.date+' '+a.time));
  return next;
}

function parseAndValidateWebReport_(text){
  let report;
  try{report=JSON.parse(String(text||'').trim());}catch(e){throw new Error('JSON形式が正しくありません。'+e.message);}
  if(Array.isArray(report)){if(report.length!==1)throw new Error('1件のレポートだけを貼り付けてください。');report=report[0];}
  return validateWebReportObject_(report);
}

function validateWebReportObject_(report){
  if(!report||typeof report!=='object')throw new Error('レポートオブジェクトがありません。');
  ['date','time','title','theme','leadingMarket','markets'].forEach(k=>{if(report[k]===undefined||report[k]===null||report[k]==='')throw new Error('必須項目がありません: '+k);});
  if(!/^\d{4}-\d{2}-\d{2}$/.test(report.date))throw new Error('date は YYYY-MM-DD 形式にしてください。');
  if(!/^\d{2}:\d{2}$/.test(report.time))throw new Error('time は HH:MM 形式にしてください。');
  const required=['金','原油','日経225先物','USD/JPY','EUR/USD','BTCUSD'];
  const names=(report.markets||[]).map(x=>x&&x.name).filter(Boolean);
  const missing=required.filter(x=>!names.includes(x));
  if(missing.length)throw new Error('必須市場が不足しています: '+missing.join('、'));
  report.tags=Array.isArray(report.tags)?report.tags:[];
  ['changes','consistency','positioning','news','handover','crossAssetFlow','sectors','events','riskManagement'].forEach(k=>{if(report[k]!==undefined&&!Array.isArray(report[k]))report[k]=[report[k]];});
  return report;
}

function findLatestMarketReportDoc_(){
  const q="mimeType='application/vnd.google-apps.document' and trashed=false and title contains '"+WEB_REPORT_CONFIG.prefix+"'";
  const files=DriveApp.searchFiles(q);let latest=null;
  while(files.hasNext()){
    const f=files.next();
    if(!/^マーケットレポート_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$/.test(f.getName()))continue;
    if(!latest||f.getLastUpdated().getTime()>latest.getLastUpdated().getTime())latest=f;
  }
  if(!latest)throw new Error('マーケットレポートのGoogle Docsが見つかりません。');
  return latest;
}

function buildWebReportFromGoogleDoc_(file){
  const text=normalizeReportText_(DocumentApp.openById(file.getId()).getBody().getText());
  const meta=parseReportMetadata_(text,file.getName());
  const report={
    date:meta.date,time:meta.time,title:meta.title,
    tags:['ドル円','ユーロドル','日経225先物','金','原油','BTCUSD'],
    theme:sectionText_(text,['今日の相場テーマ']),
    changes:sectionLines_(text,['前回からの変化','12:00・16:00からの変化','12:00からの変化','16:00からの変化']),
    consistency:sectionLines_(text,['材料と値動きの整合性']),
    leadingMarket:sectionText_(text,['今日の主導市場'])||'本文から取得不能',
    positioning:sectionLines_(text,['需給・ポジション','ポジションの偏り']),
    news:sectionLines_(text,['重要ニュースと影響','重要ニュース','市場を動かすニュース']),
    crossAssetFlow:sectionLines_(text,['クロスアセット資金フロー']),
    handover:sectionLines_(text,['NY時間への引き継ぎ','欧州時間への引き継ぎ','次の時間帯への引き継ぎ']),
    events:sectionLines_(text,['今後のイベント','重要イベント']),
    mainScenario:sectionText_(text,['メインシナリオ']),
    alternativeScenario:sectionText_(text,['代替シナリオ']),
    breakConditions:sectionText_(text,['シナリオが崩れる条件','崩れる条件']),
    riskManagement:sectionLines_(text,['リスク管理','リスク要因']),
    markets:parseMarkets_(text),
    sources:sectionLines_(text,['主な確認情報源','情報源']).map(x=>({name:x}))
  };
  if(!report.theme)throw new Error('「今日の相場テーマ」を本文から取得できません。');
  return validateWebReportObject_(report);
}

function parseReportMetadata_(text,name){
  const m=text.match(/マーケットレポート｜(\d{4})\/(\d{2})\/(\d{2})（[^）]+）(\d{2}):(\d{2})/);
  if(m)return{date:m[1]+'-'+m[2]+'-'+m[3],time:m[4]+':'+m[5],title:m[0]};
  const f=name.match(/^マーケットレポート_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})$/);
  if(!f)throw new Error('タイトルまたはファイル名から日時を取得できません。');
  return{date:f[1]+'-'+f[2]+'-'+f[3],time:f[4]+':'+f[5],title:'マーケットレポート｜'+f[1]+'/'+f[2]+'/'+f[3]+' '+f[4]+':'+f[5]};
}

function parseMarkets_(text){
  const defs=[
    {name:'金',aliases:['金','ゴールド']},{name:'原油',aliases:['WTI原油','原油','WTI']},
    {name:'日経225先物',aliases:['日経225先物（大阪取引所）','日経225先物']},
    {name:'USD/JPY',aliases:['USD/JPY','ドル円']},{name:'EUR/USD',aliases:['EUR/USD','ユーロドル']},
    {name:'BTCUSD',aliases:['BTCUSD','BTC/USD','ビットコイン']}
  ];
  return defs.map(d=>{
    const b=marketBlock_(text,d.aliases);if(!b)throw new Error('個別見通しを取得できません: '+d.name);
    return{name:d.name,direction:fieldValue_(b,['方向','方向性'])||'取得不能',price:fieldValue_(b,['現状','価格','現在値']),change:fieldValue_(b,['前日比','変化']),material:fieldValue_(b,['材料']),positioning:fieldValue_(b,['需給','ポジション']),levels:fieldValue_(b,['注目水準','水準','サポート・レジスタンス']),mainScenario:fieldValue_(b,['メインシナリオ','見通し']),alternativeScenario:fieldValue_(b,['代替シナリオ']),breakCondition:fieldValue_(b,['崩れる条件']),risk:fieldValue_(b,['リスク'])};
  });
}

function marketBlock_(text,aliases){
  const p=new RegExp('(?:^|\\n)\\s*(?:■|●|◆|◇|・)?\\s*(?:'+aliases.map(escapeRegExp_).join('|')+')\\s*\\n([\\s\\S]*?)(?=\\n\\s*(?:■|●|◆|◇)\\s*|\\n【|$)','i');
  const m=text.match(p);return m?m[1].trim():'';
}
function fieldValue_(block,labels){for(const l of labels){const m=block.match(new RegExp('(?:^|\\n)\\s*'+escapeRegExp_(l)+'\\s*[：:]\\s*([^\\n]+)','i'));if(m)return m[1].trim();}return'';}
function sectionText_(text,heads){return sectionBlock_(text,heads).replace(/\n+/g,' ').replace(/\s+/g,' ').trim();}
function sectionLines_(text,heads){const b=sectionBlock_(text,heads);return b?b.split('\n').map(x=>x.replace(/^\s*(?:[-・●■◆◇]|\d+[.)．、])\s*/,'').trim()).filter(Boolean):[];}
function sectionBlock_(text,heads){for(const h of heads){const m=text.match(new RegExp('【\\s*'+escapeRegExp_(h)+'\\s*】\\s*\\n?([\\s\\S]*?)(?=\\n\\s*【|$)','i'));if(m)return m[1].trim();}return'';}
function normalizeReportText_(text){return String(text||'').replace(/\r\n?/g,'\n').replace(/\u00a0/g,' ').replace(/[ \t]+\n/g,'\n').replace(/\n{3,}/g,'\n\n').trim();}
function extractDriveId_(v){const m=String(v||'').trim().match(/[-\w]{25,}/);if(!m)throw new Error('Google Docs URLまたはファイルIDを確認してください。');return m[0];}
function escapeRegExp_(s){return String(s).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}
function escapeWebHtml_(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');}

function getGitHubJsonFile_(path){
  const token=getGitHubToken_();
  const r=UrlFetchApp.fetch(githubContentsUrl_(path)+'?ref='+encodeURIComponent(WEB_REPORT_CONFIG.branch),{method:'get',headers:githubHeaders_(token),muteHttpExceptions:true});
  const c=r.getResponseCode();if(c===404)return{data:[],sha:null};if(c!==200)throw new Error('GitHubファイル取得失敗: HTTP '+c+' '+r.getContentText());
  const p=JSON.parse(r.getContentText());return{data:JSON.parse(Utilities.newBlob(Utilities.base64Decode(p.content)).getDataAsString('UTF-8')),sha:p.sha};
}
function putGitHubJsonFile_(path,content,sha,message){
  const payload={message:message,content:Utilities.base64Encode(content,Utilities.Charset.UTF_8),branch:WEB_REPORT_CONFIG.branch};if(sha)payload.sha=sha;
  const r=UrlFetchApp.fetch(githubContentsUrl_(path),{method:'put',contentType:'application/json',headers:githubHeaders_(getGitHubToken_()),payload:JSON.stringify(payload),muteHttpExceptions:true});
  const c=r.getResponseCode();if(c!==200&&c!==201)throw new Error('GitHub更新失敗: HTTP '+c+' '+r.getContentText());return JSON.parse(r.getContentText());
}
function getGitHubToken_(){const t=PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');if(!t)throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定です。');return t;}
function githubContentsUrl_(path){return'https://api.github.com/repos/'+WEB_REPORT_CONFIG.owner+'/'+WEB_REPORT_CONFIG.repo+'/contents/'+path;}
function githubHeaders_(token){return{Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'};}
