"""Package the same lossless snapshots for incremental, content-addressed loading."""

import gzip
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'ackb.site.v1'


def inline_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()


def asset(directory, name, content, extension):
    digest = hashlib.sha256(content).hexdigest()
    relative = f'assets/{name}.{digest}.{extension}'
    (directory / relative).write_bytes(content)
    return {'url': relative, 'sha256': digest, 'bytes': len(content)}


def pack_dataset(directory, name, payload):
    raw = json_bytes({'schema': SCHEMA, 'dataset': name, 'payload': payload})
    return {'gzip': asset(directory, name, gzip.compress(raw, mtime=0), 'json.gz'),
            'plain': asset(directory, name, raw, 'json')}


def navigation_data(data, knowledge):
    # Routing labels are not records: no declaration or support facts are inferred.
    rows = [[r['id'], r['name'], 'ccec'] for r in data['records']]
    rows += [[o['id'], o['builtin'], 'ccec'] for o in knowledge['ccec']['ops']['ops']]
    for key in ['basic_api', 'c_api']:
        rows += [[r['id'], r['name'], 'ascendc'] for r in knowledge.get('ascendc', {}).get(key, [])]
    for key in ['ops', 'intrinsics']:
        rows += [[r['id'], r['name'], 'cce-dialect'] for r in knowledge.get('cce_dialect', {}).get(key, [])]
    llvm = knowledge.get('llvm', {})
    ops = llvm.get('ops', [])
    if isinstance(ops, dict):
        ops = [dict(zip(ops['columns'], row)) for row in ops['rows']]
    rows += [[o['id'], o['name'], 'llvm'] for o in ops]
    return {'labels': sorted(rows), 'llvm_relations': llvm.get('relations', [])}


def build_site(page, style, scripts, data, knowledge, output):
    output = Path(output)
    directory = output.parent
    (directory / 'assets').mkdir(parents=True, exist_ok=True)
    datasets = {'ccec': {'catalog': data, 'knowledge': knowledge['ccec']},
                'navigation': navigation_data(data, knowledge)}
    for name, key in [('ptx', 'ptx'), ('ascendc', 'ascendc'), ('cce-dialect', 'cce_dialect'), ('llvm', 'llvm'), ('nvvm', 'nvvm')]:
        datasets[name] = knowledge.get(key, {})
    manifest = {'schema': SCHEMA, 'datasets': {name: pack_dataset(directory, name, value) for name, value in datasets.items()}}
    css = asset(directory, 'style', style.encode(), 'css')
    js = asset(directory, 'app', scripts.encode(), 'js')
    manifest['style'], manifest['script'] = css, js
    empty_knowledge = {'ptx': {'records': [], 'notes': [], 'learning': {'chapters': []}}, 'ccec': {'topics': []}}
    empty_catalog = {'version': data['version'], 'records': [], 'files': [], 'compatibility': {'profiles': []}}
    page = page.replace('<style>/*__STYLE__*/</style>', f'<link rel="stylesheet" href="{css["url"]}">')
    page = page.replace('/*__DATA__*/', inline_json(empty_catalog)).replace('/*__KNOWLEDGE__*/', inline_json(empty_knowledge))
    recovery = '<script>function refreshSite(){const url=new URL(location.href);url.searchParams.set("updated",Date.now());location.replace(url.href);}</script>'
    failure = "document.querySelector('#site-update').hidden=false"
    page = page.replace('<script>/*__SCRIPT__*/</script>', f'{recovery}\n<script id="asset-manifest" type="application/json">/*__MANIFEST__*/</script>\n<script defer src="{js["url"]}" onerror="{failure}"></script>')
    # The homepage is real HTML and can paint before JavaScript or any database.
    page = page.replace('<body>', '<body class="home-mode">').replace('<main id="home" hidden', '<main id="home"')
    page = page.replace('页面可离线使用。', '在线版按需加载；离线分享请使用单文件 HTML。')
    manifest['shell_sha256'] = hashlib.sha256(page.encode()).hexdigest()
    manifest['revision'] = hashlib.sha256(json_bytes(manifest)).hexdigest()
    manifest_text = inline_json(manifest)
    (directory / 'manifest.json').write_text(manifest_text)
    output.write_text(page.replace('/*__MANIFEST__*/', manifest_text))
    (directory / '.nojekyll').touch()
    # Keep only this build's assets in this dedicated output directory.
    keep = {entry['url'] for group in manifest['datasets'].values() for entry in group.values()} | {css['url'], js['url']}
    for old in (directory / 'assets').iterdir():
        if old.is_file() and re.fullmatch(r'[a-z-]+\.[a-f0-9]{64}\.(?:json(?:\.gz)?|js|css)', old.name) and f'assets/{old.name}' not in keep:
            old.unlink()
    print(f'Built website {output} ({output.stat().st_size:,} bytes); datasets load on demand.')
    for name, entry in manifest['datasets'].items():
        print(f'  {name}: {entry["gzip"]["bytes"]:,} compressed bytes')
