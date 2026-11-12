"""Create the requested PPT outline as editable Word and Markdown, without slides."""
import argparse  # noqa: I001
import json
from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
OUTLINE=[
('项目名称与定位',[
 '项目名称：心域智链校园心理支持协作平台；申报方向为高校心理测评与后续支持协作。',
 '介绍测评入口、结果说明、授权教师复核、求助答复与跟进记录之间的关系。',
 '负责人、团队、学院专业、导师、周期和经费均保留【待填写】。']),
('我国高校学生心理情况',[
 '介绍2024年3—6月60,782名16—28岁本科生调查，说明低年级受访者风险相对较高、同伴支持与较低风险相关。',
 '样本中80.0%知道学校提供免费咨询，2.8%曾经使用；这是不同调查题目，不能计算转化率或全国患病率。',
 '据此提出需求假设：测评结束后，学生是否能理解结果、找到支持入口，并得到适当的人工承接。']),
('学校心理健康建设现状',[
 '实际进展：教育部2025年通报，全国学生心理健康监测平台首次监测覆盖150万名学生。',
 '政策脉络：2023—2025专项行动计划、2025中小学十条措施、2026健康学校建设指导。',
 '区分已开展的监测、政策目标和逐校落实情况；不声称全国学校已全部建成或达到配置目标。']),
('高校与初高中市场背景',[
 '2025年高校3,167所，普通/职业本专科学生3,953.96万人；高校校数含成人高校，两项口径不能用于计算校均人数。',
 '普通高中1.61万所、3,039.50万人；初中5.16万所、5,509.34万人，初中人数含一贯制等学校初中段。',
 '教育规模用于说明服务体量；高校为首要场景，初中和高中独立论证，不将学生数直接转化为收入。']),
('高校测评与后续支持流程',[
 '建议展示五步流程：组织测评、结果说明、教师复核、支持衔接、记录跟进。',
 '学校和专业人员确认测评工具来源、适用对象、授权、解释规则与异常结果处理。',
 'AI仅作为经审批的辅助信息支持；不承担测评解释、诊断或风险裁定。']),
('学生端功能大纲',[
 '入口：了解测评目的与适用边界，进入经学校选定和批准的测评工具。',
 '记录：查看本人测评与支持事项，向教师留言、预约咨询并查看答复或状态。',
 '如后期配图，仅使用已登记合成界面，并标注合成数据；不作为真实使用效果证据。']),
('教师端功能大纲',[
 '在明确分配范围内查看相关学生与事项，不能用自由填写的advisor字段作为授权。',
 '复核预警、记录动作与原因，答复学生留言，建立和完成内部跟进任务。',
 '按单个授权学生导出资料；校内值守、人工处置及责任人员仍需学校确认。']),
('技术架构与数据权限',[
 '架构：Vue 3前端、FastAPI授权接口、SQLite本机工程副本，目前27张表。',
 '权限：服务端校验身份、角色、资源及独立师生分配，保留业务操作记录。',
 '隔离评测只处理合成案例；生产身份接入、Linux/TLS、安全及恢复单独验收。']),
('替代方案与项目定位',[
 '对照人工表单/线下服务、校园内容平台和专业测评工具所覆盖的环节。',
 '本项目的待验证定位是测评后信息衔接、明确授权、教师复核和可追溯跟进。',
 '先核实学校已有系统及实际流程，再讨论协作价值、接入方式和持续成本。']),
('初中与高中的独立需求',[
 '初中：青春期成长适应、同伴关系、主动求助及适当家校沟通。',
 '普通高中：入学适应、考试和升学阶段支持、教师复核与专业转介。',
 '两个学段均需适龄工具、学生告知、适用监护安排、数据边界和人工承接；当前无中学版本、家长端或获批中学试点。']),
('公开采购与市场路径',[
 '高校案例：四川邮电职业技术学院测评软件11.47万元；中国劳动关系学院智能测评与综合服务45万元。',
 '区域案例：龙泉驿合计65.3万元，拆为测评40.7万元和筛查后干预24.6万元；成都教科院96.5万元含至少20万人抽样、报告和转介支持。',
 '上述均为2026年公告，采购范围及周期不同，不计算均价，不直接作为本项目报价、预算或收入预测。']),
('高校市场进入步骤',[
 '从学校心理中心、学工部门的真实任务出发，联合信息化与运维人员梳理范围。',
 '先做隔离环境验证，再在专业、隐私、业务责任和停止条件明确后提交试点方案。',
 '由采购和维护责任单位核实成本与长期服务能力，不预设客户数、转化率或合同。']),
('实施阶段与交付成果',[
 '需求确认：流程、工具、告知、数据和职责清单，由校内业务及专业负责人确认。',
 '隔离复验与试点准备：权限、浏览器、备份恢复证据，以及指标、停止机制和响应方案。',
 '生产评审：Linux/TLS、容量、异机恢复与运维交接；周期和人员由负责人据实际资源填写。']),
('已有成果与待解决任务',[
 '已有工程证据：22项前端单元测试、38个合成页面场景、30项文章交互检查通过。',
 '最新完整后端为135通过、3条件跳过、5项WinError 10013环境错误；最新真实UI因Vite代理EACCES未通过完整整合复验。',
 '待完成：稳定环境复验、专业工具适配、真实模型评测、生产部署及学校试点批准。']),
('团队分工与预算框架',[
 '分工围绕研发整合、学校业务、专业审阅、隐私安全及部署运维展开，真实成员和导师后期手填。',
 '预算按算力/API、部署存储与备份、测评工具及专业评审、测试运维、培训和材料等真实需求核算。',
 '金额、单价、用量、周期和资金来源均待核实；一次性支出与持续运行成本分开。']),
('申报目标与下一步',[
 '交付围绕高校测评后理解、复核与支持衔接的可复验工程原型和实施材料。',
 '先确认学校业务与专业责任，完成稳定隔离环境复验，再按批准条件开展可用性验证。',
 '提交前由负责人补齐真实字段、来源与资格证明，核实签章；不把工程原型表述为已上线服务。']),
]


