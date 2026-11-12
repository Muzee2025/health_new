"""Two simple regional comparisons, using the same 2024 MOE data as the report table."""
import csv,json,os,re,sys  # noqa: E401, I001
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];QA=ROOT/'tmp/ai-application-20261027'  # noqa: E702
sys.path.insert(0,str(QA/'pydeps'));sys.path.insert(0,'C:/Users/14012/.agents/skills/math-modeling/tools/figure/scripts')  # noqa: E702
os.environ['MPLCONFIGDIR']=str(QA/'mpl-cache')
import matplotlib  # noqa: E402, I001
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from export_figure import export_figure  # noqa: E402
from visual_qa import audit_layout  # noqa: E402

base=ROOT/'docs/plan/ai-application'
with (base/'revision-20261027/regional-education-2024.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))  # noqa: E701
for r in rows:
    for k in r:
        if k!='region':r[k]=int(r[k])  # noqa: E701
css=(ROOT/'src/styles/tokens.css').read_text(encoding='utf-8')
def color(k):return re.search(r'--'+k+r':\s*(#[\da-fA-F]{6})',css)[1]
purple,sage,apricot,ink=[color(k) for k in ['brand-500','accent-sage','accent-apricot','gray-800']]
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':8.5,'svg.fonttype':'none','text.color':ink,
                     'axes.spines.top':False,'axes.spines.right':False})
audits=[]
def save(fig,stem):
    audits.append({'id':stem,'issues':[list(i) for i in audit_layout(fig)]})
    export_figure(fig,str(base/'figures'/stem),formats=['png','svg'],dpi=300,
                  size_inches=tuple(fig.get_size_inches()),tight=False,grayscale_preview=False)
    p=base/'figures'/(stem+'.svg');p.write_text('\n'.join(s.rstrip() for s in p.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')  # noqa: E702
    plt.close(fig)

top=sorted(rows,key=lambda r:r['normal_vocational_undergraduates'],reverse=True)[:12]
fig,ax=plt.subplots(figsize=(5.7,4.2));fig.subplots_adjust(left=.15,right=.95,bottom=.13,top=.86)  # noqa: E702
values=[r['normal_vocational_undergraduates']/10000 for r in top]
ax.barh([r['region'] for r in top],values,color=[purple if r['region']=='湖北' else sage for r in top],height=.65)
ax.invert_yaxis();ax.set(xlim=(0,max(values)*1.18),xlabel='普通、职业本专科在校生（万人）')  # noqa: E702
for i,v in enumerate(values):ax.text(v+2,i,f'{v:.2f}',va='center',fontsize=8.3)  # noqa: E701
fig.suptitle('2024年本专科在校生规模前12位省份',fontsize=11,fontweight='bold',y=.95)
save(fig,'fig10-regional-college')

order=['湖北','河南','安徽','江西','湖南','重庆','陕西'];index={r['region']:r for r in rows}  # noqa: E702
keys=['normal_vocational_undergraduates','regular_senior_students','junior_students']
fig,axes=plt.subplots(1,3,figsize=(5.7,3.6),sharey=True,sharex=True)
fig.subplots_adjust(left=.13,right=.97,bottom=.16,top=.78,wspace=.18)
maximum=max(index[r][k]/10000 for r in order for k in keys)*1.14
for ax,k,title,shade in zip(axes,keys,['普通、职业本专科','普通高中','初中'],[purple,apricot,sage]):  # noqa: B905
    values=[index[r][k]/10000 for r in order]
    ax.barh(order,values,color=shade,height=.62);ax.set_xlim(0,maximum);ax.set_title(title,fontsize=8.5,pad=10)  # noqa: E702
    ax.set_xlabel('万人',fontsize=8)
    for i,v in enumerate(values):ax.text(v+4,i,f'{v:.1f}',va='center',fontsize=8)  # noqa: E701
axes[0].invert_yaxis()
fig.suptitle('2024年湖北及周边六省市在校生规模',fontsize=11,fontweight='bold',y=.95)
save(fig,'fig11-hubei-neighbours')
(ROOT/'tmp/application-revision-20261027/regional-figure-audit.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'figures':2,'regions':len(rows),'auditIssues':sum(len(a['issues']) for a in audits)}))
