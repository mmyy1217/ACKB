#!/usr/bin/env python3
"""Extract functional syntax and build original, source-linked PTX learning data."""
import argparse
import hashlib
import json
from pathlib import Path
from catalog import ROOT
from ptx_index import PINNED, SOURCE_DIR, parse_manual, require_pin


def build(html, output):
    require_pin(html, PINNED['html'])
    syntax = {}
    for section in parse_manual(html.read_text()):
        blocks = [r for r in section['rubrics'] if r['name'] in ('Syntax', 'Syntax (predefined)')]
        text = '\n'.join(p for b in blocks for p in b['pre'])
        if text.strip():
            syntax[section['id']] = {'text': text, 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                                     'representation': 'official_instruction_syntax', 'source_anchor': section['id']}
    data = {'schema_version': 'ackb.ptx-syntax.v1', 'source_sha256': PINNED['html']['sha256'], 'entries': syntax}
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'Extracted {len(syntax)} syntax blocks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--html', type=Path, default=SOURCE_DIR / PINNED['html']['name'])
    parser.add_argument('--output', type=Path, default=ROOT / 'data/ptx/syntax.json')
    args = parser.parse_args()
    build(args.html, args.output)
