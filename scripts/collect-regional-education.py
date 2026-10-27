"""Extract comparable 2024 provincial education counts from saved MOE source pages."""
import argparse,csv,hashlib,json,re
from pathlib import Path
from lxml import html

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/plan/ai-application/revision-20261027'
REGIONS='北京 天津 河北 山西 内蒙古 辽宁 吉林 黑龙江 上海 江苏 浙江 安徽 福建 江西 山东 河南 湖北 湖南 广东 广西 海南 重庆 四川 贵州 云南 西藏 陕西 甘肃 青海 宁夏 新疆'.split()
SOURCES={
 'bachelor':('高等教育普通本科学生数','t20260317_1431199.html',4,8),
 'vocational':('高等教育职业本专科学生数','t20260317_1431198.html',8,16),
 'schools':('高等教育学校（机构）数','t20260317_1431201.html',0,7),
 'senior':('普通高中教育学生数','t20260319_1431390.html',2,7),
 'junior':('初中教育学生数','t20260319_1431404.html',2,9),
}

def extract(folder):
    tables={};sources={}
    for key,(title,filename,index,width) in SOURCES.items():
        file=folder/(key+'.html');tree=html.fromstring(file.read_bytes());rows={}
        for tr in tree.xpath('//tr'):
            cells=tr.xpath('./td|./th')
            if len(cells)<2:continue
            name=''.join(re.findall(r'[\u4e00-\u9fff]',cells[0].text_content()))
            if name not in REGIONS+['总计']:continue
            nums=[re.sub(r'\s|,','',c.text_content()) for c in cells[1:]]
            assert len(nums)==width and all(n.isdigit() for n in nums),(key,name,len(nums))
            assert name not in rows,(key,name)
            rows[name]=[int(n) for n in nums]
        assert set(rows)==set(REGIONS+['总计']),(key,len(rows))
        assert sum(rows[r][index] for r in REGIONS)==rows['总计'][index],key
        tables[key]=rows
        sources[key]={'title':title,'year':2024,'unit':'所' if key=='schools' else '人',
          'url':'https://www.moe.gov.cn/jyb_sjzl/moe_560/2024/gedi/202603/'+filename,
          'downloadUrl':'https://hudong.moe.gov.cn/jyb_sjzl/moe_560/2024/gedi/202603/'+filename,
          'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'valueColumnIndex':index,
          'nationalTotal':rows['总计'][index],'regions':31}
    data=[]
    for region in REGIONS:
        b=tables['bachelor'][region];v=tables['vocational'][region];s=tables['schools'][region]
        j=tables['junior'][region];h=tables['senior'][region]
        assert v[8]==v[10]+v[11] and s[0]==sum(s[2:5])
        assert h[2]==sum(h[4:7]) and j[2]==sum(j[4:8])
        data.append({'region':region,'year':2024,'regular_vocational_heis':s[0],
          'academic_bachelor_students':b[4],'vocational_normal_short_students':v[8],
          'normal_vocational_undergraduates':b[4]+v[8],
          'regular_senior_students':h[2],'junior_students':j[2]})
    DEST.mkdir(parents=True,exist_ok=True)
    with (DEST/'regional-education-2024.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    result={'year':2024,'regions':31,'sources':sources,'records':data,
      'definitions':{'normal_vocational_undergraduates':'普通本科在校生＋职业本专科在校生，不含研究生、成人与网络本专科',
       'regular_vocational_heis':'普通、职业高校，不含成人高等学校',
       'scope':'31省份，不含港澳台；各学段按教育部表口径。数值是教育规模，非心理问题检出率。'}}
    (DEST/'regional-education-2024.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'regions':len(data),'national':{k:v['nationalTotal'] for k,v in sources.items()},'hubei':next(r for r in data if r['region']=='湖北')},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sources',type=Path,required=True);a=p.parse_args();extract(a.sources)
