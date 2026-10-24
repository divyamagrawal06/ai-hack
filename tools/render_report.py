#!/usr/bin/env python3
"""Render the submission's Markdown subset to self-contained HTML and PDF.

HTML rendering uses only stdlib; PDF requires Playwright plus Chromium.
"""
import argparse
import base64
import html
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def inline(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)


def markdown(text):
    lines = text.splitlines()
    output, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1; continue
        if line.startswith('#'):
            level = len(line)-len(line.lstrip('#'))
            output.append(f'<h{level}>{inline(line[level:].strip())}</h{level}>'); i += 1
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                row = [cell.strip() for cell in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in row):
                    rows.append(row)
                i += 1
            output.append('<table><thead><tr>' + ''.join('<th>'+inline(cell)+'</th>' for cell in rows[0]) + '</tr></thead><tbody>')
            for row in rows[1:]:
                output.append('<tr>'+''.join('<td>'+inline(cell)+'</td>' for cell in row)+'</tr>')
            output.append('</tbody></table>')
        elif line.startswith('```'):
            block=[]; i+=1
            while i<len(lines) and not lines[i].startswith('```'):
                block.append(lines[i]); i+=1
            output.append('<pre><code>'+html.escape('\n'.join(block))+'</code></pre>'); i+=1
        elif re.match(r'^\d+\. ',line) or line.startswith('- '):
            ordered = bool(re.match(r'^\d+\. ',line)); tag='ol' if ordered else 'ul'
            output.append('<'+tag+'>')
            while i<len(lines) and (bool(re.match(r'^\d+\. ',lines[i])) if ordered else lines[i].startswith('- ')):
                value=re.sub(r'^\d+\. ' if ordered else r'^- ', '', lines[i])
                output.append('<li>'+inline(value)+'</li>'); i+=1
            output.append('</'+tag+'>')
        else:
            para=[line]; i+=1
            while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','```','- ')):
                para.append(lines[i]); i+=1
            output.append('<p>'+inline(' '.join(para))+'</p>')
    return '\n'.join(output)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--html-only',action='store_true'); args=parser.parse_args()
    report=ROOT/'reports/submission-report.md'
    body=markdown(report.read_text())
    figures=[]
    for name,caption in [('intake-desktop','Implemented desktop intake form'),('staff-workspace','Implemented staff review, booking and audit'),('intake-mobile','Implemented mobile intake form')]:
        path=ROOT/f'reports/screenshots/{name}.png'
        if path.exists():
            data=base64.b64encode(path.read_bytes()).decode()
            figures.append(f'<section class="figure"><h2>{caption}</h2><p>Actual screenshot of the synthetic prototype; no patient records.</p><img alt="{caption}" src="data:image/png;base64,{data}"></section>')
    document='''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>CareRoute submission report</title><style>
    @page { size:A4; margin:18mm 15mm 19mm; }
    body{font:10.5pt/1.48 Arial,sans-serif;color:#183438;max-width:1000px;margin:32px auto;padding:0 20px}
    h1{font-size:27pt;line-height:1.12;color:#126f6b;border-bottom:5px solid #126f6b;padding-bottom:20px}
    h2{font-size:15pt;margin-top:25px;color:#126f6b;break-after:avoid}h3{break-after:avoid}
    p,li{orphans:3;widows:3}a{color:#126f6b}table{width:100%;border-collapse:collapse;font-size:9pt;margin:16px 0}
    th,td{border:1px solid #cbdad8;padding:8px;text-align:left;vertical-align:top}th{background:#e5f0ed}tr{break-inside:avoid}
    code{font:9pt monospace;background:#edf4f2;padding:1px 3px}pre{white-space:pre-wrap}
    .figure{break-before:page}.figure img{display:block;max-width:100%;max-height:230mm;object-fit:contain;margin:12px auto}
    @media print{body{margin:0;padding:0;max-width:none}a{text-decoration:none}}
    </style></head><body>'''+body+''.join(figures)+'</body></html>'
    output=ROOT/'reports/submission-report.html'; output.write_text(document)
    if not args.html_only:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            launch={'headless':True,'args':['--no-sandbox']}
            executable=shutil.which('chromium') or shutil.which('chromium-browser')
            if executable: launch['executable_path']=executable
            browser=p.chromium.launch(**launch); page=browser.new_page()
            page.set_content(document, wait_until='load')
            page.pdf(path=str(ROOT/'reports/submission-report.pdf'),print_background=True,prefer_css_page_size=True,
                     display_header_footer=True,header_template='<span></span>',
                     footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#607370">CareRoute · synthetic demonstration · <span class="pageNumber"></span> / <span class="totalPages"></span></div>')
            browser.close()
    print('Rendered submission-report.html'+(' and submission-report.pdf' if not args.html_only else ''))


if __name__=='__main__': main()
