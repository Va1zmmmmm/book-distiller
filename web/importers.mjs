import {unzipSync,strFromU8} from './vendor/fflate.mjs';
import {LIMITS,cleanText,checkBook} from './core.mjs';
const parse=(s)=>{const d=new DOMParser().parseFromString(s,'application/xml');if(d.getElementsByTagName('parsererror').length)throw Error('EPUB的章节或目录损坏，未导入。');return d;};
const all=(d,n)=>Array.from(d.getElementsByTagNameNS('*',n));
function visibleText(node){if(node.nodeType===3)return node.textContent;if(node.nodeType!==1)return '';const block=/^(?:h[1-6]|p|li|blockquote|div|section|br|tr)$/i.test(node.localName);return (block?'\n':'')+Array.from(node.childNodes).map(visibleText).join('')+(block?'\n':'');}
function pathJoin(base,href){if(!href||/^[a-z]+:|^\/|\\/i.test(href))throw Error('EPUB包含无效的资源路径。');const parts=(base+'/'+decodeURIComponent(href.split('#')[0])).split('/'),out=[];for(const p of parts){if(p==='..'){if(!out.length)throw Error('EPUB资源路径越界。');out.pop();}else if(p&&p!=='.')out.push(p);}return out.join('/');}
export function readEpub(bytes){
 let total=0,entries=0;const files=unzipSync(bytes,{filter:f=>{if(++entries>LIMITS.entries)throw Error('EPUB文件项过多。');if(f.originalSize>LIMITS.unpacked||(total+=f.originalSize)>LIMITS.unpacked)throw Error('EPUB解压后过大，请分册处理。');return /\.(xml|opf|xhtml|html|htm)$/i.test(f.name);}});
 const read=n=>{if(!files[n])throw Error('EPUB缺少章节文件：'+n);return strFromU8(files[n]);};
 if(files['META-INF/encryption.xml'])throw Error('此EPUB包含加密资源，本工具不解密，请提供未加密且有权使用的版本。');
 const container=parse(read('META-INF/container.xml'));const opf=all(container,'rootfile')[0]?.getAttribute('full-path');if(!opf)throw Error('EPUB缺少书目文件。');const doc=parse(read(opf)),base=opf.includes('/')?opf.slice(0,opf.lastIndexOf('/')):'';
 const items=new Map(all(doc,'item').map(e=>[e.getAttribute('id'),e]));const chapters=[];let textCount=0;
 for(const ref of all(doc,'itemref')){const item=items.get(ref.getAttribute('idref'));if(!item)throw Error('EPUB章节清单有缺项。');if(!/html/.test(item.getAttribute('media-type')||''))continue;const x=parse(read(pathJoin(base,item.getAttribute('href'))));for(const e of Array.from(x.querySelectorAll('script,style,svg,nav')))e.remove();const body=all(x,'body')[0];if(!body)throw Error('EPUB章节没有正文。');const heading=Array.from(body.querySelectorAll('h1,h2,h3')).find(e=>e.textContent.trim())?.textContent;const text=cleanText(visibleText(body).replace(/\n{3,}/g,'\n\n'));if(text){textCount+=text.length;if(textCount>LIMITS.text)throw Error('文字超过150万字，请分册处理。');chapters.push({id:'c'+(chapters.length+1),title:cleanText(heading||`章节 ${chapters.length+1}`),text});}}
 return checkBook({id:'imported-book',title:cleanText(all(doc,'title')[0]?.textContent||'导入的书'),author:cleanText(all(doc,'creator')[0]?.textContent||''),edition:cleanText(all(doc,'publisher')[0]?.textContent||'请确认译者与版本'),chapters,import_note:'按EPUB阅读顺序提取；章节、译本与排版请回看原文件。'});
}
export async function readPdf(bytes,onProgress=()=>{}){
 const pdf=await import('./vendor/pdf.min.mjs');pdf.GlobalWorkerOptions.workerSrc=new URL('./vendor/pdf.worker.min.mjs',import.meta.url).href;
 const task=pdf.getDocument({data:bytes,isEvalSupported:false,stopAtErrors:true,disableFontFace:true,useSystemFonts:true});let d;
 try{d=await task.promise;if(d.numPages>1200)throw Error('PDF超过1200页，请分册导入。');const meta=await d.getMetadata().catch(()=>({info:{}})),chapters=[];let count=0;
 for(let i=1;i<=d.numPages;i++){onProgress(`正在读取 PDF：${i} / ${d.numPages} 页`);const page=await d.getPage(i),content=await page.getTextContent();let text='',previous=null;for(const it of content.items){if(!('str'in it))continue;const y=it.transform?.[5];if(previous!==null&&Math.abs(y-previous)>3)text+='\n';text+=it.str+(it.hasEOL?'\n':' ');previous=y;}text=cleanText(text);if(!text)throw Error(`第 ${i} 页没有可提取文字，可能是扫描页。本工具没有OCR，未导入不完整结果。`);count+=text.length;if(count>LIMITS.text)throw Error('PDF文字超过150万字，请分册处理。');chapters.push({id:'c'+i,title:'第 '+i+' 页',text});page.cleanup();}
 return checkBook({id:'imported-pdf',title:cleanText(meta.info?.Title||'导入的PDF'),author:cleanText(meta.info?.Author||''),edition:'PDF页面原文；请确认译者与版本',chapters,import_note:'PDF按页提取，不猜测章节；双栏/扫描/复杂排版需人工核对。'});
 }finally{await task.destroy();}
}
export async function importBook(file,onProgress){if(file.size>LIMITS.file)throw Error('文件超过30MB，请分册处理。');const ext=file.name.split('.').pop().toLowerCase();if(ext==='epub')return readEpub(new Uint8Array(await file.arrayBuffer()));if(ext==='pdf')return readPdf(new Uint8Array(await file.arrayBuffer()),onProgress);if(ext==='json')return checkBook(JSON.parse(await file.text()));if(['txt','md'].includes(ext)){const text=cleanText(await file.text());return checkBook({id:'imported-text',title:file.name.replace(/\.[^.]+$/,''),edition:'文本文件；请确认版本',chapters:[{id:'c1',title:'正文',text}]});}throw Error('请选择 EPUB、PDF、TXT、Markdown 或标准书籍 JSON。');}
