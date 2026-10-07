/* Additive target-identity boundary. No trigger or publisher operations.
 * Python reporting/context.py owns the complete contract. GAS verifies its
 * persisted input when a caller explicitly selects the foundation path.
 */
function validateImmutableReportContext_(input) {
  if (!input || !/^\d{4}-\d{2}-\d{2}$/.test(input.report_date || '')) throw new Error('explicit report_date required');
  if (['08:00','12:00','16:00','21:00'].indexOf(input.report_time) < 0) throw new Error('explicit report_time required');
  var expected = input.report_date + '_' + input.report_time.replace(':','-');
  if (input.report_id !== expected) throw new Error('report_id mismatch');
  var date = new Date(input.report_date + 'T00:00:00+09:00');
  if (isNaN(date.getTime()) || new Date(date.getTime()+9*3600000).toISOString().slice(0,10) !== input.report_date) throw new Error('invalid target date');
  if (['new','historical','recovery'].indexOf(input.mode) < 0) throw new Error('explicit mode required');
  var weekday = new Date(date.getTime()+9*3600000).getUTCDay();
  if (input.mode === 'new' && (weekday === 0 || weekday === 6)) throw new Error('weekend new report forbidden');
  if (!Number.isInteger(input.revision) || input.revision < 1) throw new Error('positive revision required');
  if (!/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(input.data_cutoff || '') || isNaN(Date.parse(input.data_cutoff))) throw new Error('aware data_cutoff required');
  if (Date.parse(input.data_cutoff) > Date.parse(input.report_date+'T'+input.report_time+':00+09:00')) throw new Error('cutoff after target');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.previous_business_day || '') || input.previous_business_day >= input.report_date) throw new Error('previous business day required');
  var result = {};
  ['report_date','report_time','report_id','data_cutoff','previous_report_id','previous_business_day','revision','mode'].forEach(function(key){result[key]=input[key];});
  return Object.freeze(result);
}
