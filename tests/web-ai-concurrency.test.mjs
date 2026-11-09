// BookDistiller 网页 AI 操作的并发/旧结果回归。
// 全部使用虚构材料与 mock fetch，不调用真实模型、不需要密钥。
// 运行：node --test tests/web-ai-concurrency.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const HERE=path.dirname(fileURLToPath(import.meta.url));
const WEB=path.resolve(HERE,'../web');

class FakeElement{
 constructor(tag='div'){this.tagName=tag;this.value='';this.textContent='';this.className='';this.hidden=false;this.disabled=false;this.open=false;this.checked=false;this.max=0;this.maxLength=0;this.rows=0;this.type='';this.files=[];this.href='';this.download='';this.children=[];this.listeners={};this.attrs={};this.style={};}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}
 dispatch(type,event={}){for(const fn of this.listeners[type]??[])fn(event);}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k]??null;}
 replaceChildren(...nodes){this.children=[...nodes];}
 append(...nodes){this.children.push(...nodes);}
 scrollIntoView(){}
 focus(){}
 click(){if(typeof this.onclick==='function')return this.onclick();}
}
function installDom(){
 const map=new Map();
 global.document={getElementById:id=>{if(!map.has(id))map.set(id,new FakeElement('div'));return map.get(id);},createElement:tag=>new FakeElement(tag)};
 return {el:id=>document.getElementById(id)};
}
const tick=(ms=0)=>new Promise(resolve=>setTimeout(resolve,ms));
function textOf(node){
 const out=[];
 const walk=n=>{if(n==null)return;if(typeof n==='string'){out.push(n);return;}if(n.textContent)out.push(String(n.textContent));for(const c of n.children||[])walk(c);};
 walk(node);return out.join('\n');
}
let appSeq=0;
async function loadApp(){
 appSeq++;
 return import(pathToFileURL(path.join(WEB,'app.mjs')).href+'?case='+appSeq);
}
const REVIEW='虚构读者：我还没想明白，先把这些句子留下。';
const HIGHLIGHTS='虚构原句甲。\n\n虚构原句乙。';
function configure(doc){
 doc.el('title').value='虚构书名';
 doc.el('author').value='虚构作者';
 doc.el('review').value=REVIEW;
 doc.el('highlights').value=HIGHLIGHTS;
 doc.el('key').value='test-key';
 doc.el('model').value='test-model';
}
const VALID={core_claims:['虚构读者仍在犹豫，不想把等待写成方法。'],claim_sources:[['review']],takeaway:null,takeaway_sources:[],takeable:null,takeable_sources:[],steps_sources:[],golden_quotes:['虚构原句甲。〔划线1〕'],anti_patterns:[],links:[]};
const promptOk=()=>({ok:true,status:200,text:async()=>'MOCK PROMPT'});
const apiOk=()=>({ok:true,status:200,json:async()=>({choices:[{message:{content:JSON.stringify(VALID)}}]})});
const abortError=()=>new DOMException('Aborted','AbortError');
function deferred(){let resolve,reject;const promise=new Promise((res,rej)=>{resolve=res;reject=rej;});return {promise,resolve,reject};}
function rejectOnAbort(d,signal){
 if(!signal)return;
 const fail=()=>d.reject(abortError());
 if(signal.aborted)fail();else signal.addEventListener('abort',fail,{once:true});
}
const isPrompt=url=>String(url).endsWith('card-prompt.txt');

test('S1 提示词读取期间双击只发一次模型请求',async()=>{
 const doc=installDom();const prompts=[];let apiCalls=0;const api=deferred();
 global.fetch=(url,opts)=>{
  if(isPrompt(url)){const d=deferred();prompts.push(d);rejectOnAbort(d,opts?.signal);return d.promise;}
  apiCalls++;return api.promise;
 };
 await loadApp();configure(doc);
 const p1=doc.el('ai').onclick();const p2=doc.el('ai').onclick();
 try{
  await tick();
  assert.equal(prompts.length,1,'双击不应重复读取提示词');
  prompts[0].resolve(promptOk());
  await tick();
  assert.equal(apiCalls,1,'双击只应发一次模型请求');
 }finally{
  for(const d of prompts)d.resolve(promptOk());
  api.resolve(apiOk());
  await Promise.allSettled([p1,p2]);
 }
});

