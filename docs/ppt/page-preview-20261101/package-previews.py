"""Prepare before/after images and an offline page-selection gallery."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
import hashlib, json, shutil, html, csv

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=ROOT/'deliverables/逐页优化预览_20261101'
SOURCE_PAGES=ROOT/'tmp/ppt-agent-interaction-20261031/native-final'
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
build=json.loads((HERE/'build-record.json').read_text(encoding='utf-8'))
assert json.loads((SOURCE_PAGES/'native-render.json').read_text(encoding='utf-8-sig'))['sourceSha256']==build['sourceSha256']
original_dir=OUT/'original'; pairs_dir=OUT/'comparison'; overview_dir=OUT/'overview'; kept_dir=OUT/'retained-diagrams'
for folder in [original_dir,pairs_dir,overview_dir,kept_dir]:folder.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',26)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21)
bold=ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',26)
purple='#604372'; ink='#29332F'; soft='#EEE7F2'
comparisons=[]
for n in range(1,19):
    name=f'slide-{n:02d}.png'
    shutil.copyfile(SOURCE_PAGES/name, original_dir/name)
    with Image.open(original_dir/name) as im:a=im.convert('RGB')
    with Image.open(OUT/'pdf-pages'/name) as im:b=im.convert('RGB')
    assert a.size==b.size==(1600,900)
    canvas=Image.new('RGB',(3248,988),'#FFFFFF'); draw=ImageDraw.Draw(canvas)
    draw.rectangle((0,0,3248,64),fill=soft)
    draw.text((30,15),f'{n:02d} 原页',font=bold,fill=purple)
    draw.text((1660,15),f'{n:02d} 优化方案',font=bold,fill=purple)
    canvas.paste(a,(16,76)); canvas.paste(b,(1632,76))
    target=pairs_dir/f'compare-{n:02d}.png'; canvas.save(target)
    comparisons.append({'page':n,'original':f'original/{name}','optimized':f'pdf-pages/{name}','comparison':f'comparison/compare-{n:02d}.png','change':build['pages'][n-1]['change'],'title':build['pages'][n-1]['title']})

for group in range(3):
    sheet=Image.new('RGB',(1512,1460),'#FFFFFF'); draw=ImageDraw.Draw(sheet)
    draw.text((24,12),f'优化方案总览  {group*6+1:02d}—{group*6+6:02d}',font=bold,fill=purple)
    for j in range(6):
        n=group*6+j+1; x=24+(j%2)*744; y=64+(j//2)*458
        title=build['pages'][n-1]['title']
        draw.text((x,y),f'{n:02d}  {title}',font=small,fill=ink)
        with Image.open(OUT/'pdf-pages'/f'slide-{n:02d}.png') as im:
            im=im.convert('RGB'); im.thumbnail((720,405))
            sheet.paste(im,(x,y+36))
    sheet.save(overview_dir/f'overview-{group+1}.png')

selected=json.loads((ROOT/'docs/ppt/local-agents-20261101/retained-selection.json').read_text(encoding='utf-8'))
for entry in selected['selected']:
    src=ROOT/entry['path']; dst=kept_dir/f"retained-v{entry['version']}.png"
    assert SHA(src)==entry['sha256']; shutil.copyfile(src,dst); assert SHA(dst)==entry['sha256']

pdf_name='心域智链_18页逐页优化参考稿_20261101.pdf'
shutil.copyfile(OUT/'optimized/optimized.pdf',OUT/pdf_name)
sections=[]
for row in comparisons:
    n=row['page']; title=html.escape(row['title']); change=html.escape(row['change'])
    sections.append(f'''<section id="page-{n:02d}" data-page="{n}">
<div class="section-head"><h2>{n:02d} · {title}</h2><label>选择 <select aria-label="第{n}页选择"><option value="pending">待选</option><option value="original">保留原页</option><option value="optimized">采用优化页</option><option value="revise">继续调整</option></select></label></div>
<p class="change">{change}</p><div class="pair"><figure><figcaption>原页</figcaption><a href="{row['original']}" target="_blank"><img loading="lazy" src="{row['original']}" width="1600" height="900" alt="第{n}页原版"></a></figure><figure><figcaption>优化方案</figcaption><a href="{row['optimized']}" target="_blank"><img loading="lazy" src="{row['optimized']}" width="1600" height="900" alt="第{n}页优化方案"></a></figure></div>
<div class="opinion"><label for="note-{n}">调整意见</label><input id="note-{n}" type="text" placeholder="可选：填写希望调整的内容"></div><a class="compare-link" href="{row['comparison']}" target="_blank">打开整张对照图</a></section>''')

nav=''.join(f'<a href="#page-{n:02d}">{n:02d}</a>' for n in range(1,19))
document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>心域智链 · 逐页方案选择</title><style>
:root{--purple:#604372;--soft:#EEE7F2;--ink:#29332F;--muted:#56625C;--line:#E3E8E1}*{box-sizing:border-box}body{margin:0;background:white;color:var(--ink);font:16px/1.6 "Microsoft YaHei",sans-serif}main{max-width:1680px;margin:auto;padding:32px}h1{font-size:26px;margin:0 0 12px}h2{font-size:20px;margin:0;color:var(--purple)}p{margin:10px 0}a{color:var(--purple)}.links,.nav,.toolbar{display:flex;gap:16px;flex-wrap:wrap;align-items:center}.nav{gap:10px;margin:20px 0}.nav a{padding:4px 9px;background:var(--soft);text-decoration:none}button,select,input{font:inherit}button,select{padding:7px 12px;border:1px solid var(--line);background:white;color:var(--ink);border-radius:6px}button{cursor:pointer;background:var(--soft)}section{padding:28px 0;border-top:1px solid var(--line);scroll-margin-top:20px}.section-head{display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}.change{color:var(--muted)}.pair{display:grid;grid-template-columns:1fr 1fr;gap:20px}figure{margin:0;min-width:0}figcaption{margin:6px 0;color:var(--muted)}img{display:block;max-width:100%;height:auto;border:1px solid var(--line)}.opinion{display:flex;gap:12px;align-items:center;margin-top:14px}.opinion input{min-width:0;flex:1;padding:8px 10px;border:1px solid var(--line);border-radius:6px}.compare-link{display:inline-block;margin-top:8px}.note{color:var(--muted)}footer{padding:24px 0}.toolbar span{font-variant-numeric:tabular-nums}@media(max-width:760px){main{padding:18px}.pair{grid-template-columns:1fr}.section-head{gap:10px}.opinion{align-items:flex-start;flex-direction:column}.opinion input{width:100%}h1{font-size:23px}}
</style><main><header><h1>心域智链 · 逐页方案选择</h1><p>左边原页，右边优化方案。可以逐页选择并导出选择清单，也可以直接把页码和意见发给我。</p><div class="links"><a href="心域智链_18页逐页优化参考稿_20261101.pptx">优化参考PPT</a><a href="'''+pdf_name+'''">优化参考PDF</a><a href="overview/overview-1.png">总览01—06</a><a href="overview/overview-2.png">总览07—12</a><a href="overview/overview-3.png">总览13—18</a></div><nav class="nav" aria-label="页码">'''+nav+'''</nav><div class="toolbar"><span id="selected-count" aria-live="polite">已选择0/18页</span><button id="export" type="button">导出选择清单</button></div></header>'''+''.join(sections)+'''<footer><h2>已保留的模型协作图</h2><p><a href="retained-diagrams/retained-v2.png">第2版示意图</a> · <a href="retained-diagrams/retained-v3.png">第3版示意图</a></p><p class="note">本套为立项答辩逐页审阅候选；原PPT和已选示意图保持。说明与来源保存在PPT备注及配套记录中。</p></footer></main><script>
const sections=Array.from(document.querySelectorAll('section[data-page]'));const storageKey='healthchain-page-review-20261101';let saved={};try{saved=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){}function collect(){return sections.map(s=>({page:Number(s.dataset.page),choice:s.querySelector('select').value,note:s.querySelector('input').value}))}function update(){const items=collect();document.getElementById('selected-count').textContent='已选择'+items.filter(x=>x.choice!=='pending').length+'/18页';try{localStorage.setItem(storageKey,JSON.stringify(Object.fromEntries(items.map(x=>[x.page,x]))))}catch(e){}}for(const s of sections){const v=saved[s.dataset.page];if(v){s.querySelector('select').value=['pending','original','optimized','revise'].includes(v.choice)?v.choice:'pending';s.querySelector('input').value=typeof v.note==='string'?v.note:''}s.querySelector('select').addEventListener('change',update);s.querySelector('input').addEventListener('input',update)}document.getElementById('selected-count').textContent='已选择'+collect().filter(x=>x.choice!=='pending').length+'/18页';document.getElementById('export').addEventListener('click',()=>{const payload={project:'心域智链',reviewSet:'20261101',pages:collect()};const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'}));const link=document.createElement('a');link.href=url;link.download='心域智链_逐页选择清单_20261101.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
</script></html>'''
(OUT/'逐页对照与选择.html').write_text(document,encoding='utf-8')
with (OUT/'逐页改动说明.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['page','title','change']);writer.writeheader()
    writer.writerows({key:r[key] for key in ['page','title','change']} for r in comparisons)
selection_template={'owner':'A / Lead','version':'1.0','updated':'2026-11-01','project':'心域智链','status':'blank-for-user-selection','pages':[{'page':r['page'],'title':r['title'],'choice':'pending','note':''} for r in comparisons]}
(OUT/'逐页选择清单_空白.json').write_text(json.dumps(selection_template,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'README.md').write_text('# 逐页优化预览\n\n> owner: A / Lead ｜ version: 1.0 ｜ status: 供用户逐页选择 ｜ updated: 2026-11-01\n\n打开[逐页对照与选择](逐页对照与选择.html)，每页左侧原版、右侧优化。可选保留原页、采用优化页或继续调整，再导出选择清单；也可直接把页码意见发给我。\n\n`comparison/`为18张原版/优化对照图，`pdf-pages/`为18张优化预览，`overview/`为3张总览。参考PPT的文字与流程可编辑；部分数据图和界面截图沿原素材保留。既有三学段原生图表数值保持。`retained-diagrams/`保存此前用户选择的第2、3版模型示意图。\n\n这是立项审阅候选，尚未替换原PPT；真实模型、专业、学校试点与生产状态不因材料预览改变。\n',encoding='utf-8')
record={'owner':'A / Lead','version':'1.0','updated':'2026-11-01','status':'candidate-user-review','pages':comparisons,'sourceSha256':build['sourceSha256'],'candidateSha256':build['candidateSha256'],'pdfSha256':SHA(OUT/pdf_name),'originalNativeRenderSourceVerified':True,'optimizedPipeline':'PowerPoint read-only SaveAs PDF -> Poppler 96dpi PNG','retainedSelectionHashesVerified':True,'html':'逐页对照与选择.html','comparisonCount':18,'overviewCount':3,'htmlExternalResources':0}
(HERE/'package-record.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pages':18,'comparisonImages':len(comparisons),'overviews':3,'html':str(OUT/'逐页对照与选择.html')},ensure_ascii=False))