def build(output, markdown):
    if output.exists():
        raise ValueError('Use a new draft output path')
    doc=Document()
    s=doc.sections[0]
    s.page_width=Cm(21);s.page_height=Cm(29.7)  # noqa: E702
    s.top_margin=s.bottom_margin=Cm(2.3)
    s.left_margin=s.right_margin=Cm(2.5)
    s.header_distance=s.footer_distance=Cm(1.2)
    for style_name in ('Normal','Title','Heading 1','Heading 2','List Bullet'):
        st=doc.styles[style_name]
        st.font.name='宋体'
        st._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'宋体')
        st.font.size=Pt(11.5);st.font.color.rgb=RGBColor(0,0,0)  # noqa: E702
        st.paragraph_format.line_spacing=1.15
        st.paragraph_format.space_after=Pt(4)
    doc.styles['Title'].font.name='黑体';doc.styles['Title'].font.size=Pt(20)  # noqa: E702
    doc.styles['Title']._element.rPr.rFonts.set(qn('w:eastAsia'),'黑体')
    doc.styles['Heading 2'].font.bold=True;doc.styles['Heading 2'].font.size=Pt(13)  # noqa: E702
    doc.styles['Heading 2'].paragraph_format.space_before=Pt(11)
    doc.styles['Heading 2'].paragraph_format.keep_with_next=True
    for old in list(doc.styles.element.xpath('.//w:pBdr')):
        old.getparent().remove(old)
    header=s.header.paragraphs[0];header.text='心域智链项目申报答辩大纲'  # noqa: E702
    header.runs[0].font.size=Pt(9)
    footer=s.footer.paragraphs[0];footer.alignment=2  # noqa: E702
    fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)  # noqa: E702
    doc.add_paragraph('心域智链项目答辩大纲','Title')
    doc.add_paragraph('本文件提供16个建议页面的主题和要点，供后续自行制作PPT。首期聚焦高校心理测评与后续支持，初中和高中为独立拓展分析。统计和采购来源见申报书参考资料。')
    lines=['# 心域智链项目答辩大纲','','> owner: A ｜ version: 1.1 ｜ status: 仅交付大纲，暂不制作PPT ｜ updated: 2026-10-27','','16个建议页面，供后续自行制作PPT。高校心理测评为主场景，初高中单独论证；真实人员、导师、周期和经费后期手填。数据与采购口径见[市场分析](../plan/学生心理测评市场分析.md)及[来源元数据](../plan/市场分析来源.json)。','']
    for i,(title,bullets) in enumerate(OUTLINE,1):
        if i in (5,9,13):doc.add_page_break()  # noqa: E701
        doc.add_paragraph(f'{i:02d} {title}','Heading 2')
        lines.extend([f'## {i:02d} {title}',''])
        for b in bullets:
            p=doc.add_paragraph(b,'List Bullet')
            p.paragraph_format.keep_together=True
            lines.append('- '+b)
        lines.append('')
    output.parent.mkdir(parents=True,exist_ok=True)
    for old in list(doc.element.xpath('.//w:pBdr')):
        old.getparent().remove(old)
    doc.save(output)
    markdown.write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'output':str(output),'outlineSections':16,'tables':0},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--markdown',type=Path,default=ROOT/'docs/ppt/答辩方案.md')
    a=p.parse_args();build(a.output,a.markdown)  # noqa: E702
