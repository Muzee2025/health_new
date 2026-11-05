"""Build an editable 18-page review candidate; original deck remains untouched."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import subprocess
import os
from pathlib import Path
from PIL import Image, ImageFont
from pptx import Presentation as ReadPresentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx_designer import Presentation, validate_resolved_theme
from pptx_designer.renderer.theme import ThemeComposer
from pptx_designer.tools.text import text
from pptx_designer.tools.shapes import rect, rrect, arrow
from pptx_designer.tools.images import cover_image
import pptx_designer

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
WORK = ROOT / 'tmp/ppt-page-preview-20261101'
OUT = ROOT / 'deliverables/逐页优化预览_20261101'
SOURCE = ROOT / 'deliverables/心域智链_六章答辩PPT_多智能体协作机制优化版_20261031.pptx'
EXPECTED = '3651273bde057b992dd083ed101c8bbd7dfa223c8742446e140ba7dd52698a1b'
NODE = Path('C:/Users/14012/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
NODE_MODULES = 'C:/Users/14012/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'
FONT = 'Microsoft YaHei'
SIZE = 24
W, H = 16.6666666667, 9.375
SHA = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

token_source = (ROOT / 'src/styles/tokens.css').read_text(encoding='utf-8')
def token(name):
    return re.search(r'--' + re.escape(name) + r':\s*(#[0-9A-Fa-f]{6})\s*;', token_source).group(1)[1:]
C = dict(ink=token('gray-800'), purple=token('brand-600'), soft=token('brand-100'),
         light=token('brand-50'), sage=token('accent-sage-soft'), sage_dark=token('gray-700'),
         border=token('gray-200'), muted=token('gray-600'), white=token('gray-0'))

PLAN = [
 ('项目概览', '心域智链', '扩大项目插画，集中定位和团队信息，取消外框'),
 ('1 实用性与创新力', '高校规模与政策背景', '保留原始数据图，政策改成按年排列，原网页图放备注备查'),
 ('1 实用性与创新力', '学生心理支持中的三个困境', '保留三张情境照片，统一裁剪区域和居中说明'),
 ('2 产品与服务', '学生端：测评记录与求助操作', '截图等比例放大，操作步骤压缩为两条清晰路径'),
 ('2 产品与服务', '教师端：核对答复与持续跟进', '两个工作界面独立展示，权限和处理步骤对应排列'),
 ('3 市场分析', '全国高校规模与服务衔接需求', '保留完整统计地图，调查两项指标分开陈述'),
 ('3 市场分析', '湖北切入与合作路径', '分开湖北规模、调研任务、采购参照，保留原金额和范围'),
 ('4 推广与实施', '高校先行，按学段适配', '保留原生数据图，三个适配阶段改为清晰流程'),
 ('5 技术创新', '当前原型与拟建AI如何衔接', '测评链与主动求助链分区，保留当前记录绑定和人工边界'),
 ('5 技术创新', '本地多智能体协作（拟建）', '六类任务写清角色、支撑模型及工作，居中并加粗角色/模型'),
 ('5 技术创新', '同一条求助的协作过程（示意）', '虚构案例独立成句，六行输出按原文证据整理'),
 ('5 技术创新', '分歧、缺失与人工复核（拟建）', '普通核查与紧急支路分开，不用投票补事实'),
 ('5 技术创新', '本地候选模型与职责', '将旧云端模型表换成本聊天核对的三种开源候选及分工'),
 ('5 技术创新', '情绪线索与五维展示（拟建）', '保留原文映射，未知项和明确表达以文字区分'),
 ('5 技术创新', '纵向记录与RAG检索（拟建）', '授权记录、筛选、召回、重排、摘要及人工复核用原生流程展示'),
 ('5 技术创新', '规则提示与危机复核联动', '四步处理路径放大，异常处理与规则局限压缩说明'),
 ('5 技术创新', '敏感数据处理与教师提醒（拟建）', '四项算法设计分区，合成记录核算与提醒人数分别呈现'),
 ('6 预期成果与发展规划', '阶段成果与后续实施', '当前成果、部署分层和试点顺序分别展示，不写已上线'),
]

WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
ASSETS = WORK / 'assets'
ASSETS.mkdir(exist_ok=True)
assert SHA(SOURCE) == EXPECTED, 'Source changed; review before proceeding'

theme = ThemeComposer().compose(style='minimal', seed=17)
theme['name'] = 'healthchain-page-preview-project-tokens-v1'
theme['colors'].update({'primary':'#'+C['purple'], 'accent':'#'+C['purple'], 'background':'#'+C['white'],
                        'foreground':'#'+C['ink'], 'muted':'#'+C['soft'], 'muted-foreground':'#'+C['muted'],
                        'border':'#'+C['border']})
theme['typography'] = {'heading':FONT, 'body':FONT}
theme['semantic_roles'].update({'background':'#'+C['white'], 'surface':'#'+C['soft'], 'ink':'#'+C['ink'],
    'muted':'#'+C['muted'], 'accent':'#'+C['purple'], 'border':'#'+C['border'],
    'data-series-1':'#'+C['purple'], 'data-series-2':'#'+token('accent-sage')})
theme['source']['project_override'] = 'src/styles/tokens.css; user selected centered lavender diagrams; no preset blue retained'
validate_resolved_theme(theme)
(HERE / 'resolved-theme.json').write_text(json.dumps(theme, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

prs = Presentation(template_path=str(SOURCE), theme=theme, strict_theme=True)
prs.slide_width, prs.slide_height = Inches(W), Inches(H)
original = ReadPresentation(str(SOURCE))
CTX = {'text_body':'#'+C['ink'], 'text_primary':'#'+C['ink'], 'primary':'#'+C['purple'], 'font_body':FONT, 'font_cjk':FONT}
asset_registry, traces = [], []
MEASURE_FONTS={False:ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',32), True:ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc',32)}

def wrap_box_line(value, width, bold):
    font=MEASURE_FONTS[bold]
    limit=(width-.26)*96
    result=[]; current=''
    for ch in value:
        if current and font.getlength(current+ch)>limit:
            result.append(current); current=ch
        else: current+=ch
    if current or not result: result.append(current)
    return result

def image_asset(page, shape_index):
    shape = original.slides[page-1].shapes[shape_index]
    blip = next(iter(shape._element.xpath('.//a:blip')), None)
    svg_nodes = [e for e in shape._element.iter() if e.tag.endswith('}svgBlip')]
    if svg_nodes:
        rel = svg_nodes[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
        raw = shape.part.related_part(rel).blob
        ext = 'svg'
    else:
        raw, ext = shape.image.blob, shape.image.ext
    digest = hashlib.sha256(raw).hexdigest()
    source = ASSETS / f'{digest[:20]}.{ext}'
    if not source.exists(): source.write_bytes(raw)
    output = source
    if ext == 'svg':
        output = source.with_suffix('.png')
        if not output.exists():
            code = "const sharp=require('sharp');sharp(process.argv[1],{density:180}).png().toFile(process.argv[2]).catch(e=>{console.error(e);process.exit(1)});"
            env = dict(os.environ, NODE_PATH=NODE_MODULES)
            subprocess.run([str(NODE), '-e', code, str(source), str(output)], check=True, env=env, cwd=ROOT)
    asset_registry.append({'sourcePage':page, 'sourceShapeIndex':shape_index,
        'originalPartSha256':digest, 'extracted':str(source.relative_to(ROOT)).replace('\\','/'),
        'rendered':str(output.relative_to(ROOT)).replace('\\','/'),
        'sourceRegistry':'docs/ppt/six-chapters-20261029/revision-r6/selected-assets.json'})
    return output

def T(sl, x, y, w, h, value, bold=False, color=None, align='center', size=SIZE):
    box = text(sl, x, y, w, h, value, font_size=size, color='#'+(color or C['ink']), bold=bold,
               align=align, font_name=FONT, C=CTX, anchor='middle')
    box.text_frame.margin_left = box.text_frame.margin_right = Inches(.02)
    box.text_frame.margin_top = box.text_frame.margin_bottom = 0
    for p in box.text_frame.paragraphs:
        p.space_before = p.space_after = Pt(0)
        p.line_spacing = 1.05
    return box

def B(sl, x, y, w, h, rows, fill=None):
    rrect(sl, x, y, w, h, '#'+(fill or C['soft']), line=None, C=CTX)
    parsed=[]
    for row in rows:
        val,bold = row if isinstance(row,tuple) else (row,False)
        for line in val.split('\n'):
            parsed.extend((part,bold) for part in wrap_box_line(line,w,bold))
    line_h=.43
    top=y+(h-line_h*len(parsed))/2
    for j,(val,bold) in enumerate(parsed): T(sl,x+.13,top+j*line_h,w-.26,line_h,val,bold)

def L(sl, x1, y1, x2, y2, arrowhead=True, width=3):
    shape=sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    shape.line.color.rgb=RGBColor.from_string(C['purple'])
    shape.line.width=Pt(width)
    if arrowhead:
        tail=OxmlElement('a:tailEnd'); tail.set('type','triangle'); tail.set('w','med'); tail.set('len','med')
        shape.line._get_or_add_ln().append(tail)
    return shape

def lines(sl, x,y,w,rows, align='center', step=.53):
    for i,row in enumerate(rows):
        val,bold=row if isinstance(row,tuple) else (row,False)
        T(sl,x,y+i*step,w,.45,val,bold,align=align)

def contain(sl, image, x,y,w,h):
    with Image.open(image) as im: iw,ih=im.size
    ratio=min(w/iw,h/ih); nw,nh=iw*ratio,ih*ratio
    cover_image(sl,x+(w-nw)/2,y+(h-nh)/2,nw,nh,str(image))

def table(sl,x,y,width,rows,widths=None,row_h=.68):
    widths=widths or [width/len(rows[0])]*len(rows[0])
    rect(sl,x,y,width,row_h,'#'+C['soft'],line=None,C=CTX)
    L(sl,x,y,x+width,y,False,1)
    for r,row in enumerate(rows):
        cx=x
        for c,val in enumerate(row):
            T(sl,cx+.07,y+r*row_h+.04,widths[c]-.14,row_h-.08,val,bold=r==0)
            cx+=widths[c]
        if r==0 or r==len(rows)-1: L(sl,x,y+(r+1)*row_h,x+width,y+(r+1)*row_h,False,1)

def footer(sl, value): T(sl,.8,8.77,14.5,.35,value,color=C['muted'])

def header(sl, index, title=None):
    chapter,subject,_=PLAN[index-1]
    T(sl,.8,.30,13.7,.45,chapter,color=C['muted'],align='left')
    T(sl,.8,.98,14.8,.58,title or subject,True,C['purple'],align='left')
    T(sl,14.85,.30,1.0,.45,f'{index:02d}/18',color=C['muted'])

for i,sl in enumerate(prs.slides,1):
    old=original.slides[i-1]
    old_text=[]
    for shape in old.shapes:
        if shape.has_text_frame: old_text.append(shape.text)
        if shape.has_table: old_text.extend(' | '.join(c.text for c in r.cells) for r in shape.table.rows)
    notes=old.notes_slide.notes_text_frame.text
    chart_to_keep=next((s for s in sl.shapes if s.has_chart),None) if i==8 else None
    for shape in list(sl.shapes):
        if chart_to_keep is None or shape._element is not chart_to_keep._element:
            sl.shapes._spTree.remove(shape._element)
    sl.background.fill.solid(); sl.background.fill.fore_color.rgb=RGBColor.from_string(C['white'])
    sl.notes_slide.notes_text_frame.text=notes+'\n\n【2026-11-01逐页优化预览】\n'+PLAN[i-1][2]+'。本稿为立项视觉候选，新增本地模型及协作均为拟建，不构成真实部署、临床效果或生产批准。\n【原页可见内容备查】\n'+'\n'.join(old_text)
    if i!=1: header(sl,i)

    if i==1:
        # Existing registered illustration remains the main visual; no new stock art.
        contain(sl,image_asset(1,2),7.8,2.0,8.0,5.0)
        lines(sl,.85,2.2,6.65,[('心域智链',True),('AI+校园心理支持协作平台',True),
              '连接测评记录、学生求助','与教师跟进'],align='left',step=.68)
        lines(sl,.85,6.05,14.5,['队长：周秋宇','队员：韩沐泽  甘思琪  徐婉婷  陈智勇','专业：会计ACA'],align='left',step=.63)
        T(sl,14.85,.30,1.0,.45,'01/18',color=C['muted'])
    elif i==2:
        T(sl,.85,1.9,8.3,.5,'2024年本专科在校生规模（前12省）',True)
        contain(sl,image_asset(2,7),.85,2.55,8.3,5.55)
        for yy,year,body in [(2.45,'2023—2025','开展测评，科学使用结果'),(4.25,'2025','首次监测覆盖150万名学生'),(6.05,'2026','完善监测预警与服务网络')]:
            B(sl,9.9,yy,5.9,1.3,[(year,True),body])
        footer(sl,'教育部地区统计；单位：万人。政策出处保留原页备注。')
    elif i==3:
        xs=[.85,6.05,11.25]
        titles=['求助入口与服务衔接','夜间记录与后续回应','AI回复与个人语境']
        details=[['入口清楚、事项可提交','分配、预约、答复相衔接'],['先记录压力与睡眠困扰','校内人员按服务安排回应'],['呈现原文依据和资料缺口','教师核对后决定支持方式']]
        for x,j,title,body in zip(xs,[7,10,13],titles,details):
            T(sl,x,1.95,4.57,.55,title,True,C['purple'])
            cover_image(sl,x,2.75,4.57,3.1,str(image_asset(3,j)))
            lines(sl,x,6.25,4.57,body,step=.65)
        footer(sl,'情境照片为素材模特，不代表真实学生；摄影及许可见备注。')
    elif i==4:
        for x,j,title,body in [(.85,6,'测评与记录',['选择工具并完成作答','查看本次结果与来源','按需获取AI说明']), (8.7,7,'留言、预约与答复',['描述希望沟通的事项','查看分配或预约状态','回看教师答复与处理状态'])]:
            T(sl,x,1.9,7.1,.5,title,True,C['purple'])
            cover_image(sl,x,2.6,7.1,3.95,str(image_asset(4,j)))
            lines(sl,x,6.75,7.1,body,step=.52)
        footer(sl,'项目界面使用合成演示数据；本人记录按权限显示。')
    elif i==5:
        for x,j,title,body in [(.85,6,'核对事项并答复',['仅查看明确分配的学生','核对原文和时间后撰写答复','确认发送，按需创建跟进']), (8.7,7,'跟进任务与处理结果',['记录摘要、状态和计划时间','回查原文，记录沟通结果','内部备注与学生答复分开'])]:
            T(sl,x,1.9,7.1,.5,title,True,C['purple'])
            contain(sl,image_asset(5,j),x,2.6,7.1,3.95)
            lines(sl,x,6.75,7.1,body,step=.52)
        footer(sl,'界面数据为合成演示，答复为未发送草稿。')
    elif i==6:
        contain(sl,image_asset(6,6),.85,1.85,14.95,5.9)
        B(sl,.85,7.95,7.1,.62,['80.0%知晓免费心理咨询'])
        B(sl,8.7,7.95,7.1,.62,['2.8%曾使用免费心理咨询'])
        footer(sl,'同一调查的两道题，不能直接相减作为未满足需求人数。')
    elif i==7:
        B(sl,.85,1.95,6.1,1.0,[('湖北2024年133所高校',True),'本专科在校生191.52万人'])
        table(sl,.85,3.35,6.1,[['调研任务','拟承担工作'],['理解测评记录','解释来源与资料缺失'],['找到对应人员','留言预约与分配答复'],['持续跟进','待办、备注与状态']],widths=[2.65,3.45],row_h=.88)
        T(sl,7.8,1.98,8.0,.55,'2026年公开采购辅助参照',True,C['purple'])
        table(sl,7.8,2.8,8.0,[['采购范围','成交金额'],['四川邮电职院：软件','11.47万元'],['中国劳动关系学院：系统等','45万元'],['龙泉驿区：测评与干预两包','65.3万元'],['成都教科院：区域服务','96.5万元']],widths=[5.6,2.4],row_h=.75)
        T(sl,7.8,7.1,8.0,1.05,'合作路径：需求调研 → 权限与部署确认\n→ 按校内程序验证',align='center')
        footer(sl,'各采购范围不同，金额仅作参照；缺口人数仍需校内调查。')
    elif i==8:
        chart=chart_to_keep
        chart.left,chart.top,chart.width,chart.height=map(Inches,[.85,2.3,8.8,4.85])
        for axis in [chart.chart.category_axis,chart.chart.value_axis]:
            axis.tick_labels.font.name=FONT; axis.tick_labels.font.size=Pt(SIZE)
        T(sl,.85,1.9,8.8,.5,'2025年各学段在校生规模（万人）',True)
        for y,title,body in [(2.0,'高校先行','验证测评、求助与教师跟进'),(4.1,'高中适配','更换适龄工具与支持内容'),(6.2,'初中推广','调整表达、职责与家校流程')]:
            B(sl,10.3,y,5.5,1.45,[(title,True),body])
        T(sl,.85,7.5,8.8,.9,'高校3,167所｜普通高中1.61万所\n初中5.16万所')
        footer(sl,'工具、告知、监护及人工承接按学段确认后逐校验证。')
    elif i==9:
        T(sl,.85,1.83,14.95,.5,'测评与当前记录说明',True,C['purple'])
        for j,rows in enumerate([[('原始选项',True),'本人身份与题本'],[('服务器计分',True),'保存并返回本次ID'],[('当前答卷说明',True),'绑定同一份记录'],[('学生查看',True),'分值、来源与局限']]):
            x=.85+j*3.9; B(sl,x,2.6,3.25,1.6,rows)
            if j<3:L(sl,x+3.32,3.4,x+3.83,3.4)
        T(sl,.85,4.75,14.95,.5,'主动求助与人工服务',True,C['purple'])
        for j,rows in enumerate([[('主动留言或预约',True),'学生自主填写事项'],[('分配范围内答复',True),'教师核对原文'],[('跟进与留痕',True),'记录状态与处理结果']]):
            x=.85+j*5.2; B(sl,x,5.55,4.55,1.8,rows,fill=C['sage'])
            if j<2:L(sl,x+4.62,6.45,x+5.13,6.45)
        footer(sl,'本次ID说明已有原型；RAG和多智能体仍为拟建扩展。')
    elif i==10:
        rows=[('语义理解专家','Qwen3-8B','提取事件、时间与否定'),('情绪线索专家','Qwen3-8B','整理压力与睡眠等表达'),('认知线索专家','Qwen3-8B','形成带原文的表达假设'),('纵向记录专家','Qwen3-Embedding-0.6B','召回本人记录并按时归并'),('风险复核专家','Qwen3-8B＋规则','核对分歧与待审事项'),('资源检索专家','Embedding＋Reranker','召回并排序支持资料')]
        for j,(title,model,body) in enumerate(rows):
            col=j%2; row=j//2; x=.85 if col==0 else 8.8; y=2.05+row*2.0
            sh=arrow(sl,x,y,7.0,1.65,'#'+C['soft'],line=None,C=CTX)
            sh.adjustments[0]=1.0
            if col: sh.rotation=180
            cx=x+3.18 if col==0 else x+3.82
            lines(sl,cx-2.95,y+.17,5.9,[(title,True),(model,True),body],step=.43)
        B(sl,6.7,1.55,3.25,.48,[('协调器',True)],fill=C['light'])
        L(sl,8.32,2.03,8.32,8.12)
        B(sl,6.6,8.15,3.4,.55,[('输出结果',True)],fill=C['sage'])
        footer(sl,'六类任务复用三套候选模型；紧急线索优先交人工。')
    elif i==11:
        B(sl,.85,1.9,14.95,.82,['虚构求助：期末快到了，我肯定会考砸，最近总睡不着。'])
        table(sl,.85,3.05,14.95,[['角色','读取依据','本例输出（待核验）'],['语义理解','本人授权求助文本','考试担忧、近期睡眠困扰'],['情绪线索','原文与时间','压力与睡眠表达；附引用'],['认知线索','“我肯定会考砸”','候选表达假设，不作诊断'],['纵向分析','本例未提供历史','资料不足，不补造趋势'],['风险复核','原文及各角色结果','时长与影响程度待补充'],['资源匹配','经核对线索及资源库','补充提问与求助入口草稿']],widths=[2.6,5.2,7.15],row_h=.70)
        footer(sl,'虚构案例未调用模型；完整对话不向所有角色广播。')
    elif i==12:
        for j,rows in enumerate([[('各角色回传',True),'引用、结论与待核验项'],[('协调器核对',True),'原文、时间及依据范围'],[('人工确认',True),'核对草稿后使用']]):
            x=.85+j*5.2; B(sl,x,2.25,4.55,1.55,rows)
            if j<2:L(sl,x+4.61,3.03,x+5.12,3.03)
        data=[('表述冲突','回查原文并重新分析'),('历史缺失或任务失败','保留未知或失败状态'),('紧急线索','优先进入授权人工流程')]
        for j,(title,body) in enumerate(data):
            x=.85+j*5.2; B(sl,x,5.3,4.55,1.8,[(title,True),body],fill=C['sage'] if j==2 else C['light'])
        L(sl,8.3,3.9,8.3,4.7,False); L(sl,3.1,4.7,13.5,4.7,False)
        for x in [3.1,8.3,13.5]:L(sl,x,4.7,x,5.2)
        T(sl,11.7,1.65,4.1,.5,'任一阶段紧急线索',True,C['purple'])
        L(sl,15.8,1.9,16.05,1.9,False)
        L(sl,16.05,1.9,16.05,6.2,False)
        L(sl,16.05,6.2,15.8,6.2)
        footer(sl,'紧急线索不等待普通汇总；分歧不靠投票补齐事实。')
    elif i==13:
        specs=[('语言理解与摘要','Qwen3-8B','4bit量化候选','语义、情绪与认知线索','带引用的摘要草稿'),('文本向量召回','Qwen3-Embedding-0.6B','小型文本向量模型','检索授权记录与资料','返回相关片段'),('文本相关性重排','Qwen3-Reranker-0.6B','小型文本重排模型','对候选片段排序','不产生心理风险分')]
        for j,spec in enumerate(specs):
            x=.85+j*5.2
            B(sl,x,2.5,4.55,4.8,[(spec[0],True),(spec[1],True),spec[2],spec[3],spec[4]])
        footer(sl,'本地部署为拟建方案；版本、上下文、并发和效果仍待实测。')
        sl.notes_slide.notes_text_frame.text += '\n【本聊天新增模型依据】\nhttps://huggingface.co/Qwen/Qwen3-8B-GGUF\nhttps://huggingface.co/Qwen/Qwen3-Embedding-0.6B\nhttps://huggingface.co/Qwen/Qwen3-Reranker-0.6B\n官方模型卡仅支持模型类型与可下载性，不证明本项目已部署或取得专业有效性。'
    elif i==14:
        B(sl,.85,3.15,4.3,2.25,[('虚构表达',True),'期末压力大，','最近总是睡不着。'])
        B(sl,6.0,3.0,4.4,2.55,[('语义处理',True),'提取原文、时间与否定','保留来源及缺失信息'])
        L(sl,5.22,4.3,5.9,4.3); L(sl,10.47,4.3,11.1,4.3)
        table(sl,11.2,2.25,4.6,[['维度','本例依据'],['压力','明确表达'],['焦虑','资料不足'],['低落情绪','资料不足'],['社交孤独','资料不足'],['睡眠困扰','明确表达']],widths=[2.3,2.3],row_h=.86)
        footer(sl,'五维为拟建线索展示；不生成疾病概率或量表分数。')
    elif i==15:
        T(sl,.85,2.0,3.7,.5,'本人授权记录',True,C['purple'])
        for y,label in [(3.05,'测评记录'),(4.9,'主动表达'),(6.75,'跟进反馈')]:B(sl,.85,y,3.7,1.15,[(label,True)])
        B(sl,6.05,1.75,4.75,.6,[('本次问题',True)])
        B(sl,6.05,2.85,4.75,1.15,[('权限与时间筛选',True),'限定可用记录'])
        B(sl,6.05,4.6,4.75,1.55,[('向量召回',True),('Qwen3-Embedding-0.6B',True),'输出：相关记录'])
        B(sl,6.05,6.75,4.75,1.55,[('相关性重排',True),('Qwen3-Reranker-0.6B',True),'输出：排序片段'])
        for y in [3.63,5.48,7.33]:L(sl,4.6,y,5.2,y,False)
        L(sl,5.2,3.43,5.2,7.33,False); L(sl,5.2,3.43,5.95,3.43)
        L(sl,8.42,2.35,8.42,2.75); L(sl,8.42,4.0,8.42,4.5); L(sl,8.42,6.15,8.42,6.65)
        B(sl,12.0,2.8,3.8,1.65,[('摘要生成',True),('Qwen3-8B',True),'保留原文引用与日期'])
        B(sl,12.0,5.3,3.8,1.35,[('教师复核',True),'核对原文与缺失信息'])
        B(sl,12.0,7.6,3.8,.7,[('输出结果',True)],fill=C['sage'])
        L(sl,10.9,7.53,11.4,7.53,False); L(sl,11.4,7.53,11.4,3.62,False); L(sl,11.4,3.62,11.9,3.62)
        L(sl,13.9,4.45,13.9,5.2); L(sl,13.9,6.65,13.9,7.5)
        footer(sl,'拟扩展纵向检索；权限与时间筛选由应用实现。')
    elif i==16:
        stages=[('对话规则触发','登录且非匿名会话','出现需关注线索'),('保存待审记录','确认实际保存成功','界面提示创建状态'),('分配范围内待审','仅授权教师可查看','通知接收需确认'),('人工复核与跟进','核对原文并留痕','按职责安排支持')]
        for j,rows in enumerate(stages):
            x=.85+j*3.9; B(sl,x,2.65,3.25,2.4,[(rows[0],True),rows[1],rows[2]])
            if j<3:L(sl,x+3.32,3.85,x+3.83,3.85)
        B(sl,.85,6.35,7.1,1.15,[('保存失败',True),'如实显示未创建记录'],fill=C['light'])
        B(sl,8.7,6.35,7.1,1.15,[('模型或资料不足',True),'保留支持提示和人工核查'],fill=C['light'])
        footer(sl,'规则命中是待审线索；风险级别仍需专业校准。')
    elif i==17:
        blocks=[('身份与文本保护','HMAC稳定假名；NER＋正则','密钥与身份映射隔离'),('去重与质量检查','事件ID与HMAC辅助去重','核验时间、来源和工具版本'),('AI线索与演示规则','中文RoBERTa为候选分类器','14天重复表达为演示规则'),('教师复核与跟进','摘要附原文、时间和缺口','确认、驳回或升级并留痕')]
        for j,rows in enumerate(blocks):
            x=.85+(j%2)*7.85; y=2.05+(j//2)*2.05
            B(sl,x,y,7.1,1.65,[(rows[0],True),rows[1],rows[2]])
        table(sl,.85,6.55,14.95,[['原始记录','去除重复','缺失待核','有效记录'],['4,100条','100条','100条','3,900条']],row_h=.59)
        T(sl,.85,8.0,14.95,.5,'1,000名虚拟学生：120＋80－40＝160名待复核')
        footer(sl,'合成规则演示，不是检出率、真实通知或模型效果。')
    elif i==18:
        table(sl,.85,2.25,7.4,[['成果项','当前进展'],['学生测评、记录与求助','已有原型'],['教师权限、答复与跟进','已有原型'],['AI与隐私算法、专业效果','待验证'],['服务器部署与校内试点','待确认']],widths=[5.45,1.95],row_h=.83)
        T(sl,9.1,1.95,6.7,.5,'部署分层（拟）',True,C['purple'])
        for j,label in enumerate(['学校域名、HTTPS与Nginx','Vue前端与FastAPI','本地模型服务','权限数据库与独立备份']):
            B(sl,9.1,2.65+j*1.05,6.7,.7,[(label,True)])
            if j<3:L(sl,12.45,3.35+j*1.05,12.45,3.6+j*1.05)
        T(sl,.85,7.8,14.95,.6,'隔离复验  →  校内责任与范围确认  →  有限试点')
        footer(sl,'预期交付：软件、评测记录、操作培训及部署恢复材料。')
    traces.append({'page':i,'chapter':PLAN[i-1][0],'title':PLAN[i-1][1],'change':PLAN[i-1][2],
                   'nativeShapes':len(sl.shapes),'notesPreserved':bool(notes)})

candidate=OUT / '心域智链_18页逐页优化参考稿_20261101.pptx'
prs.save(str(candidate))
assert SHA(SOURCE)==EXPECTED
source_chart=list(original.slides[7].shapes)[0] if False else next(s for s in original.slides[7].shapes if s.has_chart)
chart_source=[list(s.values) for s in source_chart.chart.series]
chart_final=next(s for s in ReadPresentation(str(candidate)).slides[7].shapes if s.has_chart)
assert chart_source==[list(s.values) for s in chart_final.chart.series]
manifest={'owner':'A / Lead','version':'1.0','updated':'2026-11-01','status':'candidate-user-review',
    'brief':'当前18页每页一张优化预览；不是15份历史PPT分别优化。六章顺序保持，原PPT不覆盖。',
    'source':str(SOURCE.relative_to(ROOT)).replace('\\','/'),'sourceSha256':EXPECTED,
    'candidate':str(candidate.relative_to(ROOT)).replace('\\','/'),'candidateSha256':SHA(candidate),
    'slideCount':len(prs.slides),'canvasInches':[W,H],'nativeFont':FONT,'nativeTextPt':SIZE,
    'theme':{'path':'docs/ppt/page-preview-20261101/resolved-theme.json','sha256':SHA(HERE/'resolved-theme.json'),
             'version':'1.0','packageVersion':pptx_designer.__version__,'packagePath':pptx_designer.__file__,'seed':17},
    'originalChartDataPreserved':chart_source,'pages':traces,'assets':asset_registry,
    'realModelCalls':0,'businessChanges':False,'independentReview':'pending','renderAndVisualReview':'pending'}
(HERE/'build-record.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'candidate':str(candidate),'slides':len(prs.slides),'assets':len(asset_registry),'sourceUnchanged':True},ensure_ascii=False))
