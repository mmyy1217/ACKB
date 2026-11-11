#!/usr/bin/env python3
"""Build a self-contained, offline CCE interface manual."""

import argparse
import json
from pathlib import Path

from catalog import ROOT, VERSION, validate


def build(source, output):
    data = json.loads(source.read_text())
    validate(data)
    page = (ROOT / 'web/index.html').read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    page = page.replace('/*__STYLE__*/', (ROOT / 'web/style.css').read_text())
    page = page.replace('/*__DATA__*/', payload)
    page = page.replace('/*__SCRIPT__*/', (ROOT / 'web/app.js').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page)
    print(f'Built {output} ({output.stat().st_size:,} bytes). Open directly in a browser.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'data' / VERSION / 'catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/index.html')
    args = parser.parse_args()
    build(args.data, args.output)
