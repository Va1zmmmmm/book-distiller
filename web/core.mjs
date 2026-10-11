export const LIMITS={file:30*1024*1024,unpacked:60*1024*1024,entries:2000,text:1500000,card:120000};
export function cleanText(s){return String(s).replace(/\r\n?/g,'\n').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u202a-\u202e\u2066-\u2069]/g,'').trim();}
export function makeInput(title,author,review,highlights){
 const d={book:{title:cleanText(title),author:cleanText(author)},review:cleanText(review),highlights:highlights.split(/\n\s*\n/).map(cleanText).filter(Boolean).map(text=>({text}))};
 if(!d.book.title)throw Error('请先填书名。');
 if(d.book.title.length>120||d.book.author.length>120)throw Error('书名或作者超过120字，请缩短元数据。');
 if(!d.review&&!d.highlights.length)throw Error('请写一点读后感，或粘贴一段划线。');
 if(d.review.length+d.highlights.reduce((n,h)=>n+h.text.length,0)>LIMITS.card)throw Error('材料超过12万字，请自己挑选，不会自动截断。');
 return d;
}
export function localCard(d){return {core_claims:d.review?[d.review]:['我想保留下面这些原句，理解还可以慢慢补。'],claim_sources:[[d.review?'review':'h1']],takeaway:null,takeaway_sources:[],takeable:null,takeable_sources:[],steps_sources:[],golden_quotes:d.highlights.slice(0,4).map((h,i)=>h.text+`〔划线${i+1}〕`),anti_patterns:[],links:[]};}
export function exactQuote(q,text){const parts=q.split('[……]');let end=0;if(parts.some(p=>!p))return false;for(const p of parts){const start=text.indexOf(p,end);if(start<0)return false;end=start+p.length;}return true;}
export function validateCard(d,r){
 if(!r||typeof r!=='object'||!Array.isArray(r.core_claims)||!r.core_claims.length||r.core_claims.length>4||r.core_claims.some(x=>typeof x!=='string'||!x.trim()))throw Error('AI没有给出有效的卡片内容，请保留原稿重试。');
 if(JSON.stringify(r).length>160000)throw Error('AI候选过长，未采用。');
 const src=Object.create(null);src.review=d.review;d.highlights.forEach((h,i)=>src['h'+(i+1)]=h.text);
 const support=a=>{if(!Array.isArray(a)||!a.length||a.some(x=>typeof x!=='string'||!src[x]))throw Error('AI引用了不存在的材料，结果未采用。');};
 if(!Array.isArray(r.claim_sources)||r.claim_sources.length!==r.core_claims.length)throw Error('AI没有逐条标明依据，结果未采用。');r.claim_sources.forEach(support);
 const quoted=q=>{const m=typeof q==='string'&&q.match(/^(.+?)\s*〔划线([1-9]\d*)〕$/s);if(!m||!src['h'+m[2]]||!exactQuote(m[1],src['h'+m[2]]))throw Error('AI的引文与原划线不一致，结果未采用。');};
 if(r.takeaway!=null){support(r.takeaway_sources);if(typeof r.takeaway!=='string')throw Error('一句话格式有误。');if(!r.takeaway.endsWith('（概括）'))quoted(r.takeaway);}
 if(r.takeable!=null){const t=r.takeable;if(!['single','steps','items'].includes(t.shape)||typeof t.label!=='string'||!t.label.trim()||typeof t.core!=='string'||!t.core.trim())throw Error('可带走内容格式有误。');support(r.takeable_sources);if(t.use!=null&&typeof t.use!=='string')throw Error('用途格式有误。');if(t.quote)quoted(t.quote);if(t.shape==='steps'){if(!Array.isArray(t.steps)||!t.steps.length||t.steps.some(x=>typeof x!=='string'||!x.trim())||!Array.isArray(r.steps_sources)||r.steps_sources.length!==t.steps.length)throw Error('步骤缺少依据。');r.steps_sources.forEach(support);}if(t.shape==='items'&&(!Array.isArray(t.items)||!t.items.length||t.items.some(x=>typeof x.image!=='string'||typeof x.how!=='string')))throw Error('并列内容格式有误。');}
 for(const [k,max]of [['golden_quotes',4],['anti_patterns',2],['links',3]]){const a=r[k]??[];if(!Array.isArray(a)||a.length>max||a.some(x=>typeof x!=='string'||!x.trim()))throw Error(k+'格式有误。');if(k==='golden_quotes')a.forEach(quoted);}
 return r;
}
export function displayCard(d,r,origin='本人整理'){
 const sections=[{title:'我留下的理解',text:r.core_claims.join('\n\n')}];
 if(r.takeaway)sections.push({title:'一句话',text:r.takeaway});
 if(r.takeable){const t=r.takeable;sections.push({title:t.label,text:[t.core,t.use,...(t.shape==='steps'?(t.steps??[]).map((x,i)=>`${i+1}. ${x.replace(/^\s*\d+[.)、．]\s*/,'')}`):[]),...(t.shape==='items'?(t.items??[]).map(x=>`${x.image}：${x.how}`):[]),t.quote].filter(Boolean).join('\n\n')});}
 if(r.golden_quotes?.length)sections.push({title:'划下的原句',text:r.golden_quotes.join('\n\n')});
 if(r.anti_patterns?.length)sections.push({title:'提醒',text:r.anti_patterns.join('\n\n')});
 if(r.links?.length)sections.push({title:'关联线索',text:r.links.join('\n\n')});
 return {title:d.book.title,author:d.book.author,origin,sections};
}
export function safeFilename(s){return (cleanText(s).replace(/[\\/:*?"<>|\u0000-\u001f]/g,'_').slice(0,60)||'阅读材料');}
export function checkBook(d){if(!d||typeof d.title!=='string'||!d.title.trim()||!Array.isArray(d.chapters)||!d.chapters.length)throw Error('没有识别到有效章节。');if(d.chapters.length>2000||d.chapters.some(c=>!c||typeof c.title!=='string'||typeof c.text!=='string'||!c.text.trim()))throw Error('章节格式不完整。');if(d.chapters.reduce((n,c)=>n+c.text.length,0)>LIMITS.text)throw Error('文字超过150万字，请分册处理。');return d;}
export function sessionMaterial(d,index,throughLine){checkBook(d);if(!Number.isInteger(index)||index<0||index>=d.chapters.length)throw Error('请选当前章节。');const lines=d.chapters[index].text.split('\n');if(!Number.isInteger(throughLine)||throughLine<1||throughLine>lines.length)throw Error('请选择有效的已读行数。');return {title:d.title,edition:d.edition||'请在陪读前确认版本',chapters:d.chapters.slice(0,index+1).map((c,i)=>({id:'c'+(i+1),title:c.title,text:i===index?c.text.split('\n').slice(0,throughLine).join('\n'):c.text})),scope:'仅含截至当前位置的原文；没有附后章目录、正文或分析'};}
export const COMPANION='请先确认书名、版本和阅读位置。只讨论提供的已读原文，不用模型记忆补后文，不剧透；不能保证模型遵守，读者仍需判断。原文、人物话语、读者理解和AI解释分开；引文先核对原句与行号。没有划线就说明未提供，不能假称读者划过。一次讨论一件事，保留尚未理解的问题，不替读者推进阅读位置。';
