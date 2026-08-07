/*
 * Decimal values such as 77.29, 15.15, 29.78 and 4.670% must never be
 * interpreted as numbered section headings. A plain numbered heading is
 * valid only when whitespace follows the period, for example "1. 市場概況".
 *
 * Also prevent the entire report from being rendered twice when Google Docs
 * exports the body without recognizable numbered headings. In that fallback
 * case, the body belongs to the single "本文" section and must not also remain
 * in the preface.
 */
parseDocument = function parseDocumentWithoutDecimalHeadings(rawText, fallbackTitle) {
  const lines = String(rawText || "").replace(/\r/g, "").split("\n");
  let cursor = 0;
  while (cursor < lines.length && !lines[cursor].trim()) cursor += 1;

  let documentTitle = fallbackTitle;
  if (cursor < lines.length && /^マーケットレポート[｜|]/.test(lines[cursor].trim())) {
    documentTitle = lines[cursor].trim();
    cursor += 1;
  }

  const preface = [];
  const sections = [];
  let current = null;

  // Critical: require one or more spaces after the punctuation.
  // "1. 市場概況" matches; "77.29ドル" and "4.670%" do not.
  const plainHeadingPattern = /^\s*(\d{1,2})[．.]\s+(.+?)\s*$/;
  const bracketHeadingPattern = /^\s*【\s*(?:(\d{1,2})[．.]\s*)?(.+?)\s*】\s*$/;

  const startSection = (number, title) => {
    if (current) sections.push(current);
    current = {
      number: number || "",
      title: String(title || "").trim(),
      lines: []
    };
  };

  for (; cursor < lines.length; cursor += 1) {
    const line = lines[cursor];
    const trimmed = line.trim();
    const bracketHeading = trimmed.match(bracketHeadingPattern);
    const plainHeading = trimmed.match(plainHeadingPattern);

    if (bracketHeading) {
      startSection(bracketHeading[1], bracketHeading[2]);
      continue;
    }
    if (plainHeading) {
      startSection(plainHeading[1], plainHeading[2]);
      continue;
    }

    if (current) current.lines.push(line);
    else preface.push(line);
  }

  if (current) sections.push(current);

  // If no numbered/bracketed section was detected, the old implementation
  // kept the same lines in both `preface` and `sections`, which displayed the
  // complete report twice. Move the body into the single fallback section.
  if (!sections.length) {
    const bodyLines = preface.slice();
    preface.length = 0;
    sections.push({ number: "", title: "本文", lines: bodyLines });
  }

  return { title: documentTitle, preface, sections };
};
