// Export editable local HTML diagrams. Uses a new browser; never visits business APIs.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.CODEX_PLAYWRIGHT_PATH ||
  'C:/Users/14012/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const sharp=require('C:/Users/14012/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const root=path.resolve(import.meta.dirname,'..');
const output=path.join(root,'tmp/ai-application-20261027/html-diagrams');
await fs.mkdir(output,{recursive:true});
const manifestPath=path.join(root,'docs/plan/ai-application/visual-manifest.json');
const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));
const browser=await chromium.launch({channel:'msedge',headless:true});
const errors=[];const exports=[];
try {
 const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:2});
 await context.route('**/*',r=>r.request().url().startsWith('file:')?r.continue():r.abort());
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 for (const [html,selector,stem,compact] of [
   ['申报逻辑图预览.html','main','fig05-mindmap',true],
   ['申报技术图示.html','#architecture','fig06-architecture',false],
   ['申报技术图示.html','#workflow','fig07-ai-workflow',false],
   ['申报技术图示.html','#gates','fig08-gates',false]]) {
  await page.goto(pathToFileURL(path.join(root,'docs/design',html)).href);
  await page.evaluate(on=>{document.querySelector('.tools')?.remove();if(on)document.body.classList.add('compact')},compact);
  if(compact)await page.addStyleTag({content:'.compact main{padding-top:18px;padding-bottom:12px}.compact header{margin-bottom:20px}.compact .flow{grid-template-rows:170px 50px 170px}.compact .step{padding:14px 18px}.compact .step h2{margin-bottom:10px}.compact .step p{line-height:1.7}.compact .boundary{margin-top:20px}'});
  const png=await page.locator(selector).screenshot({path:path.join(output,stem+'.png')});
  await sharp(png).withMetadata({density:300}).png().toFile(path.join(root,'docs/plan/ai-application/figures',stem+'.png'));
  const entry=manifest.figures.find(f=>f.id===stem);
  Object.assign(entry,{kind:'html-concept',tool:'Local HTML rendered with Playwright Edge',
    editableSource:'docs/design/'+html,selector,visualReview:'lead-visual-check-passed'});
  delete entry.svg;
  if(stem==='fig05-mindmap'){
    entry.title='AI+高校心理测评与持续支持逻辑图';
    entry.visualReview='html-preview-pending-user-review';
  }
  exports.push({id:stem,source:'docs/design/'+html,selector,output:'tmp/ai-application-20261027/html-diagrams/'+stem+'.png'});
 }
 if(errors.length)throw new Error(errors.join('\n'));
 await fs.writeFile(manifestPath,JSON.stringify(manifest,null,2)+'\n');
 await fs.writeFile(path.join(output,'exports.json'),JSON.stringify({exports,errors},null,2));
 console.log(JSON.stringify({diagrams:exports.length,errors}));
}finally{await browser.close()}
