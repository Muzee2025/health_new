"""Rasterize a private Word PDF export for per-page visual review."""
import argparse
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image, ImageOps, ImageDraw

p = argparse.ArgumentParser()
p.add_argument('pdf')
p.add_argument('out')
args = p.parse_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
pdf = pdfium.PdfDocument(args.pdf)
thumbs = []
for i, page in enumerate(pdf):
    im = page.render(scale=1.5).to_pil().convert('RGB')
    im.save(out / f'page-{i+1}.png')
    thumb = ImageOps.contain(im, (298, 422))
    tile = Image.new('RGB', (318, 452), 'white')
    tile.paste(thumb, ((318-thumb.width)//2, 6))
    ImageDraw.Draw(tile).text((12, 432), str(i+1), fill='black')
    thumbs.append(tile)
for start in range(0, len(thumbs), 9):
    canvas = Image.new('RGB', (318*3, 452*3), '#dddddd')
    for j, tile in enumerate(thumbs[start:start+9]):
        canvas.paste(tile, ((j%3)*318, (j//3)*452))
    canvas.save(out / f'contact-{start//9+1}.png')
print(f'pages={len(pdf)} output={out.resolve()}')
