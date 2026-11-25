#!/usr/bin/env python3
"""Build a self-contained, offline CCE interface manual."""

import argparse
import base64
import hashlib
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
    insights = render_insights()
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
            dialect = dialect_web_payload(dialect_data)
            audit = json.loads(DIALECT_OUTPUT.with_name('translation-audit.json').read_text())
            if audit['dialect_commit'] != dialect['source']['commit']:
                raise ValueError('Dialect translation audit source mismatch')
            dialect['intrinsics'] = [item for item in dialect['intrinsics'] if item['path_status'] == 'confirmed']
            visible_ids = {item['id'] for item in dialect['intrinsics']}
            for op in dialect['ops']:
                op['intrinsic_ids'] = [identity for identity in op['intrinsic_ids'] if identity in visible_ids]
            dialect['counts']['intrinsics'] = len(visible_ids)
            dialect['translation_audit'] = {case['name']: case for case in audit['cases'] if case['status'] == 'confirmed'}
            knowledge['cce_dialect'] = dialect
    from llvm_ir import OUTPUT as LLVM_OUTPUT, validate_model as validate_llvm
    if LLVM_OUTPUT.exists():
        llvm = json.loads(LLVM_OUTPUT.read_text())
        errors = validate_llvm(llvm)
        if errors: raise ValueError('; '.join(errors))
        from llvm_ir import web_payload as llvm_web_payload
        knowledge['llvm'] = llvm_web_payload(llvm)
        if 'cce_dialect' in knowledge:
            from dialect_correspondence import add_correspondence
            evidence = json.loads(DIALECT_OUTPUT.with_name('cann-correspondence.json').read_text())
            add_correspondence(knowledge['cce_dialect'], llvm, evidence)
        from llvm_ir import dialect_navigation
        knowledge['llvm_navigation'] = dialect_navigation(llvm, knowledge.get('cce_dialect', {'intrinsics': []}))
    knowledge['hivm-defs'] = json.loads((ROOT / 'data/hivm_defs/index.json').read_text())
    knowledge['nvvm'] = json.loads((ROOT / 'data/nvvm/index.json').read_text())
    knowledge['ptx']['forms'] = json.loads((ROOT / 'data/ptx/forms.json').read_text())
    scripts = '\n'.join((ROOT / 'web' / name).read_text() for name in [
        'loading.js', 'knowledge.js', 'ptx-reader.js', 'ccec-static.js', 'ccec-ops.js',
        'ccec-a5.js', 'ccec-calls.js', 'multi-backend.js', 'llvm-core.js', 'symbol-depth.js', 'hivm-defs.js', 'gap-insight.js', 'app.js'])
    style = (ROOT / 'web/style.css').read_text()
    from site_build import inline_json, build_site
    for asset in sorted((ROOT / 'web/insights/files').glob('a5-gap-*.*')):
        date = asset.stem.removeprefix('a5-gap-')
        extension = asset.suffix[1:]
        mime = {'json': 'application/json', 'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}[extension]
        content = asset.read_bytes()
        if site:
            relative = Path('insights') / asset.name
            destination = output.parent / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            url = f'{relative}?v={hashlib.sha256(content).hexdigest()[:16]}'
        else:
            url = 'data:' + mime + ';base64,' + base64.b64encode(content).decode('ascii')
        insights = insights.replace(f'__GAP_{date}_{extension.upper()}__', url)
    if site:
        page = page.replace('<!--__INSIGHTS__-->', '<template id="insights-slot"></template>')
        scripts = ("'use strict';\nconst insightsSlot = document.getElementById('insights-slot');\n"
                   + "insightsSlot.insertAdjacentHTML('beforebegin'," + inline_json(insights) + ");\n"
                   + "insightsSlot.remove();\n" + scripts)
        build_site(page, style, scripts, data, knowledge, output)
        return
    page = page.replace('<!--__INSIGHTS__-->', insights)
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
