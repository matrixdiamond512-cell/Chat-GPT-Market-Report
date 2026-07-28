(() => {
  const byId = id => document.getElementById(id);
  const usSectorsEl = byId('dashboardUsSectors');
  const jpSectorsEl = byId('dashboardJapanSectors');
  const nikkeiEl = byId('dashboardNikkeiContributors');
  const usMoversEl = byId('dashboardUsMovers');
  const conclusionEl = byId('dashboardConclusion');
  const riskEl = byId('dashboardRisk');
  const latestEl = byId('latestReport');
  if (!usSectorsEl || !jpSectorsEl || !nikkeiEl || !usMoversEl) return;

  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const textOf = item => typeof item === 'string' ? item : (item?.text || item?.summary || item?.title || item?.name || '');
  const clean = value => String(value || '').replace(/\s+/g, ' ').trim();
  const escapeHtml = value => String(value || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const direction = value => {
    const t = String(value || '').toLowerCase();
    if (/上昇|値上がり|プラス|買い|堅調|反発|up|gain|positive/.test(t)) return 'up';
    if (/下落|値下がり|マイナス|売り|軟調|反落|down|loss|negative/.test(t)) return 'down';
    return 'neutral';
  };

  function getCurrentReport() {
    const source = typeof reports !== 'undefined' && Array.isArray(reports) ? reports : [];
    if (!source.length) return null;
    if (typeof selectedKey !== 'undefined' && selectedKey) {
      const found = source.find(r => `${r.date} ${r.time}` === selectedKey);
      if (found) return found;
    }
    return source[0];
  }

  function normalizeRows(value) {
    return arr(value).map(item => {
      if (typeof item === 'string') return { name: clean(item), note: '', value: '', direction: '' };
      return {
        name: clean(item?.name || item?.title || item?.sector || item?.industry || item?.ticker || item?.symbol || item?.stock),
        note: clean(item?.reason || item?.note || item?.material || item?.summary || item?.description),
        value: clean(item?.change || item?.rate || item?.contribution || item?.value || item?.percent),
        direction: clean(item?.direction || '')
      };
    }).filter(row => row.name);
  }

  function extractLines(report, includePatterns, excludePatterns = []) {
    const raw = [report?.fullText, ...arr(report?.sectors).map(textOf), ...arr(report?.news).map(textOf)].filter(Boolean).join('\n');
    return raw.split(/\n+/).map(clean).filter(line => line.length >= 4 && includePatterns.some(p => p.test(line)) && !excludePatterns.some(p => p.test(line)));
  }

  function uniqueRows(rows, limit = 8) {
    const seen = new Set();
    return rows.filter(row => {
      const key = clean(row.name || row).toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, limit);
  }

  function sectorRows(report, market) {
    const keys = market === 'us'
      ? ['usSectors','usSectorPerformance','usIndustries','americanSectors']
      : ['japanSectors','tokyoSectors','japanIndustries','tseSectors'];
    for (const key of keys) {
      const rows = normalizeRows(report?.[key]);
      if (rows.length) return uniqueRows(rows, 10);
    }
    const found = extractLines(report,
      market === 'us'
        ? [/米国.*(?:セクター|業種)/, /S&P.?500.*(?:セクター|業種)/i, /SOX|NASDAQ100|ラッセル2000|Russell 2000/i, /米株.*(?:買われ|売られ)/]
        : [/東京市場.*(?:セクター|業種)/, /東証.*(?:業種|セクター)/, /日本株.*(?:買われ|売られ)/, /銀行|商社|海運|自動車|電機|半導体|医薬品|小売|不動産/],
      market === 'us' ? [/東京|東証|日経/] : [/米国|S&P|NASDAQ|SOX|Russell/i]
    );
    return uniqueRows(found.map(line => ({name:line,note:'',value:'',direction:direction(line)})),10);
  }

  function contributorRows(report, positive) {
    const keys = positive
      ? ['nikkeiPositiveContributors','nikkeiPlusContributors','positiveContributors','nikkeiContributorsUp']
      : ['nikkeiNegativeContributors','nikkeiMinusContributors','negativeContributors','nikkeiContributorsDown'];
    for (const key of keys) {
      const rows = normalizeRows(report?.[key]);
      if (rows.length) return uniqueRows(rows, 8);
    }
    const found = extractLines(report, positive
      ? [/寄与度.*(?:プラス|上位)/, /プラス寄与/, /押し上げ寄与/, /日経.*押し上げ/]
      : [/寄与度.*(?:マイナス|下位)/, /マイナス寄与/, /押し下げ寄与/, /日経.*押し下げ/]);
    return uniqueRows(found.map(line => ({name:line,note:'',value:'',direction:positive?'up':'down'})),8);
  }

  function moverRows(report, gainers) {
    const keys = gainers
      ? ['usGainers','usTopGainers','usStockGainers','americanGainers']
      : ['usLosers','usTopLosers','usStockLosers','americanLosers'];
    for (const key of keys) {
      const rows = normalizeRows(report?.[key]);
      if (rows.length) return uniqueRows(rows, 8);
    }
    const found = extractLines(report, gainers
      ? [/米国.*(?:大幅上昇|値上がり|上昇率上位)/, /S&P.*上昇率上位/i, /NASDAQ.*上昇率上位/i]
      : [/米国.*(?:大幅下落|値下がり|下落率上位)/, /S&P.*下落率上位/i, /NASDAQ.*下落率上位/i]);
    return uniqueRows(found.map(line => ({name:line,note:'',value:'',direction:gainers?'up':'down'})),8);
  }

  function renderRows(rows, emptyText) {
    if (!rows.length) return `<p class="market-depth-empty">${escapeHtml(emptyText)}</p><span class="source-status is-missing">原文に該当データなし</span>`;
    return `<div class="market-depth-list">${rows.map((row,i) => `<div class="market-depth-row">
      <span class="market-depth-rank">${i+1}</span>
      <span class="market-depth-main"><strong>${escapeHtml(row.name)}</strong>${row.note?`<small>${escapeHtml(row.note)}</small>`:''}</span>
      ${row.value?`<span class="market-depth-value ${direction(row.direction||row.value||row.name)}">${escapeHtml(row.value)}</span>`:''}
    </div>`).join('')}</div><span class="source-status is-available">レポート原文から表示</span>`;
  }

  function renderSplit(leftTitle,leftRows,rightTitle,rightRows,leftEmpty,rightEmpty) {
    return `<div class="market-depth-columns">
      <section class="market-depth-column"><h4>${escapeHtml(leftTitle)}</h4>${renderRows(leftRows,leftEmpty)}</section>
      <section class="market-depth-column"><h4>${escapeHtml(rightTitle)}</h4>${renderRows(rightRows,rightEmpty)}</section>
    </div>`;
  }

  function readerRows(rows,emptyText) {
    if (!rows.length) return `<p class="report-reader-empty">${escapeHtml(emptyText)}</p>`;
    return `<ul>${rows.map(row=>`<li><strong>${escapeHtml(row.name)}</strong>${row.value?` <span class="market-depth-value ${direction(row.direction||row.value||row.name)}">${escapeHtml(row.value)}</span>`:''}${row.note?` — ${escapeHtml(row.note)}`:''}</li>`).join('')}</ul>`;
  }

  function articleInternals(report) {
    const us=sectorRows(report,'us'), jp=sectorRows(report,'jp');
    const plus=contributorRows(report,true), minus=contributorRows(report,false);
    const gain=moverRows(report,true), loss=moverRows(report,false);
    return `<section class="report-reader-section report-internals-v2" id="reader-internals">
      <h2>9. セクター・業種・個別銘柄</h2>
      <div class="report-reader-copy">
        <h3>米国市場｜セクター・業種</h3>${readerRows(us,'記載なし')}
        <h3>東京市場｜セクター・業種</h3>${readerRows(jp,'記載なし')}
        <h3>日経225｜プラス寄与度上位</h3>${readerRows(plus,'記載なし')}
        <h3>日経225｜マイナス寄与度上位</h3>${readerRows(minus,'記載なし')}
        <h3>米国市場｜大幅上昇銘柄</h3>${readerRows(gain,'記載なし')}
        <h3>米国市場｜大幅下落銘柄</h3>${readerRows(loss,'記載なし')}
      </div>
    </section>`;
  }

  function summaryInternals(report) {
    return `<section class="report-summary-panel report-summary-panel--wide report-internals-v2">
      <h4>セクター・業種・個別銘柄</h4>
      <div class="report-summary-split">
        <div><h5>米国市場</h5>${readerRows(sectorRows(report,'us').slice(0,5),'記載なし')}<h5>大幅上昇・下落銘柄</h5>${readerRows([...moverRows(report,true).slice(0,3),...moverRows(report,false).slice(0,3)],'記載なし')}</div>
        <div><h5>東京市場</h5>${readerRows(sectorRows(report,'jp').slice(0,5),'記載なし')}<h5>日経225寄与度上位</h5>${readerRows([...contributorRows(report,true).slice(0,3),...contributorRows(report,false).slice(0,3)],'記載なし')}</div>
      </div>
    </section>`;
  }

  function injectIntoReport(report) {
    if (!latestEl || !report || latestEl.querySelector('.report-internals-v2')) return;
    const reader = latestEl.querySelector('.report-reader');
    if (reader) {
      const markets = reader.querySelector('#reader-markets');
      const node=document.createElement('div'); node.innerHTML=articleInternals(report);
      reader.insertBefore(node.firstElementChild,markets||null);
      const toc=reader.querySelector('.report-reader-toc');
      if(toc&&!toc.querySelector('[href="#reader-internals"]')) toc.insertAdjacentHTML('beforeend','<a href="#reader-internals">セクター・個別株</a>');
      return;
    }
    const summaryGrid=latestEl.querySelector('.report-summary-grid');
    if(summaryGrid) summaryGrid.insertAdjacentHTML('beforeend',summaryInternals(report));
  }

  function render(report) {
    if (!report) return;
    if(conclusionEl) conclusionEl.textContent=clean(report.mainScenario||report.conclusion||report.outlook||'記載なし');
    if(riskEl) riskEl.textContent=clean(report.breakConditions||arr(report.riskManagement).map(textOf)[0]||'記載なし');
    usSectorsEl.innerHTML=renderRows(sectorRows(report,'us'),'米国市場のセクター・業種データが本文にありません。');
    jpSectorsEl.innerHTML=renderRows(sectorRows(report,'jp'),'東京市場のセクター・業種データが本文にありません。');
    nikkeiEl.innerHTML=renderSplit('プラス寄与度上位',contributorRows(report,true),'マイナス寄与度上位',contributorRows(report,false),'プラス寄与度データなし','マイナス寄与度データなし');
    usMoversEl.innerHTML=renderSplit('大幅上昇銘柄',moverRows(report,true),'大幅下落銘柄',moverRows(report,false),'米国上昇銘柄データなし','米国下落銘柄データなし');
    injectIntoReport(report);
  }

  const observer = latestEl ? new MutationObserver(()=>setTimeout(()=>render(getCurrentReport()),0)) : null;
  if(observer) observer.observe(latestEl,{childList:true,subtree:false});

  const timer=setInterval(()=>{const report=getCurrentReport();if(!report)return;clearInterval(timer);render(report);},120);
  setTimeout(()=>clearInterval(timer),12000);
})();