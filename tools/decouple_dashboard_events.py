from pathlib import Path

PATH = Path('apps-script/DashboardJsonSync.gs')


def replace_section(text, start_marker, end_marker, replacement):
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError('start marker not found: ' + start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError('end marker not found: ' + end_marker)
    return text[:start] + replacement.rstrip() + '\n\n' + text[end:]


text = PATH.read_text(encoding='utf-8')
first_line_end = text.find('\n')
if first_line_end >= 0 and text.startswith('// Root-fix version:'):
    text = '// Root-fix version: 2026-08-06 14:10 JST' + text[first_line_end:]

sync_main = r'''function syncDashboardJsonToGitHub() {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var reports = dashboardFetchReportsJson_();
    var result = syncDashboardJsonToGitHubFromReports_(reports);
    dashboardAlert_(
      'ダッシュボードJSONをGitHubへ反映しました。\n' +
      '対象: ' + result.latestKey + '\n' +
      '件数: ' + result.reportCount + '\n' +
      'コミット: ' + result.commitSha
    );
    return result;
  } catch (error) {
    dashboardSaveResult_({ ok: false, error: error.message });
    dashboardAlert_('ダッシュボードJSONを反映できませんでした。\n' + error.message);
    throw error;
  } finally {
    lock.releaseLock();
  }
}'''
text = replace_section(
    text,
    'function syncDashboardJsonToGitHub() {',
    'function syncDashboardJsonToGitHubFromReports_',
    sync_main,
)

sync_from_reports = r'''function syncDashboardJsonToGitHubFromReports_(reports) {
  var payload = dashboardBuildPayloadFromReports_(reports);
  var json = JSON.stringify(payload, null, 2) + '\n';
  var current = dashboardGetGitHubJsonFile_(DASHBOARD_JSON_CONFIG.targetPath);
  var result = dashboardPutGitHubJsonFile_(
    DASHBOARD_JSON_CONFIG.targetPath,
    json,
    current.sha,
    'Update dashboard JSON from market reports'
  );
  return dashboardSaveResult_({
    ok: true,
    targetPath: DASHBOARD_JSON_CONFIG.targetPath,
    latestKey: payload.currentReportKey,
    reportCount: payload.reports.length,
    commitSha: result.commit.sha
  });
}'''
text = replace_section(
    text,
    'function syncDashboardJsonToGitHubFromReports_(reports) {',
    'function buildDashboardJsonFromReports_',
    sync_from_reports,
)

PATH.write_text(text, encoding='utf-8')
print('Decoupled dashboard JSON sync from event JSON sync.')
