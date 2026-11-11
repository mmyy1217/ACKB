#!/usr/bin/env python3
"""Extract conditional CCE declarations without executing the device compiler."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VERSION = "9.3.0~weekly.20261104.01"
REVISION = "1"
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_$][\w$]*|0[xX][\da-fA-F]+[uUlL]*|\d+(?:\.\d+)?[uUlLfF]*|\.\.\.|##|::|&&|\|\||->|==|!=|<=|>=|<<|>>|\+\+|--|[^\s]')
COMMENT = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/')
BUILTIN = re.compile(r'\b__builtin_cce_\w+')
MARKERS = {"CCE_INTRINSIC", "CCE_AICORE_INLINE", "CCE_FUNC", "__avo", "CALLEE_ATTR", "PIPE_ID", "DEPRECATED"}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def file_digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def tokens(value):
    return TOKEN.findall(value)


def clean(value):
    return COMMENT.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]) if m[0].startswith(('//', '/*')) else m[0], value)


def pretty(ts):
    result, previous = '', ''
    for t in ts:
        tight = t in (')', ']', ';', ',', '::', '.') or previous in ('(', '[', '::', '.') or t == '('
        result += ('' if not result or tight else ' ') + t
        previous = t
    return result


def split_args(ts):
    parts, part, stack = [], [], []
    for t in ts:
        if t in ('(', '[', '{'):
            stack.append(t)
        elif t in (')', ']', '}') and stack:
            stack.pop()
        if t == ',' and not stack:
            parts.append(part)
            part = []
        else:
            part.append(t)
    return parts + [part] if part or parts else []


def matching(ts, start, left='(', right=')'):
    depth = 0
    for i in range(start, len(ts)):
        depth += ts[i] == left
        depth -= ts[i] == right
        if left == '<' and ts[i] == '>>':
            depth -= 2
        if depth <= 0:
            return i
    raise ValueError(f'Unbalanced {left} at token {start}')


def expand(ts, macros, disabled=frozenset(), depth=0):
    if depth > 30:
        raise ValueError('Macro expansion exceeded 30 levels')
    result, i = [], 0
    while i < len(ts):
        name = ts[i]
        macro = macros.get(name)
        if not macro or name in disabled or name in MARKERS:
            result.append(name)
            i += 1
            continue
        params, body, _ = macro
        if params is None:
            result.append(name)
            i += 1
            continue
        if i + 1 >= len(ts) or ts[i + 1] != '(':
            result.append(name)
            i += 1
            continue
        end = matching(ts, i + 1)
        args = split_args(ts[i + 2:end])
        if not args and len(params) == 1 and params[0] != '...':
            args = [[]]
        variadic = bool(params and params[-1] == '...')
        if (not variadic and len(args) != len(params)) or (variadic and len(args) < len(params) - 1):
            result.extend(ts[i:end + 1])
            i = end + 1
            continue
        values = dict(zip(params, args))
        if variadic:
            tail = []
            for argument in args[len(params) - 1:]:
                if tail:
                    tail.append(',')
                tail.extend(argument)
            values['__VA_ARGS__'] = tail
        replaced, j = [], 0
        while j < len(body):
            t = body[j]
            if t == '#' and j + 1 < len(body) and body[j + 1] in values:
                replaced.append(json.dumps(pretty(values[body[j + 1]])))
                j += 2
                continue
            replaced.extend(values.get(t, [t]) or ['__CCE_OPS_EMPTY_ARG__'])
            j += 1
        while '##' in replaced:
            k = replaced.index('##')
            if k == 0 or k + 1 == len(replaced):
                raise ValueError(f'Invalid token paste in {name}')
            replaced[k - 1:k + 2] = [(replaced[k - 1] + replaced[k + 1]).replace('__CCE_OPS_EMPTY_ARG__', '')]
        replaced = [t for t in replaced if t != '__CCE_OPS_EMPTY_ARG__']
        result.extend(expand(replaced, macros, disabled | {name}, depth + 1))
        i = end + 1
    return result


def group_for(filename):
    if 'legacy' in filename:
        return 'Legacy SIMD'
    if 'simt' in filename:
        return 'SIMT'
    if '_ave' in filename:
        return 'Vector / AVE'
    if any(x in filename for x in ('types', 'defines', 'builtin_vars', 'runtime', 'dpp')):
        return '配套定义'
    return 'AI Core'


def family_for(name):
    n = name.lower().lstrip('_')
    if any(x in n for x in ('copy', 'load2d', 'load3d', 'dma', 'mov_', 'load_cbuf', 'img2col')):
        return '搬运 / DMA'
    if any(x in n for x in ('flag', 'barrier', 'sync', 'fence', 'wait', 'pipe')):
        return '同步 / 流水'
    if any(x in n for x in ('cvt', 'conv_', 'convert', 'dequant', 'quant', 'cast')):
        return '类型转换'
    if any(x in n for x in ('mad', 'mmad', 'matmul', 'gemm', 'winograd', 'mx')):
        return '矩阵 / Cube'
    if 'atomic' in n or n.startswith('atom_'):
        return '原子操作'
    if any(x in n for x in ('spr', 'ctrl', 'get_', 'set_', 'read_', 'write_')):
        return '控制 / 寄存器'
    if any(x in n for x in ('ld', 'st', 'gather', 'scatter', 'alloc', 'free', 'prefetch')):
        return '访存 / 布局'
    return '计算 / 其他'


def signature_parts(ts):
    filtered, i = [], 0
    template = []
    while i < len(ts):
        if ts[i] in ('__attribute__', '__declspec') and i + 1 < len(ts) and ts[i + 1] == '(':
            i = matching(ts, i + 1) + 1
        elif ts[i] == 'template' and i + 1 < len(ts) and ts[i + 1] == '<':
            end = matching(ts, i + 1, '<', '>')
            template += ts[i:end + 1]
            i = end + 1
        elif ts[i] == '[':
            i = matching(ts, i, '[', ']') + 1
        elif ts[i] in MARKERS or ts[i] in ('static', 'inline', '__inline__', '__forceinline__', 'constexpr', '__aicore__', '__simt_callee__', '__host__', '__device__'):
            i += 1
        else:
            filtered.append(ts[i])
            i += 1
    for i, t in enumerate(filtered):
        if t == '(' and i > 0:
            name = filtered[i - 1]
            if not re.fullmatch(r'[A-Za-z_$][\w$]*', name) or name in ('decltype', 'alignas', 'static_assert', 'if', 'while'):
                return None
            end = matching(filtered, i)
            if i < 2 or '=' in filtered[:i]:
                return None
            return name, pretty(filtered[:i - 1]), [pretty(x) for x in split_args(filtered[i + 1:end])], pretty(template)
    return None


def typedef_name(ts):
    filtered, i = [], 0
    while i < len(ts):
        if ts[i] == '__attribute__' and i + 1 < len(ts) and ts[i + 1] == '(':
            i = matching(ts, i + 1) + 1
        else:
            filtered.append(ts[i])
            i += 1
    if '[' in filtered:
        filtered = filtered[:filtered.index('[')]
    identifiers = [t for t in filtered if re.fullmatch(r'[A-Za-z_$][\w$]*', t)]
    return identifiers[-1] if identifiers else 'anonymous'


def extract_file(path, relative):
    original = path.read_text()
    stripped = clean(original)
    rawlines, lines = original.splitlines(), stripped.splitlines()
    stream, meta, macros, macro_records, includes = [], [], {}, [], []
    variants = {}
    conditions, errors = [], []
    i = 0
    while i < len(lines):
        start = i
        s = lines[i]
        while s.rstrip().endswith('\\') and i + 1 < len(lines):
            s = s.rstrip()[:-1] + ' ' + lines[i + 1]
            i += 1
        end = i
        i += 1
        if not s.lstrip().startswith('#') and any(t in macros and macros[t][0] is not None and t not in MARKERS for t in tokens(s)):
            while tokens(s).count('(') > tokens(s).count(')') and i < len(lines) and not lines[i].lstrip().startswith('#'):
                s += ' ' + lines[i]
                end = i
                i += 1
        source = {'file': relative, 'line': start + 1, 'end_line': end + 1}
        directive = re.match(r'\s*#\s*(\w+)\s*(.*)', s)
        if directive:
            op, body = directive.groups()
            if op in ('if', 'ifdef', 'ifndef'):
                expr = body if op == 'if' else f'{"!" if op == "ifndef" else ""}defined({body.strip()})'
                conditions.append({'seen': [expr.strip()], 'active': expr.strip()})
            elif op in ('elif', 'else') and conditions:
                frame = conditions[-1]
                prior = ' || '.join(f'({x})' for x in frame['seen'])
                frame['active'] = f'!({prior})' + (f' && ({body})' if op == 'elif' else '')
                if op == 'elif':
                    frame['seen'].append(body)
            elif op == 'endif' and conditions:
                conditions.pop()
            elif op == 'include':
                includes.append({'name': body.strip(' <>"'), **source, 'conditions': [x['active'] for x in conditions]})
            elif op == 'define':
                m = re.match(r'(\w+)(\(([^)]*)\))?\s*(.*)', body)
                if m:
                    name, form, args, value = m.groups()
                    params = [x.strip() for x in args.split(',') if x.strip()] if form else None
                    definition_source = {**source, 'conditions': [x['active'] for x in conditions]}
                    previous = macros.get(name)
                    if previous and previous[:2] != (params, tokens(value)):
                        variants[name] = True
                    macros[name] = (params, tokens(value), definition_source)
                    macro_signature = '#define ' + name + ('(' + args + ')' if form else '') + (' ' + pretty(tokens(value)) if value else '')
                    macro_records.append({'name': name, 'kind': 'macro', 'signature': macro_signature, 'conditions': [x['active'] for x in conditions], 'source': source, 'builtins': sorted(set(BUILTIN.findall(value))), 'parameters': params})
            elif op == 'undef':
                macros.pop(body.strip(), None)
                variants.pop(body.strip(), None)
            continue
        ts = tokens(s)
        active = [x['active'] for x in conditions]
        ambiguous = {name for name in variants if name not in MARKERS and name in macros and macros[name][0] is not None and active[:len(macros[name][2]['conditions'])] != macros[name][2]['conditions']}
        for name in ambiguous.intersection(ts):
            errors.append({'reason': 'Conditional macro alternatives require preprocessing', 'text': s.strip(), **source})
        try:
            expanded = expand(ts, macros, frozenset(ambiguous))
        except ValueError as exc:
            expanded = ts
            errors.append({'reason': str(exc), 'text': s.strip(), **source})
        defined_at = [macros[t][2] for t in ts if t in macros and macros[t][0] is not None and t not in MARKERS]
        entry = {**source, 'conditions': [x['active'] for x in conditions], 'generated': expanded != ts, 'macro_sources': defined_at}
        stream.extend(expanded)
        meta.extend([entry] * len(expanded))

    records, units = [], Counter()

    def record(kind, name, header, a, b, body=(), namespace=''):
        entry = meta[a]
        signature = pretty(header)
        conditions_here = entry['conditions']
        source = {k: entry[k] for k in ('file', 'line', 'end_line')}
        if b > a:
            source['end_line'] = max(source['end_line'], meta[b - 1]['end_line'])
        excerpt = '\n'.join(rawlines[source['line'] - 1:source['end_line']])
        data = {'name': name, 'kind': kind, 'signature': signature, 'conditions': conditions_here, 'source': source, 'generated': entry['generated'], 'macro_sources': entry['macro_sources'], 'builtins': sorted(set(BUILTIN.findall(' '.join(list(header) + list(body))))), 'excerpt': excerpt}
        data['namespace'] = namespace
        if kind == 'interface':
            parts = signature_parts(header)
            data.update(return_type=parts[1], parameters=parts[2], template=parts[3])
            data['definition'] = pretty(list(header) + (['{'] + list(body) + ['}'] if body else []))
            data['calls'] = sorted(set(re.findall(r'CCE_SCALAR\s*\(\s*(\w+)\s*\)', data['definition'])))
        records.append(data)
        units[kind] += 1

    def parse(a, limit, namespace=''):
        pos = a
        while pos < limit:
            if stream[pos] in (';', '}'):
                pos += 1
                continue
            start = pos
            parens = brackets = 0
            while pos < limit:
                t = stream[pos]
                if t == '(':
                    parens += 1
                elif t == ')':
                    parens -= 1
                elif t == '[':
                    brackets += 1
                elif t == ']':
                    brackets -= 1
                if parens == 0 and brackets == 0 and t in (';', '{'):
                    break
                pos += 1
            if pos == limit:
                if stream[start:pos]:
                    errors.append({'reason': 'Unterminated scope item', 'text': pretty(stream[start:pos])[:1500], **{k: meta[start][k] for k in ('file', 'line', 'end_line')}})
                break
            header = stream[start:pos]
            delimiter = stream[pos]
            try:
                close = matching(stream, pos, '{', '}') if delimiter == '{' else pos
            except ValueError as exc:
                errors.append({'reason': str(exc), 'text': pretty(header), **{k: meta[start][k] for k in ('file', 'line', 'end_line')}})
                break
            if 'namespace' in header or (header[:1] == ['extern'] and delimiter == '{'):
                ns = '::'.join(filter(None, [namespace, pretty(header[1:])])) if 'namespace' in header else namespace
                parse(pos + 1, close, ns)
            elif header[:1] in (['enum'], ['struct'], ['class']) or header[:2] in (['typedef', 'enum'], ['typedef', 'struct']):
                tail = close if delimiter == ';' else close + 1
                while delimiter != ';' and tail < limit and stream[tail] not in (';', '}'):
                    tail += 1
                full = stream[start:tail]
                names = re.findall(r'(?:enum(?: class)?|struct|class)\s+(\w+)', pretty(header))
                name = names[0] if names else (stream[tail - 1] if tail > close + 1 else 'anonymous')
                record('type', name, full, start, tail, namespace=namespace)
                close = tail - 1
            else:
                try:
                    parts = signature_parts(header)
                except ValueError:
                    parts = None
                if parts:
                    record('interface', parts[0], header, start, close + 1, stream[pos + 1:close] if delimiter == '{' else [], namespace=namespace)
                elif header[:1] in (['typedef'], ['using']):
                    name = header[1] if header[0] == 'using' else typedef_name(header)
                    record('type', name, header, start, close + 1, namespace=namespace)
                elif '(' not in header or header[:1] == ['constexpr']:
                    ids = [t for t in header[:header.index('=') if '=' in header else len(header)] if re.fullmatch(r'\w+', t)]
                    record('constant', ids[-1] if ids else 'anonymous', stream[start:close + 1], start, close + 1, namespace=namespace)
                else:
                    units['unresolved'] += 1
                    errors.append({'reason': 'Unclassified declaration or macro invocation', 'text': pretty(stream[start:close + 1])[:1500], **{k: meta[start][k] for k in ('file', 'line', 'end_line')}})
            pos = close + 1
    parse(0, len(stream))
    for m in macro_records:
        if m['name'] in ('set_flag', 'wait_flag', 'pipe_barrier') and m['parameters'] is not None and m['builtins']:
            records.append({**m, 'kind': 'interface_macro', 'excerpt': '\n'.join(rawlines[m['source']['line'] - 1:m['source']['end_line']]), 'generated': False, 'macro_sources': []})
        else:
            records.append({**m, 'excerpt': '\n'.join(rawlines[m['source']['line'] - 1:m['source']['end_line']]), 'generated': False, 'macro_sources': []})
    return records, errors, includes, dict(units)


def extract(toolkit, output, package=None):
    compiler = toolkit / 'tools/bisheng_compiler'
    include = compiler / 'lib/clang/15.0.5/include'
    if not include.is_dir():
        raise ValueError(f'Expected CCE resource headers at {include}')
    version_file = toolkit / 'share/info/bisheng-compiler/version.info'
    version_metadata = version_file.read_text() if version_file.exists() else None
    if version_metadata and ('Version=9.3.0\n' not in version_metadata or 'timestamp=20261104_' not in version_metadata):
        raise ValueError('This extractor targets CANN 9.3.0 weekly 20261104; the installed compiler metadata differs.')
    seeds = sorted({*include.glob('*cce*.h'), *include.glob('*dpp*.h')})
    excluded_names = {'__clang_cce_aicpu_neon.h'}
    files = [p for p in seeds if p.name not in excluded_names]
    manifest, all_records, errors, all_includes, excluded_records = [], [], [], [], []
    for path in files:
        relative = path.relative_to(include).as_posix()
        records, failures, includes, units = extract_file(path, relative)
        manifest.append({'path': relative, 'sha256': digest(path.read_bytes()), 'bytes': path.stat().st_size, 'units': units})
        for rec in records:
            if rec['name'].startswith('__pto_'):
                excluded_records.append({'name': rec['name'], 'source': rec['source'], 'reason': 'PTO-only wrapper; outside CCE interface scope'})
                continue
            rec['group'] = group_for(relative)
            if rec['name'].startswith('debug_') or rec['name'] == 'KERNEL_TASK_TYPE_DEFAULT':
                rec['kind'] = 'helper'
            if rec['group'] == '配套定义' and rec['kind'] in ('interface', 'interface_macro'):
                rec['kind'] = 'helper'
            rec['family'] = family_for(rec['name']) if rec['kind'].startswith('interface') else '配套定义'
            rec['id'] = digest(json.dumps([VERSION, relative, rec['source']['line'], rec['kind'], rec['signature'], rec['conditions']], ensure_ascii=False).encode())[:20]
            rec['status'] = 'header'
            all_records.append(rec)
        errors.extend(failures)
        all_includes.extend(includes)
    all_records.sort(key=lambda r: (r['name'].lower(), r['source']['file'], r['source']['line'], r['signature']))
    counts = Counter(x['kind'] for x in all_records)
    raw_builtins = sorted({name for p in files for name in BUILTIN.findall(p.read_text())})
    linked = {b for r in all_records if r['kind'].startswith('interface') for b in r['builtins']}
    dependencies = sorted({i['name'] for i in all_includes})
    dataset = {'schema_version': 1, 'extractor_revision': REVISION, 'version': VERSION, 'source': {'type': 'installed_toolkit', 'package_name': 'Ascend-cann-toolkit_' + VERSION + '_linux-x86_64.run', 'package_sha256': None, 'package_verified': False, 'resource_root': 'tools/bisheng_compiler/lib/clang/15.0.5/include', 'compiler_files': [{'path': str(p.relative_to(toolkit)), 'sha256': file_digest(p)} for p in (compiler / 'bin/ccec', compiler / 'bin/bisheng') if p.exists()]}, 'counts': dict(counts), 'files': manifest, 'records': all_records, 'report': {'unresolved': errors, 'excluded_files': [{'path': x, 'reason': 'AI CPU NEON; outside AI Core scope'} for x in sorted(excluded_names)], 'includes': all_includes, 'external_includes': [d for d in dependencies if d not in {p.name for p in files}], 'raw_builtin_names': raw_builtins, 'unlinked_builtin_names': sorted(set(raw_builtins) - linked), 'limitations': ['Symbolic conditions are preserved, not evaluated for a device.', 'Macro expansion covers function-like macros and token pasting; this is not a full C++ preprocessor.', 'Object-like macros remain symbolic; generated interfaces retain definition and invocation locations.', 'Internal conditionals in wrapper bodies are not an execution trace.', 'External standard-library and runtime includes are inventoried but not recursively parsed.', 'Installed headers have not been compared with the original .run package.', 'No device compilation or runtime experiments have been performed.']}}
    dataset['report']['excluded_records'] = excluded_records
    dataset['source']['package_sha256'] = file_digest(package) if package else None
    dataset['source']['version_metadata'] = {'path': str(version_file.relative_to(toolkit)), 'text': version_metadata, 'sha256': file_digest(version_file)} if version_metadata else None
    dataset['extractor_sha256'] = digest(Path(__file__).read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'files': len(files), 'counts': counts, 'unresolved': len(errors), 'builtin_names': len(raw_builtins)}, ensure_ascii=False))
    return dataset


def validate(data, toolkit=None):
    records = data['records']
    assert len({r['id'] for r in records}) == len(records), 'Duplicate record IDs'
    assert dict(Counter(r['kind'] for r in records)) == data['counts'], 'Incorrect counts'
    manifest = {f['path']: f for f in data['files']}
    if data['source']['package_verified']:
        verification = data['source']['package_verification']
        assert verification['scope'] == 'scanned_resource_headers'
        assert not verification['missing'] and not verification['mismatched']
        assert verification['outer_sha256'] == data['source']['package_sha256']
        assert {m['file'] for m in verification['matches']} == set(manifest)
        for match in verification['matches']:
            assert match['dataset_sha256'] == match['package_sha256'] == manifest[match['file']]['sha256']
    for r in records:
        assert r['source']['file'] in manifest
        assert r['name'] and r['signature'] and r['status'] == 'header'
        assert r['source']['line'] > 0 and r['source']['end_line'] >= r['source']['line']
        if r['kind'] == 'interface':
            assert isinstance(r['parameters'], list) and r['return_type']
    if toolkit:
        resource = toolkit / data['source']['resource_root']
        for f in data['files']:
            assert digest((resource / f['path']).read_bytes()) == f['sha256'], f['path']
        for r in records:
            lines = (resource / r['source']['file']).read_text().splitlines()
            assert '\n'.join(lines[r['source']['line'] - 1:r['source']['end_line']]) == r['excerpt'], r['id']
    print(f'Validated {len(records)} records, {len(manifest)} files, unique IDs and source references.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['extract', 'validate'])
    parser.add_argument('--toolkit', type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--data', type=Path, default=ROOT / 'data' / VERSION / 'catalog.json')
    args = parser.parse_args()
    if args.action == 'extract':
        if args.toolkit is None:
            parser.error('extract requires --toolkit')
        extract(args.toolkit, args.data, args.package)
    else:
        validate(json.loads(args.data.read_text()), args.toolkit)


if __name__ == '__main__':
    main()
