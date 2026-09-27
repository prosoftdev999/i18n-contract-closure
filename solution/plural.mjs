import fs from 'node:fs';
const q=JSON.parse(fs.readFileSync(0,'utf8'));
const pr=new Intl.PluralRules(q.locale,{type:q.type==='selectordinal'?'ordinal':'cardinal'});
process.stdout.write(JSON.stringify(q.values.map(v=>pr.select(v))));
