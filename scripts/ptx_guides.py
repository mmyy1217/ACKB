#!/usr/bin/env python3
"""Validate and emit comprehensive Chinese guides for all 221 PTX instructions."""

import argparse
import json
from pathlib import Path

from catalog import ROOT
from ptx_guides_data_a import GUIDES_A
from ptx_guides_data_b import GUIDES_B


def build_guides(data_dir=ROOT / 'data/ptx'):
    instructions = json.loads((data_dir / 'instructions.json').read_text())
    expected_anchors = {inst['anchor'] for inst in instructions}

    overlap = set(GUIDES_A) & set(GUIDES_B)
    if overlap:
        raise ValueError(f'Duplicate anchors across guide modules: {sorted(overlap)}')

    merged = {**GUIDES_A, **GUIDES_B}
    missing = expected_anchors - set(merged)
    extra = set(merged) - expected_anchors
    if missing:
        raise ValueError(f'Missing guides for {len(missing)} anchors: {sorted(missing)[:10]}')
    if extra:
        raise ValueError(f'Unknown guide anchors: {sorted(extra)[:10]}')

    out = {}
    for inst in instructions:
        anchor = inst['anchor']
        raw = merged[anchor]
        for field in ('summary', 'mechanism', 'example', 'operands', 'result', 'pitfall'):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise ValueError(f'Missing or empty field {field} for {anchor}')
        related = raw.get('related', [])
        bad_related = [r for r in related if r not in expected_anchors]
        if bad_related:
            raise ValueError(f'Invalid related anchor(s) for {anchor}: {bad_related}')
        out[anchor] = {
            'anchor': anchor,
            'summary': raw['summary'],
            'mechanism': raw['mechanism'],
            'qualifiers': raw.get('qualifiers', []),
            'example': raw['example'],
            'operands': raw['operands'],
            'result': raw['result'],
            'pitfall': raw['pitfall'],
            'related': related,
            'scope': 'representative_form_with_qualifiers',
            'verification': 'unverified',
        }
    return {'schema_version': 'ackb.ptx-guides.v1', 'entries': out}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/ptx')
    args = parser.parse_args()
    data = build_guides(args.data_dir)
    out = args.data_dir / 'guides.json'
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {out} ({len(data["entries"])} instruction guides)')


if __name__ == '__main__':
    main()
