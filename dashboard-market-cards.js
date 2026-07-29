(() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  const arr = value => Array.isArray(value) ? value : (value ? [value] : []);
  const firstText = (...values) => values.find(value => typeof value === 'string' && value.trim() && !/^(?:記載なし|レポートに記載