const MARKET_REPORT_HISTORY_CONFIG = {
  timezone: 'Asia/Tokyo',
  batchSize: 20,
  continuationHandler: 'continueHistoricalMarketReportImport',
  stateProperty: 'MARKET_REPORT_HISTORY_IMPORT_STATE',
  resultProperty: 'MARKET_REPORT_HISTORY_IMPORT_RESULT'
};

function startHistoricalMarketReportImport() {
  clearHistoricalImportTriggers_();
  PropertiesService.getScriptProperties().deleteProperty(MARKET_REPORT_HISTORY_CONFIG.stateProperty);
  const result = processHistoricalMarketReportBatch_();

  if (!result.finished) {
    ScriptApp.newTrigger(MARKET_REPORT_HISTORY_CONFIG.continuationHandler)
      .timeBased()
      .after(60 * 1000)
      .create();
  }

  SpreadsheetApp.getUi().alert(formatHistoricalImportResult_(result));
  return result;
}

function continueHistoricalMarketReportImport() {
  clearHistoricalImportTriggers_();
  const result = processHistoricalMarketReportBatch_();
  if (!result.finished) {
    ScriptApp.newTrigger(MARKET_REPORT_HISTORY_CONFIG.continuationHandler)
      .timeBased()
      .after(60 * 1000)
      .create();
  }
  return result;
}

function stopHistoricalMarketReportImport() {
  const deleted = clearHistoricalImportTriggers_();
  SpreadsheetApp.getUi().alert('過去レポートの自動取り込みを停止しました。削除したトリガー: ' + deleted + '件');
}

function showHistoricalMarketReportImportStatus() {
  const props = PropertiesService.getScriptProperties();
  SpreadsheetApp.getUi().alert(
    '進行状態:\n' + (props.getProperty(MARKET_REPORT_HISTORY_CONFIG.stateProperty) || '未開始') +
    '\n\n最終結果:\n' + (props.getProperty(MARKET_REPORT_HISTORY_CONFIG.resultProperty) || '実行履歴なし')
  );
}

function processHistoricalMarketReportBatch_() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  try {
    const props = PropertiesService.getScriptProperties();
    const allFiles = listHistoricalMarketReportDocs_();
    const state = JSON.parse(props.getProperty(MARKET_REPORT_HISTORY_CONFIG.stateProperty) || '{"offset":0,"imported":0,"fallback":0,"failed":0}');
    const batch = allFiles.slice(state.offset, state.offset + MARKET_REPORT_HISTORY_CONFIG.batchSize);

    if (!batch.length) {
      const finishedResult = Object.assign({}, state, { total: allFiles.length, finished: true });
      saveHistoricalImportResult_(finishedResult);
      props.deleteProperty(MARKET_REPORT_HISTORY_CONFIG.stateProperty);
      clearHistoricalImportTriggers_();
      return finishedResult;
    }

    const current = getGitHubJsonFile_(WEB_REPORT_CONFIG.targetPath);
    const reportMap = new Map((Array.isArray(current.data) ? current.data : []).map(report => [report.date + ' ' + report.time, report]));
    const errors = [];

    batch.forEach(file => {
      try {
        let report;
        let usedFallback = false;
        try {
          report = buildWebReportFromGoogleDoc_(file);
        } catch (standardError) {
          report = buildLegacyWebReportFromGoogleDoc_(file, standardError.message);
          usedFallback = true;
        }

        reportMap.set(report.date + ' ' + report.time, report);
        state.imported += 1;
        if (usedFallback) state.fallback += 1;
      } catch (error) {
        state.failed += 1;
        errors.push(file.getName() + ': ' + error.message);
      }
    });

    const nextReports = Array.from(reportMap.values())
      .sort((a, b) => (b.date + ' ' + b.time).localeCompare(a.date + ' ' + a.time));

    const firstName = batch[0].getName();
    const lastName = batch[batch.length - 1].getName();
    const commit = putGitHubJsonFile_(
      WEB_REPORT_CONFIG.targetPath,
      JSON.stringify(nextReports, null, 2) + '\n',
      current.sha,
      'Import historical market reports: ' + firstName + ' - ' + lastName
    );

    state.offset += batch.length;
    state.total = allFiles.length;
    state.finished = state.offset >= allFiles.length;
    state.lastCommitSha = commit.commit.sha;
    state.lastBatch = batch.map(file => file.getName());
    state.errors = errors;
    state.updatedAt = Utilities.formatDate(new Date(), MARKET_REPORT_HISTORY_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss');

    if (state.finished) {
      props.deleteProperty(MARKET_REPORT_HISTORY_CONFIG.stateProperty);
      clearHistoricalImportTriggers_();
    } else {
      props.setProperty(MARKET_REPORT_HISTORY_CONFIG.stateProperty, JSON.stringify(state));
    }

    saveHistoricalImportResult_(state);
    return state;
  } finally {
    lock.releaseLock();
  }
}

