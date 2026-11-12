"""Create a self-contained, plain HTML review copy of the application body."""
import argparse, base64, html, re  # noqa: E401, I001
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prefer-svg',action='store_true',help='Embed vector artwork when available')
args=parser.parse_args()
source=ROOT/'docs/plan/心域智链申报计划书.md'
lines=source.read_text(encoding='utf-8').splitlines()

def inline(s):
    parts=[];end=0  # noqa: E702
    for m in re.finditer(r'\[([^\]]+)\]\((https://[^)]+)\)|(https://[^\s<>，。；）]+)',s):
        parts.append(html.escape(s[end:m.start()]));url=m[2] or m[3];label=m[1] or url  # noqa: E702
        parts.append(f'<a href="{html.escape(url)}">{html.escape(label)}</a>');end=m.end()  # noqa: E702
    return ''.join(parts)+html.escape(s[end:])

blocks=[];toc=[];i=0  # noqa: E702
while i<len(lines):
    line=lines[i].strip();i+=1  # noqa: E702
    if not line or line.startswith('>'):continue  # noqa: E701
    if line.startswith('#'):
        level=len(line)-len(line.lstrip('#'));text=line[level:].strip()  # noqa: E702
        anchor=f'section-{len(toc)}' if level==2 else ''
        if level==2:toc.append((anchor,text))  # noqa: E701
        blocks.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>');continue  # noqa: E702
    if line.startswith('|'):
        rows=[line]
        while i<len(lines) and lines[i].strip().startswith('|'):rows.append(lines[i].strip());i+=1  # noqa: E701, E702
        cells=[[c.strip() for c in row.strip('|').split('|')] for row in rows]
        cells=[r for r in cells if not all(re.fullmatch(r':?-{3,}:?',v) for v in r)]
        header='<tr>'+''.join(f'<th scope="col">{inline(v)}</th>' for v in cells[0])+'</tr>'
        body=''.join('<tr>'+''.join(f'<td>{inline(v)}</td>' for v in r)+'</tr>' for r in cells[1:])
        blocks.append(f'<div class="table-wrap"><table><thead>{header}</thead><tbody>{body}</tbody></table></div>');continue  # noqa: E702
    image=re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)',line)
    if image:
        file=(source.parent/image[2]).resolve();file.relative_to(ROOT)  # noqa: E702
        if args.prefer_svg and file.with_suffix('.svg').exists():file=file.with_suffix('.svg')  # noqa: E701
        data=base64.b64encode(file.read_bytes()).decode()
        mime='image/svg+xml' if file.suffix=='.svg' else 'image/png'
        blocks.append(f'<img src="data:{mime};base64,{data}" alt="{html.escape(image[1])}">');continue  # noqa: E702
    if line.startswith('$$') and line.endswith('$$'):
        blocks.append(f'<p class="equation">{inline(line[2:-2])}</p>');continue  # noqa: E702
    cls='caption' if re.match(r'^[图表]\d+\s',line) else 'source' if line.startswith(('来源：','项目方案示意')) else ''
    blocks.append(f'<p class="{cls}">{inline(line)}</p>')

nav=' · '.join(f'<a href="#{a}">{html.escape(t)}</a>' for a,t in toc)
css='''
*{box-sizing:border-box}body{margin:0;background:#fff;color:#29332F;font-family:"Microsoft YaHei","PingFang SC",sans-serif}
main{max-width:960px;padding:46px 40px 64px;margin:auto}h1{font-size:28px;line-height:1.6;text-align:center;margin:14px 0 30px;font-weight:600}
h2{font-size:23px;font-weight:600;margin:45px 0 22px;text-align:center;scroll-margin-top:20px}h3{font-size:18px;font-weight:600;margin:30px 0 14px}
p{font-size:16px;line-height:1.95;margin:13px 0;overflow-wrap:anywhere}nav{font-size:14px;text-align:center;line-height:2.2;margin:0 0 38px;color:#56625C}
a{color:inherit;text-underline-offset:3px;overflow-wrap:anywhere}img{display:block;max-width:100%;height:auto;margin:20px auto 10px}
.caption{text-align:center;font-size:14px;margin:20px 0 12px}.source{font-size:13px;color:#56625C;line-height:1.8;margin-bottom:28px}
.equation{text-align:center;font-family:"Cambria Math","Times New Roman",serif;line-height:1.7;margin:20px 0}
.table-wrap{overflow-x:auto;margin:16px 0 26px}table{border-collapse:collapse;width:100%;border-top:2px solid #29332F;border-bottom:2px solid #29332F;font-size:14px;line-height:1.7}
thead{border-bottom:1px solid #29332F}th,td{padding:13px 12px;text-align:center;vertical-align:middle;border:0}th{font-weight:600}
.review{font-size:13px;color:#56625C;text-align:center;margin:0 0 18px}
@media(max-width:640px){main{padding:28px 18px}h1{font-size:23px}h2{font-size:21px}p{font-size:15px}table{min-width:620px}}
@media print{@page{size:A4;margin:20mm}main{padding:0;max-width:none}nav,.review{display:none}h2,h3,.caption{break-after:avoid}img,table,tr{break-inside:avoid}}
'''
tokens=(ROOT/'src/styles/tokens.css').read_text(encoding='utf-8')
css=css.replace('#29332F','var(--text-primary)').replace('#56625C','var(--text-secondary)')
css=css.replace('background:#fff','background:var(--surface)').replace('font-family:"Microsoft YaHei","PingFang SC",sans-serif','font-family:var(--font-sans)')
out='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><title>心域智链申报书正文审阅版</title><style>'+tokens+css+'</style></head><body><main><p class="review">正文与图表审阅版 · 图示样式待确认 · 申报登记表和签章栏见Word附件</p><nav aria-label="章节目录">'+nav+'</nav>'+''.join(blocks)+'</main></body></html>'
target=ROOT/'deliverables/心域智链申报书正文审阅版.html'
target.write_text(out,encoding='utf-8')
print(f'Created self-contained review HTML: {target.name}; {len(out)} characters')
