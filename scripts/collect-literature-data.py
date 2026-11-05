"""Download open research articles/supplements and preserve table-level provenance."""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from lxml import html as lhtml

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "tmp/literature-data-20261028"
RAW = WORK / "raw"
PAPERS = [
    ("ZHOU2024", "10.1186/s13034-024-00841-w", "https://link.springer.com/article/10.1186/s13034-024-00841-w"),
    ("CHEN2023", "10.1186/s12888-023-05068-1", "https://link.springer.com/article/10.1186/s12888-023-05068-1"),
    ("CHEN2021", "10.1038/s41398-021-01271-4", "https://www.nature.com/articles/s41398-021-01271-4"),
    ("FENG2025", "10.2196/69639", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12120367/fullTextXML"),
    ("FITZ2017", "10.2196/mental.7785", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5478797/fullTextXML"),
    ("YANG2023", "10.1186/s12888-023-04972-w", "https://link.springer.com/article/10.1186/s12888-023-04972-w"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AcademicTableReader/1.0; open-access-research)"}
CACHE = {}
if (WORK / 'download-manifest.json').exists():
    for paper in json.loads((WORK / 'download-manifest.json').read_text(encoding='utf-8'))['papers']:
        for record in paper['downloads']:
            if record.get('status') == 200 and record.get('bytes', 0) > 0:
                CACHE[record['url']] = record


def fetch(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    cached=CACHE.get(url)
    if cached and (WORK/cached['path']).is_file() and hashlib.sha256((WORK/cached['path']).read_bytes()).hexdigest()==cached['sha256']:
        return cached
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=40) as response:
                content=response.read()
                destination.write_bytes(content)
                return {"url": url, "resolved_url": response.url, "path": str(destination.relative_to(WORK)).replace('\\', '/'),
                        "status": response.status, "bytes": len(content), "content_type": response.headers.get("content-type", ""),
                        "sha256": hashlib.sha256(content).hexdigest(), "downloaded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            if attempt:
                return {"url": url, "status": getattr(exc, 'code', 'failed'), "error": type(exc).__name__}
        time.sleep(0.6)


def flat_tables(html):
    soup = lhtml.fromstring(html.encode('utf-8') if isinstance(html, str) else html, parser=lhtml.HTMLParser(encoding='utf-8'))
    output = []
    for i, table in enumerate(soup.xpath('//table'), 1):
        captions = table.xpath('./caption | ../figcaption | ../h3 | ../h4')
        caption = ' '.join(captions[0].itertext()).strip() if captions else ''
        cells = [[re.sub(r"\s+", " ", ' '.join(c.itertext())).strip() for c in row.xpath('./td | ./th')] for row in table.xpath('.//tr')]
        if cells:
            output.append({"table_index": i, "id": table.get("id", ""), "caption": caption, "cells": cells})
    return output


def collect(paper):
    sid, doi, url = paper
    article = fetch(url, RAW / f"{sid}-article.{'xml' if 'fullTextXML' in url else 'html'}")
    result = {"source_id": sid, "doi": doi, "url": url, "downloads": [article], "tables": []}
    if article["status"] != 200:
        return result
    html = (WORK / article["path"]).read_text(encoding="utf-8", errors="replace")
    soup = lhtml.fromstring(html.encode('utf-8'), parser=lhtml.HTMLParser(encoding='utf-8'))
    titles = soup.xpath('//meta[@name="citation_title"]/@content | //title/text() | //article-title/text()')
    result["title"] = titles[0] if titles else ''
    result["license_links"] = sorted({urljoin(url, a.get('href')) for a in soup.xpath('//a[@href]') if "creativecommons.org/licenses/" in a.get('href')})
    result['license_links'] += soup.xpath('//*[local-name()="license"]/@*[local-name()="href"]')
    (RAW / f"{sid}-article.txt").write_text('\n'.join(soup.itertext()), encoding="utf-8")
    result["tables"] = flat_tables(html)
    links = []
    for a in soup.xpath('//a[@href]'):
        link = urljoin(url, a.get('href'))
        if any(term in link for term in ["MOESM", "/api/download?alt_name="]):
            if re.search(r"\.(?:pdf|docx?|xlsx?|csv|zip)(?:\?|$)", link, re.I) or "/api/download?alt_name=" in link:
                if link not in links:
                    links.append(link)
    for i, link in enumerate(links, 1):
        name = Path(urlsplit(link).path).name
        if not re.search(r"\.(pdf|docx?|xlsx?|csv|zip)$", name, re.I):
            name = f"supplement-{i}.bin"
        result["downloads"].append(fetch(link, RAW / f"{sid}-{name}"))
    if sid == 'FENG2025':
        result['downloads'].append(fetch('https://www.jmir.org/api/download?alt_name=jmir_v27i1e69639_app2.docx&filename=f74065e460e54bcd1cc432ac404b58bf.docx', RAW/'FENG2025-app2.docx'))
    # Springer full-size table pages contain the source cells when article HTML omits them.
    for a in soup.xpath('//a[@href]'):
        link = urljoin(url, a.get('href'))
        if re.search(r"/tables/\d+$", link) and not any(d["url"] == link for d in result["downloads"]):
            rec = fetch(link, RAW / f"{sid}-table-{link.rsplit('/',1)[-1]}.html")
            result["downloads"].append(rec)
            if rec["status"] == 200:
                result["tables"].extend([{**t, "table_url": link} for t in flat_tables((WORK / rec["path"]).read_text(encoding="utf-8", errors="replace"))])
    return result


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        papers = list(executor.map(collect, PAPERS))
    figshare = fetch("https://api.figshare.com/v2/articles/26600857", RAW / "YANG2024-figshare.json")
    if figshare["status"] == 200:
        meta = json.loads((WORK / figshare["path"]).read_text(encoding="utf-8"))
        item = {"source_id": "YANG2023SUPP", "title": meta["title"], "doi": meta.get("doi"), "article_doi": "10.1186/s12888-023-04972-w", "article_year": 2023, "repository_deposit_year": 2024, "url": meta.get("url_public_html"), "license": meta.get("license"), "downloads": [figshare], "tables": []}
        for f in meta.get("files", []):
            item["downloads"].append(fetch(f["download_url"], RAW / f"YANG2024-{f['name']}"))
        papers.append(item)
    else:
        papers.append({"source_id": "YANG2024", "downloads": [figshare]})
    out = {"owner": "A Lead", "updated": "2026-10-28", "method": "targeted SciSpace discovery and primary-source download; not a systematic review", "papers": papers}
    (WORK / "download-manifest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{ "id": p["source_id"], "title": p.get("title"), "tables": len(p.get("tables", [])), "downloads": [{k:d.get(k) for k in ['path','status','bytes']} for d in p["downloads"]], "licenses": p.get("license_links", p.get("license"))} for p in papers], ensure_ascii=False))


if __name__ == "__main__":
    main()