test('S2 提示词读取失败：不发模型请求、释放占位、可重试',async()=>{
 const doc=installDom();let promptFails=true;let apiCalls=0;
 global.fetch=async(url)=>{
  if(isPrompt(url)){if(promptFails)throw new TypeError('Failed to fetch');return promptOk();}
  apiCalls++;return apiOk();
 };
 await loadApp();configure(doc);
 await doc.el('ai').onclick();
 assert.equal(apiCalls,0,'提示词失败不应发起模型请求');
 assert.equal(doc.el('ai').disabled,false,'失败后按钮应恢复');
 assert.match(doc.el('status').textContent,/提示词读取失败/);
 promptFails=false;
 await doc.el('ai').onclick();
 assert.equal(apiCalls,1,'失败后应可重试');
 assert.match(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
});

test('S3 模型等待时改材料：取消旧请求且不采用旧结果',async()=>{
 const doc=installDom();let apiCalls=0;let aborted=false;const api=deferred();
 global.fetch=(url,opts)=>{
  if(isPrompt(url))return Promise.resolve(promptOk());
  apiCalls++;
  if(opts?.signal)opts.signal.addEventListener('abort',()=>{aborted=true;api.reject(abortError());},{once:true});
  return api.promise;
 };
 await loadApp();configure(doc);
 const p=doc.el('ai').onclick();
 try{
  await tick();
  assert.equal(apiCalls,1);
  doc.el('review').value=REVIEW+'（改后）';
  doc.el('review').dispatch('input');
  await tick();
  assert.equal(aborted,true,'改材料应取消进行中的请求');
  assert.match(doc.el('status').textContent,/取消|已修改/);
 }finally{
  api.resolve(apiOk());
  await p;
 }
 assert.equal(doc.el('ai').disabled,false,'取消后按钮应恢复');
 assert.doesNotMatch(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
});

test('S4 模型等待时编辑卡片：旧结果不覆盖编辑',async()=>{
 const doc=installDom();let apiCalls=0;const api=deferred();
 global.fetch=(url)=>{if(isPrompt(url))return Promise.resolve(promptOk());apiCalls++;return api.promise;};
 await loadApp();configure(doc);
 await doc.el('local').onclick();
 const p=doc.el('ai').onclick();
 try{
  await tick();
  assert.equal(apiCalls,1);
  const area=doc.el('edit-sections').children[0].children[1];
  area.value='本人改写的段落，不接受旧候选。';
  area.oninput();
  assert.match(textOf(doc.el('preview')),/本人改写的段落/);
  api.resolve(apiOk());
  await p;
 }finally{
  api.resolve(apiOk());
  await p;
 }
 const text=textOf(doc.el('preview'));
 assert.match(text,/本人改写的段落/,'编辑后的内容应保留');
 assert.doesNotMatch(text,/虚构读者仍在犹豫/,'旧 AI 结果不应覆盖编辑');
 assert.equal(doc.el('ai').disabled,false);
});

test('S5 模型等待时重新排版：旧结果不覆盖新排版',async()=>{
 const doc=installDom();let apiCalls=0;const api=deferred();
 global.fetch=(url)=>{if(isPrompt(url))return Promise.resolve(promptOk());apiCalls++;return api.promise;};
 await loadApp();configure(doc);
 await doc.el('local').onclick();
 const p=doc.el('ai').onclick();
 try{
  await tick();
  assert.equal(apiCalls,1);
  await doc.el('local').onclick();
  api.resolve(apiOk());
  await p;
 }finally{
  api.resolve(apiOk());
  await p;
 }
 const text=textOf(doc.el('preview'));
 assert.match(text,/本人文字 \/ 本地排版/,'重新排版后的版本应保留');
 assert.doesNotMatch(text,/虚构读者仍在犹豫/,'旧 AI 结果不应覆盖新排版');
 assert.equal(doc.el('ai').disabled,false);
});

test('S6 成功路径：采用结果并解锁',async()=>{
 const doc=installDom();let apiCalls=0;
 global.fetch=async(url)=>{if(isPrompt(url))return promptOk();apiCalls++;return apiOk();};
 await loadApp();configure(doc);
 await doc.el('ai').onclick();
 assert.equal(apiCalls,1);
 assert.match(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
 assert.equal(doc.el('ai').disabled,false,'成功后应解锁');
 await doc.el('ai').onclick();
 assert.equal(apiCalls,2,'成功后应可再次生成');
});

test('S7 模型失败（HTTP 500）：原卡保留、解锁、可重试',async()=>{
 const doc=installDom();let apiCalls=0;
 global.fetch=async(url)=>{
  if(isPrompt(url))return promptOk();
  apiCalls++;
  return apiCalls===1?{ok:false,status:500,json:async()=>({})}:apiOk();
 };
 await loadApp();configure(doc);
 await doc.el('ai').onclick();
 assert.equal(apiCalls,1);
 assert.doesNotMatch(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
 assert.equal(doc.el('ai').disabled,false,'失败后应解锁');
 assert.match(doc.el('status').textContent,/HTTP 500/);
 await doc.el('ai').onclick();
 assert.equal(apiCalls,2,'失败后应可重试');
 assert.match(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
});

test('S8 模型返回非法 JSON：原卡保留、解锁、可重试',async()=>{
 const doc=installDom();let apiCalls=0;
 global.fetch=async(url)=>{
  if(isPrompt(url))return promptOk();
  apiCalls++;
  return apiCalls===1?{ok:true,status:200,json:async()=>({choices:[{message:{content:'这不是 JSON'}}]})}:apiOk();
 };
 await loadApp();configure(doc);
 await doc.el('ai').onclick();
 assert.equal(apiCalls,1);
 assert.doesNotMatch(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
 assert.equal(doc.el('ai').disabled,false,'解析失败后应解锁');
 await doc.el('ai').onclick();
 assert.equal(apiCalls,2,'解析失败后应可重试');
 assert.match(textOf(doc.el('preview')),/虚构读者仍在犹豫/);
});
