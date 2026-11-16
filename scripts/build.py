#!/usr/bin/env python3
"""Build a self-contained, offline CCE interface manual."""

import argparse
import json
from pathlib import Path

from catalog import ROOT, VERSION, validate
from database import load_catalog
from knowledge import Knowledge


def build(source, output):
    data = load_catalog(source)
    validate(data)
    page = (ROOT / 'web/index.html').read_text()
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    page = page.replace('/*__STYLE__*/', (ROOT / 'web/style.css').read_text())
    page = page.replace('/*__DATA__*/', payload)
    ptx = Knowledge('ptx')
    ccec = Knowledge('ccec')
    knowledge = {'ptx': {'records': ptx.records, 'notes': ptx.notes, 'source': ptx.tree['source'], 'scan': ptx.tree['scan'], 'learning': ptx.learning, 'taxonomy': ptx.taxonomy},
                 'ccec': ccec.tree if source.resolve() == (ROOT / 'data' / VERSION / 'catalog.json').resolve() else {'topics': []}}
    from ccec_ops import build_model, validate as validate_ops
    from database import Database
    op_db = Database(source)
    ops = build_model(op_db)
    validate_ops(ops, op_db)
    knowledge['ccec']['ops'] = ops
    from ccec_calls import load_calls
    knowledge['ccec']['call_evidence'] = load_calls(op_db)
    if source.resolve() == (ROOT / 'data' / VERSION / 'catalog.json').resolve():
        from ccec_support import Support
        from ccec_static import OUTPUT, validate as validate_static, web_payload
        support = Support()
        static = json.loads(OUTPUT.read_text())
        errors = validate_static(static, support)
        if errors:
            raise ValueError('; '.join(errors))
        knowledge['ccec']['static_support'] = web_payload(static, support)
        from ascendc import OUTPUT as ASC_OUTPUT, validate_model as validate_ascendc, web_payload as ascendc_web_payload
        from cce_dialect import OUTPUT as DIALECT_OUTPUT, validate_model as validate_dialect, web_payload as dialect_web_payload
        if ASC_OUTPUT.exists():
            asc_data = json.loads(ASC_OUTPUT.read_text())
            asc_errors = validate_ascendc(asc_data)
            if asc_errors:
                raise ValueError('; '.join(asc_errors))
            knowledge['ascendc'] = ascendc_web_payload(asc_data)
        if DIALECT_OUTPUT.exists():
            dialect_data = json.loads(DIALECT_OUTPUT.read_text())
            dialect_errors = validate_dialect(dialect_data)
            if dialect_errors:
                raise ValueError('; '.join(dialect_errors))
            knowledge['cce_dialect'] = dialect_web_payload(dialect_data)
    encoded = json.dumps(knowledge, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    page = page.replace('/*__KNOWLEDGE__*/', encoded)
    page = page.replace('/*__SCRIPT__*/', (ROOT / 'web/knowledge.js').read_text() + '\n' + (ROOT / 'web/ptx-reader.js').read_text() + '\n' + (ROOT / 'web/ccec-static.js').read_text() + '\n' + (ROOT / 'web/ccec-ops.js').read_text() + '\n' + (ROOT / 'web/ccec-a5.js').read_text() + '\n' + (ROOT / 'web/ccec-calls.js').read_text() + '\n' + (ROOT / 'web/multi-backend.js').read_text() + '\n' + (ROOT / 'web/app.js').read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page)
    print(f'Built {output} ({output.stat().st_size:,} bytes). Open directly in a browser.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'data' / VERSION / 'catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'dist/index.html')
    args = parser.parse_args()
    build(args.data, args.output)