function listHistoricalMarketReportDocs_() {
  const query = "mimeType='application/vnd.google-apps.document' and trashed=false and title contains '" + WEB_REPORT_CONFIG.prefix + "'";
  const files = DriveApp.searchFiles(query);
  const result = [];

  while (files.hasNext()) {
    const file = files.next();
    if (!/^マーケットレポート_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}$/.test(file.getName())) continue;
    result.push(file);
  }

  return result.sort((a, b) => b.getName().localeCompare(a.getName()));
}

function buildLegacyWebReportFromGoogleDoc_(file, parseError) {
  const text = normalizeReportText_(DocumentApp.openById(file.getId()).getBody().getText());
  const meta = parseReportMetadata_(text, file.getName());
  const names = ['金', '原油', '日経225先物', 'USD/JPY', 'EUR/USD', 'BTCUSD'];

  const report = {
    date: meta.date,
    time: meta.time,
    title: meta.title,
    tags: ['過去レポート', '自動移行'],
    theme: sectionText_(text, ['今日の相場テーマ']) || firstMeaningfulLine_(text) || '過去レポート本文',
    changes: sectionLines_(text, ['前回からの変化']),
    consistency: sectionLines_(text, ['材料と値動きの整合性']),
    leadingMarket: sectionText_(text, ['今日の主導市場']) || '本文の見出し構成が旧形式のため取得不能',
    positioning: sectionLines_(text, ['需給・ポジション', 'ポジションの偏り']),
    news: sectionLines_(text, ['重要ニュースと影響', '重要ニュース', '市場を動かすニュース']),
    crossAssetFlow: sectionLines_(text, ['クロスアセット資金フロー']),
    handover: sectionLines_(text, ['NY時間への引き継ぎ', '欧州時間への引き継ぎ', '次の時間帯への引き継ぎ']),
    events: sectionLines_(text, ['今後のイベント', '重要イベント']),
    mainScenario: sectionText_(text, ['メインシナリオ']),
    alternativeScenario: sectionText_(text, ['代替シナリオ']),
    breakConditions: sectionText_(text, ['シナリオが崩れる条件', '崩れる条件']),
    riskManagement: sectionLines_(text, ['リスク管理', 'リスク要因']),
    markets: names.map(name => ({
      name: name,
      direction: '本文参照',
      material: '旧形式のため自動抽出できません。下部の原文を確認してください。',
      breakCondition: '取得不能'
    })),
    fullText: text,
    migrationNote: '標準解析に失敗したため原文保存形式で移行: ' + parseError,
    sourceDocument: {
      id: file.getId(),
      name: file.getName(),
      url: file.getUrl(),
      updatedAt: file.getLastUpdated().toISOString()
    }
  };

  return validateWebReportObject_(report);
}

function firstMeaningfulLine_(text) {
  return String(text || '').split('\n')
    .map(line => line.trim())
    .find(line => line && !/^マーケットレポート[｜_]/.test(line)) || '';
}

function clearHistoricalImportTriggers_() {
  let deleted = 0;
  ScriptApp.getProjectTriggers()
    .filter(trigger => trigger.getHandlerFunction() === MARKET_REPORT_HISTORY_CONFIG.continuationHandler)
    .forEach(trigger => {
      ScriptApp.deleteTrigger(trigger);
      deleted += 1;
    });
  return deleted;
}

function saveHistoricalImportResult_(result) {
  PropertiesService.getScriptProperties().setProperty(
    MARKET_REPORT_HISTORY_CONFIG.resultProperty,
    JSON.stringify(result, null, 2)
  );
  console.log(JSON.stringify(result));
}

function formatHistoricalImportResult_(result) {
  return [
    '過去レポートのWEB版取り込みを開始しました。',
    '対象: ' + (result.total || 0) + '件',
    '処理済み: ' + (result.offset || 0) + '件',
    '登録成功: ' + (result.imported || 0) + '件',
    '原文保存形式: ' + (result.fallback || 0) + '件',
    '失敗: ' + (result.failed || 0) + '件',
    result.finished ? '処理は完了しました。' : '残りは自動で継続処理します。'
  ].join('\n');
}
