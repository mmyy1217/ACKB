"""Render curated, versioned articles without database dependencies."""
import json
import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render():
    directory = ROOT / 'web/insights'
    entries = json.loads((directory / 'index.json').read_text())
    seen = set()
    rows, articles = [], []
    for entry in entries:
        slug = entry['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in seen:
            raise ValueError(f'Invalid or duplicate insight slug: {slug}')
        seen.add(slug)
        title, date, summary = (escape(entry[key]) for key in ('title', 'date', 'summary'))
        body = (directory / f'{slug}.html').read_text()
        rows.append(f'<li><time datetime="{date}">{date}</time><div><a href="#insight={slug}">{title}</a><p>{summary}</p></div></li>')
        articles.append(f'<article data-insight="{slug}" hidden><a class="insight-back" href="#insights">返回洞察</a><header><h1>{title}</h1><time datetime="{date}">{date}</time></header>{body}</article>')
    return ('<main id="insights" hidden aria-label="洞察"><div id="insights-content" tabindex="-1">'
            '<section id="insights-index"><h1>洞察</h1><p class="insights-intro">关于编程体系、编译层级与目标能力的研究笔记。</p><ul class="insights-list">'
            + ''.join(rows) + '</ul></section>' + ''.join(articles)
            + '<section id="insight-missing" hidden><h1>未找到这篇文章</h1><a href="#insights">返回洞察目录</a></section></div></main>')
