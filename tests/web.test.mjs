import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {makeInput,localCard,validateCard,displayCard,sessionMaterial,exactQuote} from '../web/core.mjs';
const examples=JSON.parse(fs.readFileSync(new URL('../web/examples.json',import.meta.url),'utf8'));
test('published original examples satisfy source contract',()=>{for(const k of ['fiction','method']){const x=examples[k];assert.equal(validateCard(x.input,x.response),x.response);assert.ok(displayCard(x.input,x.response).sections.length);}});
test('step numbers render once',()=>{const x=examples.method;assert.ok(!displayCard(x.input,x.response).sections.some(s=>/1\. 1\./.test(s.text)));});
test('local layout retains readers words; no inferred methods',()=>{const d=makeInput('书','人','还没懂，不能说我选择不懂。','一条原句。\n\n第二条。');const r=localCard(d);assert.deepEqual(r.core_claims,[d.review]);assert.equal(r.takeable,null);assert.equal(r.golden_quotes[1],'第二条。〔划线2〕');validateCard(d,r);});
test('fabricated and inherited source IDs rejected',()=>{const x=examples.fiction;for(const ref of ['h999','constructor','__proto__',{}]){const r=structuredClone(x.response);r.claim_sources=[[ref]];assert.throws(()=>validateCard(x.input,r));}});
test('altered quotes and wrong source references rejected',()=>{const x=examples.fiction;const r=structuredClone(x.response);r.golden_quotes=['这是我编的。〔划线1〕'];assert.throws(()=>validateCard(x.input,r));});
test('explicit elision is ordered, never fuzzy',()=>{assert.ok(exactQuote('甲[……]丙','甲乙丙'));assert.ok(!exactQuote('丙[……]甲','甲乙丙'));assert.ok(!exactQuote('甲，乙','甲乙'));});
test('partial chapter scope contains no future title or raw text',()=>{const b={title:'测试',edition:'版本',chapters:[{title:'当前',text:'第一行\n第二行未读'},{title:'后章秘密',text:'青灯晚潮'}]};const s=sessionMaterial(b,0,1);const raw=JSON.stringify(s);assert.ok(raw.includes('第一行'));for(const marker of ['第二行未读','后章秘密','青灯晚潮'])assert.ok(!raw.includes(marker));assert.throws(()=>sessionMaterial(b,0,3));});
test('browser prompt matches canonical CLI prompt',()=>{assert.ok(fs.readFileSync(new URL('../web/card-prompt.txt',import.meta.url),'utf8').includes('未解问题不自动成为读者已接受的立场'));});
test('vendor files match pinned hash manifest',()=>{const v=JSON.parse(fs.readFileSync(new URL('../web/vendor/manifest.json',import.meta.url)));return import('node:crypto').then(({createHash})=>{for(const [name,hash]of Object.entries(v.sha256))assert.equal(createHash('sha256').update(fs.readFileSync(new URL('../web/vendor/'+name,import.meta.url))).digest('hex'),hash);});});
test('corrupt EPUB bytes rejected with a readable message',async()=>{const {readEpub}=await import('../web/importers.mjs');assert.throws(()=>readEpub(new Uint8Array([0x50,0x4b,0x03,0x04,0x00,0x00])),/EPUB文件损坏或不是有效的EPUB/);});
test('non-UTF-8 EPUB content rejected instead of silent mojibake',async()=>{const {readEpub}=await import('../web/importers.mjs');const {zipSync}=await import('../web/vendor/fflate.mjs');const bad=new Uint8Array([...Buffer.from('<container>'),0xbe,...Buffer.from('</container>')]);assert.throws(()=>readEpub(zipSync({'META-INF/container.xml':bad})),/不是有效的UTF-8编码/);});
test('PDF errors classified by cause, not all as corrupt',async()=>{const {pdfErrorMessage}=await import('../web/importers.mjs');const cases=[
 [{name:'InvalidPDFException',message:'Invalid PDF structure.'},/文件损坏或不是有效的PDF/],
 [{name:'PasswordException',message:'No password given'},/密码保护/],
 [{name:'Error',message:'Setting up fake worker failed: "Failed to fetch dynamically imported module: http://x/pdf.worker.min.mjs".'},/解析组件加载失败/],
 [{name:'TypeError',message:'Failed to fetch dynamically imported module: http://x/pdf.min.mjs'},/解析组件加载失败/],
 [{name:'TypeError',message:'boom'},/未知原因/],
 [null,/未知原因/]];for(const [e,re]of cases){const m=pdfErrorMessage(e);assert.match(m,re);if(!/InvalidPDFException/.test(String(e?.name||''))){assert.ok(!m.includes('文件损坏'),`unexpected corrupt label: ${m}`);assert.ok(!m.includes('不是有效的PDF'),`unexpected corrupt label: ${m}`);}}});
test('unknown PDF error is not disguised as a corrupt file',async()=>{const {pdfErrorMessage}=await import('../web/importers.mjs');const m=pdfErrorMessage(new TypeError('boom'));assert.match(m,/未知原因/);assert.ok(!m.includes('文件损坏'));assert.ok(!m.includes('不是有效的PDF'));});
