/* Shared display-only adapter. Source records and publication gates stay immutable. */
(function (global) {
  const formal = r => [r.originalReportStatus,r.report_status,r.publicationStatus,r.status].some(s => /^(?:PUBLISHED|FORMALLY_PUBLISHED)$/.test(s || ''));
  function normalize(record, folder) {
    if (!record || formal(record) || !/^\d{4}-\d{2}-\d{2}$/.test(record.date || '') ||
        !['08:00','12:00','16:00','21:00'].includes(record.time) || typeof record.fullText !== 'string' || record.fullText.length < 250) return null;
    if (record.sourceFolderId && record.sourceFolderId !== folder) return null;
    const body = record.fullText.replace(/^\uFEFF/, '').replace(/^#{1,3}\s+/, '');
    if (!record.title || !body.startsWith(record.title) || !record.title.includes(record.date.replace(/-/g,'/')) || !record.title.endsWith(record.time)) return null;
    const source = record.sourceDocument;
    const url = typeof source === 'string' ? source : source?.url;
    const urlId = /^https:\/\/docs\.google\.com\/document\/d\/([A-Za-z0-9_-]+)(?:[/?#]|$)/.exec(url || '')?.[1];
    const id = typeof source === 'object' ? source?.id || source?.fileId || record.retrospectiveGoogleDocId || urlId : urlId;
    const revision = record.driveRevisionId || record.revision || source?.revision;
    if (!id || !revision || (url && (!urlId || urlId !== id))) return null;
    if (record.driveTextLength != null && record.driveTextLength !== record.fullText.length) return null;
    const reference = /HISTORICAL_ARCHIVE_NOT_OFFICIAL_PUBLICATION|REFERENCE|NOT_VERIFIED|NOT_FORMALLY_PUBLISHED|ANALYSIS_VIEW_ONLY|閲覧用分析版|NOT_SLOT_VERIFIED|PUBLICATION_PENDING|ORIGINAL_NOT_FOUND/.test(
      [record.archiveType,record.originalReportStatus,record.publicationStatus,record.status].join(' '));
    const heldReadback = record.originalReportStatus === 'BLOCKED_PRE_DRAFT_EVIDENCE_MISSING' &&
      record.verifiedAtSlot === false && (
        (record.archiveType === 'DRIVE_READBACK_ANALYSIS' && record.archiveStatus === 'HISTORICAL_ARCHIVE') ||
        (record.archiveType === 'GOOGLE_DOCS_READBACK' && record.archiveStatus === 'REFERENCE_ANALYSIS_NOT_OFFICIAL')
      );
    if (!reference && !heldReadback) return null;
    // Contradictory legacy slot verification is usable only as a conservative view.
    return {...record, sourceDocument: {...(typeof source === 'object' ? source : {}),id,url:url || 'https://docs.google.com/document/d/'+id+'/edit'},
      driveRevisionId:revision, driveTextLength:record.fullText.length,
      archiveStatus:'HISTORICAL_ARCHIVE', verifiedAtSlot:false,
      archiveNotice:record.archiveNotice || '保存済み本文の参考閲覧版。正式発行・当該時刻の価格検証は未確認です。',
      historicalArchiveDisplayOnly:true};
  }
  global.MarketReportArchiveSource = {normalize};
})(window);
