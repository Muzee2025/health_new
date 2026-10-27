"""Render five statistical charts. Data: chart-data.csv; diagrams are separate HTML."""
import csv, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/plan/ai-application'
QA = ROOT / 'tmp/ai-application-20261027'
sys.dont_write_bytecode = True
sys.path.insert(0, str(QA / 'pydeps'))  # Optional task-local matplotlib installation.
sys.path.insert(0, 'C:/Users/14012/.agents/skills/math-modeling/tools/figure/scripts')
os.environ['MPLCONFIGDIR'] = str(QA / 'mpl-cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from setup_style import setup_style
from export_figure import export_figure
from visual_qa import audit_layout

manifest = json.loads((DATA / 'visual-manifest.json').read_text(encoding='utf-8'))
with (DATA / 'chart-data.csv').open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
values = {r['indicator']: float(r['value']) for r in rows if r['value']}
css = (ROOT / 'src/styles/tokens.css').read_text(encoding='utf-8')
colors = {k: re.search(r'--' + v + r':\s*(#[\da-fA-F]{6})', css)[1] for k, v in
          {'ink':'gray-800', 'purple':'brand-500', 'sage':'accent-sage', 'apricot':'accent-apricot'}.items()}
setup_style(journal='general', lang='zh', use_sciplots=False)
plt.rcParams.update({'font.family':'Microsoft YaHei', 'font.size':9, 'svg.fonttype':'none',
    'axes.spines.top':False, 'axes.spines.right':False, 'text.color':colors['ink'],
    'figure.constrained_layout.use':False, 'figure.autolayout':False})
audits = []

def save(fig, stem, note):
    entry = next(f for f in manifest['figures'] if f['id'] == stem)
    fig.text(.5, .93, entry['title'], ha='center', fontsize=11, fontweight='bold')
    # Full source/scope notes belong in the report appendix.
    audits.append({'id':stem, 'issues':[list(i) for i in audit_layout(fig)]})
    export_figure(fig, str(DATA / 'figures' / stem), formats=['png','svg'], dpi=300,
                  size_inches=tuple(fig.get_size_inches()), tight=False, grayscale_preview=False)
    svg=DATA / 'figures' / (stem+'.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)

def horizontal(stem, labels, keys, xmax, xlabel, note, shades=None):
    fig, ax = plt.subplots(figsize=(5.7, 2.75))
    fig.subplots_adjust(left=.28, right=.94, bottom=.24, top=.83)
    vals = [values[k] for k in keys]
    ax.barh(labels, vals, height=.54, color=shades or colors['purple'],
            edgecolor=colors['ink'], linewidth=.4)
    ax.invert_yaxis(); ax.set(xlim=(0, xmax), xlabel=xlabel)
    for i, v in enumerate(vals):
        text = f'{v:,.2f}' if xmax > 1000 else f'{v:.1f}%'
        ax.text(v + xmax * .012, i, text, va='center', fontsize=8.7)
    save(fig, stem, note)

# A reported bound (<5%) stays text rather than becoming an exact bar.
fig, ax = plt.subplots(1, 2, figsize=(5.7, 3.25))
fig.subplots_adjust(left=.11, right=.98, bottom=.25, top=.81, wspace=.46)
vals = [values[k] for k in ['轻度风险组','高风险组']]
ax[0].bar(['轻度风险','高风险'], vals, color=[colors['sage'],colors['purple']])
for i, v in enumerate(vals): ax[0].text(i, v+1, f'{v:.1f}%', ha='center', fontsize=9)
ax[0].set(ylim=(0,55), ylabel='样本内比例（%）', title='经常或每天不想上学')
ax[0].text(.5, -.22, '无抑郁风险组：<5%', transform=ax[0].transAxes, ha='center', fontsize=8)
for offset, risk, shade in [(-.17,'无风险',colors['sage']),(.17,'高风险',colors['purple'])]:
    vals = [values[risk+'组'+k] for k in ['不做或抄作业','考试作弊']]
    positions = [offset, 1+offset]
    ax[1].bar(positions, vals, .34, label=risk, color=shade, hatch='///' if offset>0 else '')
    for x, v in zip(positions, vals): ax[1].text(x, v+.5, f'{v:g}', ha='center', fontsize=8)
ax[1].set(xticks=[0,1], xticklabels=['不做/抄作业','考试作弊'], ylim=(0,22), title='自陈学习问题（%）')
ax[1].legend(frameon=False, loc='upper right', fontsize=8)
save(fig, 'fig01-youth', '2024年五万余名四年级至高三样本；分组关联，非诊断率或因果效应。')

labels = ['竞争氛围浓厚','同学竞争激烈','学习互相较量','害怕学习落后']
horizontal('fig02-pressure', labels, labels, 105, '受访大学生感知比例（%）',
           '来源：2023中国大学生追踪调查论文；不是焦虑或抑郁症状率。')
labels = ['普通/职业本专科','普通高中','初中学段']
horizontal('fig03-education', labels, labels, 6500, '在校生（万人）',
           '来源：教育部2025年统计；教育体量不代表客户数量或市场收入。',
           [colors['purple'],colors['apricot'],colors['sage']])

# Separate panels preserve the different university and regional delivery scopes.
fig, ax = plt.subplots(1, 2, figsize=(5.7, 3.2))
fig.subplots_adjust(left=.23, right=.97, bottom=.39, top=.76, wspace=1.2)
vals = [values[k] for k in ['四川邮电单项软件','劳动关系学院综合系统']]
ax[0].barh(['单项测评软件','高校综合系统'], vals, height=.5, color=[colors['sage'],colors['purple']])
ax[0].invert_yaxis(); ax[0].set(xlim=(0,55), xlabel='公告金额（万元）', title='高校两类标的')
for i, v in enumerate(vals): ax[0].text(v+1, i, f'{v:g}', va='center', fontsize=8)
measure, support, regional = [values[k] for k in ['龙泉驿测评包','龙泉驿干预包','成都教科院区域服务']]
ax[1].barh(['龙泉驿两包','成都教科院'], [measure,regional], height=.5, color=[colors['purple'],colors['sage']])
ax[1].barh(['龙泉驿两包'], [support], left=[measure], height=.5, color=colors['apricot'], hatch='///')
ax[1].invert_yaxis(); ax[1].set(xlim=(0,115), xlabel='公告金额（万元）', title='区域综合服务')
ax[1].text(measure/2, 0, str(measure), ha='center', va='center', color='white', fontsize=8)
ax[1].text(measure+support/2, 0, str(support), ha='center', va='center', fontsize=8)
ax[1].text(regional+1, 1, str(regional), va='center', fontsize=8)
fig.text(.5, .12, '四川邮电11.47万元 / 中国劳动关系学院45万元\n龙泉驿：测评40.7＋干预24.6；成都教科院：区域测评、报告与转介。', ha='center', fontsize=7.8)
save(fig, 'fig04-procurement', '四项2026年官方公告；范围与周期不同，不计算均价或本项目报价。')

horizontal('fig09-service', ['知道有免费咨询','曾使用免费咨询'],
           ['知晓学校免费心理咨询','曾使用学校免费心理咨询'], 105, '各题报告比例（%）',
           '2024年60,782名本科生调查；两个不同问题，不作转化率或互斥分布。')
(QA / 'figure-layout-audit.json').write_text(json.dumps(audits, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'charts':len(audits), 'rows':len(rows), 'layoutIssues':sum(len(a['issues']) for a in audits)}))
