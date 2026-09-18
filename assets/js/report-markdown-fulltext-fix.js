/* Render the original report's Markdown without truncating or summarizing it. */
(() => {
  'use strict';
  const escapeHtml = (value) => String(value).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  const inline = (value) => escapeHtml(value).replace(/\\\*\\\*/g,'**').replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>');
  function markdownLines(lines) {
    const output = [];
    let paragraph = [], bullets = [];
    const flushParagraph = () => { if (paragraph.length) { output.push('<p>'+paragraph.map(inline).join('<br>')+'</p>'); paragraph=[]; } };
    const flushBullets = () => { if (bullets.length) { output.push('<ul>'+bullets.map(item=>'<li>'+inline(item)+'</li>').join('')+'</ul>'); bullets=[]; } };
    for (const raw of lines || []) {
      const line = String(raw ?? '').replace(/\r/g,'').trim();
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
