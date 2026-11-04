/* Render the original report's Markdown without truncating or summarizing it. */
(() => {
  'use strict';
  const escapeHtml = (value) => String(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const inline = (value) => escapeHtml(value).replace(/\\\*\\\*/g,'**').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>').replace(/`([^`]+)`/g,'<code>$1</code>');
  function cells(line) {
    return String(line).trim().replace(/^\|/, '').replace(/\|$/, '')
      .split(/(?<!\\)\|/).map(value => value.trim().replace(/\\\|/g, '|'));
  }
  function alignment(line) {
    return cells(line).map(cell => {
      const value = cell.replace(/\s/g, '');
      if (!/^:?-{3,}:?$/.test(value)) return null;
      return value.startsWith(':') && value.endsWith(':') ? 'center'
        : value.endsWith(':') ? 'right' : 'left';
    });
  }
  function isTableStart(line, next) {
    if (!String(line || '').includes('|') || !String(next || '').includes('|')) return false;
    const aligns = alignment(next);
    return aligns.length > 0 && aligns.every(Boolean) && aligns.length === cells(line).length;
  }
  function renderTable(headerLine, separatorLine, bodyLines) {
    const headers = cells(headerLine), aligns = alignment(separatorLine);
    const head = headers.map((value, index) => '<th scope="col" style="text-align:' + aligns[index] + '">' + inline(value) + '</th>').join('');
    const rows = bodyLines.map(line => {
      const values = cells(line);
      return '<tr>' + headers.map((_, index) => '<td style="text-align:' + aligns[index] + '">' + inline(values[index] ?? '') + '</td>').join('') + '</tr>';
    }).join('');
    const widthClass = headers.length === 5 ? ' market-table-five' : '';
    return '<div class="market-table-wrap markdown-table-wrap"><table class="market-table markdown-table' + widthClass + '"><thead><tr>' + head + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }
  function markdownLines(lines) {
    const output = [];
    let paragraph = [], bullets = [];
    const flushParagraph = () => { if (paragraph.length) { output.push('<p>'+paragraph.map(inline).join('<br>')+'</p>'); paragraph=[]; } };
    const flushBullets = () => { if (bullets.length) { output.push('<ul>'+bullets.map(item=>'<li>'+inline(item)+'</li>').join('')+'</ul>'); bullets=[]; } };
    const source = lines || [];
    for (let index = 0; index < source.length; index++) {
      const line = String(source[index] ?? '').replace(/\r/g,'').trim();
      const next = String(source[index + 1] ?? '').replace(/\r/g,'').trim();
      if (isTableStart(line, next)) {
        flushParagraph(); flushBullets();
        const body = [];
        index += 2;
        for (; index < source.length; index++) {
          const row = String(source[index] ?? '').replace(/\r/g,'').trim();
          if (!row || !row.includes('|')) { index--; break; }
          body.push(row);
        }
        output.push(renderTable(line, next, body));
        continue;
      }
      if (!line) { flushParagraph(); flushBullets(); continue; }
      if (/^(?:---+|___+)$/.test(line)) { flushParagraph(); flushBullets(); output.push('<hr>'); continue; }
      const heading = line.match(/^#{1,6}\s+(.+)$/);
      if (heading) { flushParagraph(); flushBullets(); output.push('<h3>'+inline(heading[1])+'</h3>'); continue; }
      const bullet = line.match(/^(?:[-*]\s+|[・●■▶]\s*)(.+)$/);
      if (bullet) { flushParagraph(); bullets.push(bullet[1]); continue; }
      flushBullets(); paragraph.push(line);
    }
    flushParagraph(); flushBullets();
    return output.join('');
  }
  if (typeof renderRichText === 'function') renderRichText = markdownLines;
  if (typeof renderPreface === 'function') renderPreface = markdownLines;
})();
