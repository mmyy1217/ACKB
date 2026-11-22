#!/usr/bin/env python3
"""Build a self-contained, offline CCE interface manual."""

import argparse
import json
from pathlib import Path

from catalog import ROOT, VERSION, validate
from database import load_catalog
from knowledge import Knowledge
from insights import render as render_insights


def build(source, output, site=False):
    data = load_catalog(source)
    validate(data)
    page = (ROOT / 'web/index.html').read_text()
    page = page.replace('<!--__ASCENDC_MAP__-->', (ROOT / 'web/ascendc-map.html').read_text())
    page = page.replace('<!--__INSIGHTS__-->', render_insights())
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
    from llvm_ir import OUTPUT as LLVM_OUTPUT, validate_model as validate_llvm
    if LLVM_OUTPUT.exists():
        llvm = json.loads(LLVM_OUTPUT.read_text())
        errors = validate_llvm(llvm)
        if errors: raise ValueError('; '.join(errors))
        from llvm_ir import web_payload as llvm_web_payload
        knowledge['llvm'] = llvm_web_payload(llvm)
        from llvm_ir import dialect_navigation
        knowledge['llvm_navigation'] = dialect_navigation(llvm, knowledge.get('cce_dialect', {'intrinsics': []}))
    knowledge['nvvm'] = json.loads((ROOT / 'data/nvvm/index.json').read_text())
    knowledge['ptx']['forms'] = json.loads((ROOT / 'data/ptx/forms.json').read_text())
    scripts = '\n'.join((ROOT / 'web' / name).read_text() for name in [
        'loading.js', 'knowledge.js', 'ptx-reader.js', 'ccec-static.js', 'ccec-ops.js',
        'ccec-a5.js', 'ccec-calls.js', 'multi-backend.js', 'llvm-core.js', 'symbol-depth.js', 'app.js'])
    style = (ROOT / 'web/style.css').read_text()
    from site_build import inline_json, build_site
    if site:
        build_site(page, style, scripts, data, knowledge, output)
        return
    payload = inline_json(data)
    encoded = inline_json(knowledge)
    page = page.replace('/*__STYLE__*/', style).replace('/*__DATA__*/', payload)
    page = page.replace('/*__KNOWLEDGE__*/', encoded)
    page = page.replace('/*__SCRIPT__*/', scripts)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page)
    print(f'Built {output} ({output.stat().st_size:,} bytes). Open directly in a browser.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'data' / VERSION / 'catalog.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--site', action='store_true', help='Build a lazy-loading website instead of the offline HTML')
    args = parser.parse_args()
    build(args.data, args.output or ROOT / ('dist/site/index.html' if args.site else 'dist/index.html'), args.site)
