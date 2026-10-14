/* Real browser rejection tests against the generated, source-bound HTML. */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {spawnSync} = require('child_process');
const source = process.argv[2];
const output = process.argv[3];
const browser = process.argv[4];
if (!source || !output || fs.existsSync(output)) throw new Error('Require source and a new negative-test directory');
const html = fs.readFileSync(path.join(source, 'report.html'), 'utf8');
const contract = JSON.parse(fs.readFileSync(path.join(source, 'render-contract.json'), 'utf8'));
const cases = [
  ['one-digit', html.replace(/(data-numeric-id="n00001">)[^<]+/, '$199999'), /differences|numeric_differences/],
  ['panel-15-missing', html.replace(/<section[^>]+data-card="15"[\s\S]*?<\/section>/, ''), /cards|visual_order/],
  ['card-overlap', html.replace('</style>', '.card-15{position:absolute;left:0;top:200px;width:900px}</style>'), /overlapping_cards|overflow|outside/],
];
fs.mkdirSync(output, {recursive: true});
const results = [];
for (const [name, candidate, expectedError] of cases) {
  const directory = path.join(output, name);
  fs.mkdirSync(directory);
  const altered = {...contract, html_sha256: crypto.createHash('sha256').update(candidate).digest('hex')};
  fs.writeFileSync(path.join(directory, 'report.html'), candidate);
  fs.writeFileSync(path.join(directory, 'contract.json'), JSON.stringify(altered));
  const args = ['scripts/render_morning_png.js','--html',path.join(directory,'report.html'),
    '--contract',path.join(directory,'contract.json'),'--out',path.join(directory,'png')];
  if (browser) args.push('--browser',browser);
  const result = spawnSync(process.execPath,args,{encoding:'utf8',timeout:60000});
  if (result.status === 0 || !expectedError.test(result.stderr) || fs.existsSync(path.join(directory,'png'))) {
    throw new Error(`${name} did not fail closed: ${result.stderr}`);
  }
  fs.writeFileSync(path.join(directory,'rejection.log'),result.stderr);
  results.push({case:name,status:'PASS',renderer:'REJECTED',publication:'NOT_RUN'});
}
fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2)+'\n');
process.stdout.write(JSON.stringify(results)+'\n');
