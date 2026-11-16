#!/usr/bin/env python3
"""Extract and validate the two-layer AscendC knowledge base (basic_api & c_api/simt_api) for Ascend 950 (dav_3510)."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from catalog import ROOT, VERSION, clean
from ccec_ops import Ops
from ccec_transfer import transfer_for
from compatibility import evaluate
from database import Database

ASC_STRIP_RE = re.compile(
    r'R"([A-Za-z0-9_]*)\([\s\S]*?\)\1"'
    r'|"(?:\\\r?\n|\\.|[^"\\\r\n])*"'
    r"|\'(?:\\.|[^\'\\\r\n])*\'"
    r'|//[^\n]*|/\*[\s\S]*?\*/'
)

DEFAULT_TOOLKIT = Path('/home/zuomin/Ascend/cann-weekly-9.3.0-20261104.01/cann-9.3.0')
OUTPUT = ROOT / 'data/ascendc/index.json'
SCHEMA_VERSION = 'ackb.ascendc.v1'

LIMITATIONS = [
    'Static extraction from CANN 9.3.0~weekly.20261104.01 AscendC headers; no device compilation or execution was performed.',
    'Target assessment is locked to Huawei Ascend 950PR_9579 (__NPU_ARCH__ == 3510 / dav_3510).',
    'In c_api, declarations in vector_compute/ without reg_base_impl (3510) definitions are marked excluded (declared_only_2201) rather than supported on 950.',
    'CCEC callee links are extracted lexically from 3510 implementation bodies and classified against CCEC wrappers vs clang_builtin_alias entries.',
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eval_3510(conditions: list[str]) -> str:
    if not conditions:
        return 'matches'
    vals = [evaluate(c, {'__NPU_ARCH__': 3510, '__CCE_AICORE__': 3510}) for c in conditions]
    if False in vals:
        return 'excluded'
    if None in vals:
        return 'unknown'
    return 'matches'


def classify_ascendc_family(name: str, rel_file: str, signature: str = '') -> tuple[str, dict | None]:
    low = name.lower()
    f = rel_file.lower()
    transfer = ascendc_transfer(low, f, signature)
    if transfer or any(k in f for k in ('datamove', 'data_copy', 'reg_load', 'reg_store', 'loadalign', ' loadunalign', 'storealign', 'storeunalign')) or any(k in low for k in ('datacopy', 'copy_', 'load2d', 'load3d', 'fixpipe')):
        if any(k in f for k in ('reg_compute/load', 'reg_compute/store', 'reg_compute/gather', 'reg_compute/scatter')) or any(k in low for k in ('loadalign', 'loadunalign', 'storealign', 'storeunalign', 'vld', 'vst')):
            return '访存 / 布局', None
        return '搬运 / DMA', transfer
    if 'cube_compute' in f or '_mm_' in f or '_gemm_' in f or '_conv2d_' in f or any(k in low for k in ('mmad', 'gemm', 'matmul', 'conv2d')):
        return '矩阵 / Cube', None
    if 'atomic' in f or 'atomic' in low:
        return '原子操作', None
    if 'sync' in f or 'event' in f or 'membar' in f or any(k in low for k in ('setflag', 'waitflag', 'set_flag', 'wait_flag', 'barrier', 'pipe_barrier', 'reg_barrier', 'syncthreads', 'syncall')):
        return '同步 / 流水', None
    if 'convert' in f or 'vconv' in f or 'mulcast' in f or any(k in low for k in ('cast', 'vconv', 'cvt')):
        return '类型转换', None
    if any(k in f for k in ('gather', 'scatter', 'transpose', 'brcb', 'vpadding', 'permute', 'sort', 'hist')) or any(k in low for k in ('gather', 'scatter', 'transpose', 'brcb', 'sort', 'hist', 'load', 'store')):
        return '访存 / 布局', None
    if any(k in f for k in ('spr', 'cache_ctrl', 'sys_var', 'addrreg', 'maskreg', 'limits')) or any(k in low for k in ('set_', 'get_', 'dcci', 'cache', 'blockidx', 'block_idx', 'subblock', 'coreid')):
        return '控制 / 寄存器', None
    return '计算 / 其他', None


def ascendc_transfer(low_name: str, low_file: str, sig: str = '') -> dict | None:
    routes = [
        (('gm2ub', 'gm_to_ub', 'out_to_ub'), ('gm', 'ubuf', 'GM → UB')),
        (('ub2gm', 'ub_to_gm', 'ub_to_out'), ('ubuf', 'gm', 'UB → GM')),
        (('gm2l1', 'gm_to_cbuf', 'out_to_l1'), ('gm', 'cbuf', 'GM → L1')),
        (('l12l0a', 'cbuf_to_ca', 'l1_to_l0a'), ('cbuf', 'ca', 'L1 → L0A')),
        (('l12l0b', 'cbuf_to_cb', 'l1_to_l0b'), ('cbuf', 'cb', 'L1 → L0B')),
        (('gm2l0a',), ('gm', 'ca', 'GM → L0A')),
        (('gm2l0b',), ('gm', 'cb', 'GM → L0B')),
        (('l0c2gm', 'cc_to_gm', 'fixpipe'), ('cc', 'gm', 'L0C → GM')),
        (('l0c2l1', 'cc_to_cbuf'), ('cc', 'cbuf', 'L0C → L1')),
        (('l0c2ub', 'cc_to_ub'), ('cc', 'ubuf', 'L0C → UB')),
        (('ub2l1', 'ubuf_to_cbuf'), ('ubuf', 'cbuf', 'UB → L1')),
        (('l12ub', 'cbuf_to_ubuf'), ('cbuf', 'ubuf', 'L1 → UB')),
        (('ub2ub', 'ubuf_to_ubuf'), ('ubuf', 'ubuf', 'UB → UB')),
        (('l12bt', 'cbuf_to_bt'), ('cbuf', 'bt', 'L1 → BT')),
        (('l12fb', 'cbuf_to_fbuf'), ('cbuf', 'fbuf', 'L1 → FixpipeBuf')),
    ]
    for keys, (src, dst, label) in routes:
        if any(k in low_name for k in keys):
            return {
                'id': f'transfer:{src}:{dst}',
                'src': src,
                'dst': dst,
                'label': label,
                'search_alias': label.replace(' → ', '2').replace(' ', ''),
            }
    return transfer_for(low_name)


def strip_comments(text: str) -> str:
    # Normalize string/char literals to empty literals on single lines while blanking comments,
    # so unmatched quotes in CRLF line continuations cannot swallow following functions.
    def _repl(m):
        s = m[0]
        if s.startswith(('"', "'", 'R"')):
            return re.sub(r'[^\n]', ' ', s)
        return re.sub(r'[^\n]', ' ', s)
    return ASC_STRIP_RE.sub(_repl, text)


def parse_functions_in_header(text: str, rel_file: str, known_ccec_names: set[str]) -> list[dict]:
    """Extract function declarations and inline definitions with line numbers, conditions, and callees."""
    stripped = strip_comments(text)
    raw_lines = text.splitlines()
    lines = stripped.splitlines()

    # Track preprocessor condition frames per line
    line_conds = {}
    frames = []
    idx = 0
    while idx < len(lines):
        start_ln = idx + 1
        line = lines[idx]
        idx += 1
        while line.rstrip().endswith('\\') and idx < len(lines):
            line = line.rstrip()[:-1] + ' ' + lines[idx]
            idx += 1
        m = re.match(r'^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)$', line)
        if m:
            op, body = m.group(1), m.group(2).strip()
            if op in ('if', 'ifdef', 'ifndef'):
                expr = body if op == 'if' else f'{"!" if op == "ifndef" else ""}defined({body})'
                frames.append({'seen': [expr], 'active': expr})
            elif op in ('elif', 'else') and frames:
                prior = ' || '.join('(' + s + ')' for s in frames[-1]['seen'])
                frames[-1]['active'] = f'!({prior})' + (f' && ({body})' if op == 'elif' else '')
                if op == 'elif':
                    frames[-1]['seen'].append(body)
            elif op == 'endif' and frames:
                frames.pop()
        for ln in range(start_ln, idx + 1):
            line_conds[ln] = [f['active'] for f in frames if not re.search(r'INCLUDE_.*_H|ASCENDC_MODULE_.*_H|ASCENDC_C_API_INCLUDE', f['active'])]

    # Scan for __aicore__ / __simd_callee__ / __inline__ / template function declarations & definitions
    results = []
    pattern = re.compile(
        r'(?:(template\s*<[^{;]+?>)\s*)?'
        r'(?:ASC_DEPRECATED\([^\n]+\)\s*)?'
        r'(?:__ASC_USE_RESERVED_UBUF__\([^\n]+\)\s*)?'
        r'((?:__aicore__|__simd_callee__|__device__|__host__|inline|__inline__|static|constexpr)\s+'
        r'[^{;]+?\b([A-Za-z_][A-Za-z0-9_]*)\s*\(([^{;]*?)\))\s*(;|\{)',
        re.S,
    )
    for m in pattern.finditer(stripped):
        tmpl, decl_head, func_name, params_raw, term = m.groups()
        if func_name in ('if', 'for', 'while', 'switch', 'return', 'sizeof', 'alignof', 'static_assert'):
            continue
        start_pos = m.start()
        start_line = stripped.count('\n', 0, start_pos) + 1
        end_pos = m.end()
        body_text = ''
        if term == '{':
            depth = 1
            p = end_pos
            while p < len(stripped) and depth > 0:
                c = stripped[p]
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                p += 1
            end_pos = p
            body_text = stripped[m.end() - 1:end_pos]
        end_line = stripped.count('\n', 0, end_pos) + 1
        sig_clean = re.sub(r'\s+', ' ', ((tmpl + ' ') if tmpl else '') + decl_head).strip()
        params = [re.sub(r'\s+', ' ', p).strip() for p in split_params(params_raw) if p.strip()]
        ret_prefix = re.sub(r'\s+', ' ', decl_head[:decl_head.rfind(func_name)]).strip()
        ret_type = re.sub(r'\b(__aicore__|__simd_callee__|__device__|__host__|inline|__inline__|static|constexpr|__inout_pipe__\([^)]*\)|__in_pipe__\([^)]*\)|__out_pipe__\([^)]*\))\b', '', ret_prefix).strip()

        callees = []
        raw_calls = []
        reg_refs = []
        core_guards = []
        if body_text:
            for cg in re.finditer(r'\b(ASC(?:END)?_IS_AI[CV])\b', body_text):
                if cg.group(1) not in core_guards:
                    core_guards.append(cg.group(1))
            for tok_m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(|<)', body_text):
                callee = tok_m.group(1)
                if callee == func_name:
                    continue
                if callee in known_ccec_names and callee not in callees:
                    callees.append(callee)
                elif callee not in raw_calls and callee not in ('if', 'for', 'while', 'switch', 'return', 'static_assert', 'SupportType', 'SupportEnum', 'IsSameType', 'CheckRegTrait', 'GetDstType'):
                    raw_calls.append(callee)
            for m_reg in re.finditer(r'\bReg::([A-Za-z_][A-Za-z0-9_]*)\b', body_text):
                if m_reg.group(1) not in reg_refs:
                    reg_refs.append(m_reg.group(1))

        excerpt = '\n'.join(raw_lines[max(0, start_line - 1):min(len(raw_lines), end_line)])
        deprecated = 'ASC_DEPRECATED' in excerpt
        results.append({
            'name': func_name,
            'template': re.sub(r'\s+', ' ', tmpl).strip() if tmpl else '',
            'return_type': ret_type,
            'parameters': params,
            'signature': sig_clean + (';' if term == ';' else ''),
            'has_body': term == '{',
            'core_guards': core_guards,
            'callees': callees,
            'raw_calls': raw_calls,
            'reg_refs': reg_refs,
            'deprecated': deprecated,
            'conditions': line_conds.get(start_line, []),
            'source': {'file': rel_file, 'line': start_line, 'end_line': end_line},
            'excerpt': excerpt[:2400],
        })
    return results


def split_params(raw: str) -> list[str]:
    parts, cur, depth = [], [], 0
    for ch in raw:
        if ch in '<(':
            depth += 1
        elif ch in '>)':
            depth = max(0, depth - 1)
        if ch == ',' and depth == 0:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append(''.join(cur))
    return parts


def build_ccec_callee_index(db: Database, ops_model: dict) -> dict[str, dict]:
    """Index CCEC names by 3510 layer (direct_ccec_intrinsic vs via_ccec_wrapper) and op_ids."""
    layers = ops_model['record_layers']
    target = db.target(chip='Ascend950PR_9579')
    by_name = defaultdict(list)
    for r in db.records:
        if r['kind'].startswith('interface'):
            by_name[r['name']].append(r)

    index = {}
    for name, recs in by_name.items():
        active = [r for r in recs if db.condition(r, target) != 'excluded'] or recs
        lset = {layers[r['id']]['layer'] for r in active if r['id'] in layers}
        op_ids_raw = {oid for r in active for oid in layers.get(r['id'], {}).get('op_ids', [])}
        def op_sort_key(oid: str):
            short = oid.removeprefix('ccec_op___builtin_cce_')
            exact = 0 if short == name else 1 if short.startswith(name + '_') else 2
            return (exact, len(short), short)
        op_ids = sorted(op_ids_raw, key=op_sort_key)
        wrapper_ids = [r['id'] for r in active if layers.get(r['id'], {}).get('layer') == 'wrapper']
        entry_ids = [r['id'] for r in active if layers.get(r['id'], {}).get('layer') == 'intrinsic_entry']
        if lset == {'intrinsic_entry'}:
            call_kind = 'direct_ccec_intrinsic'
        elif lset == {'wrapper'}:
            call_kind = 'via_ccec_wrapper'
        elif 'intrinsic_entry' in lset and 'wrapper' in lset:
            call_kind = 'both_intrinsic_and_wrapper'
        else:
            call_kind = 'unresolved'
        index[name] = {
            'name': name,
            'call_kind': call_kind,
            'op_ids': op_ids[:16],
            'wrapper_record_ids': wrapper_ids[:6],
            'entry_record_ids': entry_ids[:6],
        }
    return index


def extract_capi_layer(toolkit: Path, ccec_index: dict[str, dict], files_meta: dict[str, dict]) -> list[dict]:
    """Extract the lower-layer unified ASC C-API + SIMT API (c_api + simt_api)."""
    known_ccec = set(ccec_index)
    asc_root = toolkit / 'x86_64-linux/asc'

    # 1) Parse 3510 implementation files first (impl/c_api/reg_base_impl + impl/c_api/experimental + impl/simt_api)
    impl_3510_by_name = defaultdict(list)
    impl_2201_names = set()

    for impl_dir, is_3510 in [
        (asc_root / 'impl/c_api/reg_base_impl', True),
        (asc_root / 'impl/c_api/experimental', True),
        (asc_root / 'impl/simt_api', True),
        (asc_root / 'impl/c_api/memory_base_impl', False),
    ]:
        if not impl_dir.exists():
            continue
        for fp in sorted(impl_dir.rglob('*.h')):
            rel = fp.relative_to(toolkit).as_posix()
            if 'npu_arch_920' in rel:
                continue
            files_meta[rel] = {'path': rel, 'sha256': sha256(fp)}
            text = fp.read_text(errors='replace')
            for fn in parse_functions_in_header(text, rel, known_ccec):
                if not fn['has_body']:
                    continue
                if is_3510:
                    impl_3510_by_name[fn['name']].append(fn)
                else:
                    impl_2201_names.add(fn['name'])

    # 2) Parse public headers in include/c_api and include/simt_api (excluding simt_api/cpp which belongs to AscendC::Simt C++ layer)
    decl_by_name = defaultdict(list)
    for inc_dir in (asc_root / 'include/c_api', asc_root / 'include/simt_api'):
        for fp in sorted(inc_dir.rglob('*.h')):
            rel = fp.relative_to(toolkit).as_posix()
            if '/simt_api/cpp/' in rel:
                continue
            files_meta[rel] = {'path': rel, 'sha256': sha256(fp)}
            text = fp.read_text(errors='replace')
            for fn in parse_functions_in_header(text, rel, known_ccec):
                decl_by_name[fn['name']].append(fn)

    all_names = sorted(set(decl_by_name) | set(impl_3510_by_name))
    items = []
    for name in all_names:
        # Filter out internal helper macros/functions that aren't public asc_* or simt_api interfaces
        decls = decl_by_name.get(name, [])
        impls_3510 = impl_3510_by_name.get(name, [])
        if not decls and not name.startswith('asc_'):
            continue
        sample = (decls or impls_3510)[0]
        rel_file = sample['source']['file']
        if '/utils/' in rel_file and not name.startswith('asc_'):
            continue

        is_simt = '/simt_api/' in rel_file
        is_composite = '/composite/' in rel_file
        is_reg_compute = '/reg_compute/' in rel_file
        is_cube = '/cube_' in rel_file
        is_vec_mem = '/vector_compute/' in rel_file
        is_vec_dma = '/vector_datamove/' in rel_file

        group = (
            'SIMT API' if is_simt
            else 'ASC Composite' if is_composite
            else 'ASC Reg Vector' if is_reg_compute
            else 'ASC Cube' if is_cube
            else 'ASC Vector DMA' if is_vec_dma
            else 'ASC Memory Vector (2201)' if is_vec_mem
            else 'ASC Common / Sync / System'
        )
        family, transfer = classify_ascendc_family(name, rel_file, sample['signature'])

        # Determine 950 (3510) support status
        has_3510_body = bool(impls_3510) or any(d['has_body'] for d in decls)
        if has_3510_body:
            status_3510 = 'matches'
            status_reason = 'implemented_on_3510'
        elif name in impl_2201_names or is_vec_mem:
            status_3510 = 'excluded'
            status_reason = 'declared_only_implemented_on_2201'
        else:
            # Evaluate preprocessor conditions on declarations
            cond_vals = [eval_3510(d['conditions']) for d in decls] if decls else ['unknown']
            status_3510 = 'excluded' if all(v == 'excluded' for v in cond_vals) else 'unknown'
            status_reason = 'declaration_without_3510_body'

        callee_names = sorted({c for fn in (impls_3510 + decls) for c in fn['callees']})
        callee_details = [ccec_index[c] for c in callee_names if c in ccec_index]
        ccec_op_ids = sorted({oid for cd in callee_details for oid in cd['op_ids']})
        core_guards = sorted({cg for fn in (impls_3510 + decls) for cg in fn['core_guards']})

        forms = []
        seen_sigs = set()
        for fn in (decls or impls_3510):
            if fn['signature'] in seen_sigs:
                continue
            seen_sigs.add(fn['signature'])
            forms.append({
                'signature': fn['signature'],
                'return_type': fn['return_type'],
                'parameters': fn['parameters'],
                'source': fn['source'],
            })

        rep_impl = impls_3510[0] if impls_3510 else next((d for d in decls if d['has_body']), sample)
        items.append({
            'id': f'ascendc_capi_{name}',
            'layer': 'capi',
            'name': name,
            'namespace': 'AscendC::Simt' if is_simt and 'AscendC' in sample.get('excerpt', '') else '',
            'group': group,
            'family': family,
            'transfer': transfer,
            'condition_3510': status_3510,
            'status_reason': status_reason,
            'core_guards': core_guards,
            'deprecated': any(fn['deprecated'] for fn in (decls + impls_3510)),
            'overload_count': len(forms),
            'impl_3510_count': len(impls_3510),
            'forms': forms[:24],
            'ccec_callees': callee_details,
            'ccec_op_ids': ccec_op_ids[:16],
            'source': sample['source'],
            'impl_source': rep_impl['source'] if has_3510_body else None,
            'excerpt': rep_impl['excerpt'],
        })
    return items


def extract_basic_layer(toolkit: Path, ccec_index: dict[str, dict], files_meta: dict[str, dict]) -> list[dict]:
    """Extract the upper-layer AscendC Basic API (LocalTensor / GlobalTensor / RegTensor interfaces & dav_3510 impls)."""
    known_ccec = set(ccec_index)
    asc_root = toolkit / 'x86_64-linux/asc'

    # 1) Parse dav_3510 implementation files (impl/basic_api/dav_3510 + impl/basic_api/reg_compute/dav_3510 + impl/simt_api/cpp)
    impl_3510_by_stem = defaultdict(list)
    impl_3510_funcs = defaultdict(list)
    helper_graph = {'reg': defaultdict(list), 'basic': defaultdict(list)}
    for impl_dir in (
        asc_root / 'impl/basic_api/dav_3510',
        asc_root / 'impl/basic_api/reg_compute/dav_3510',
        asc_root / 'impl/simt_api/cpp',
        asc_root / 'include/basic_api/reg_compute',
    ):
        if not impl_dir.exists():
            continue
        is_public_reg = 'include/basic_api/reg_compute' in impl_dir.as_posix()
        for fp in sorted(impl_dir.rglob('*.h')):
            rel = fp.relative_to(toolkit).as_posix()
            if not is_public_reg:
                files_meta[rel] = {'path': rel, 'sha256': sha256(fp)}
            text = fp.read_text(errors='replace')
            stem = fp.name.replace('_impl.h', '').replace('_intf.h', '')
            is_reg_impl = '/reg_compute/' in rel
            domain = 'reg' if is_reg_impl else 'basic'
            for fn in parse_functions_in_header(text, rel, known_ccec):
                if fn['has_body']:
                    if not is_public_reg:
                        impl_3510_by_stem[stem].append(fn)
                        impl_3510_funcs[fn['name']].append(fn)
                    helper_graph[domain][fn['name']].append(fn)

    def resolve_transitive_callees(seeds: list[dict], domain: str, max_depth: int = 4) -> set[str]:
        found = set()
        seen = set()
        queue = [(domain, fn, 0) for fn in seeds]
        while queue:
            cur_dom, fn, depth = queue.pop(0)
            key = (cur_dom, fn['source']['file'], fn['source']['line'])
            if key in seen:
                continue
            seen.add(key)
            found.update(fn['callees'])
            if depth >= max_depth:
                continue
            for rname in fn.get('reg_refs', ()):
                for target_fn in helper_graph['reg'].get(rname, ()):
                    queue.append(('reg', target_fn, depth + 1))
                for suffix in ('Impl', 'Operator', 'Cal'):
                    for target_fn in helper_graph['reg'].get(rname + suffix, ()):
                        queue.append(('reg', target_fn, depth + 1))
            for cname in fn.get('raw_calls', ()):
                if len(cname) < 4:
                    continue
                for target_fn in helper_graph[cur_dom].get(cname, ()):
                    queue.append((cur_dom, target_fn, depth + 1))
        return found

    # 2) Parse public interface files in include/basic_api and include/simt_api/cpp
    decl_by_qname = defaultdict(list)
    for inc_root in (asc_root / 'include/basic_api', asc_root / 'include/simt_api/cpp'):
        if not inc_root.exists():
            continue
        for fp in sorted(inc_root.rglob('*.h')):
            rel = fp.relative_to(toolkit).as_posix()
            if '/op_frame/' in rel or 'kernel_struct_' in fp.name or 'kernel_tensor' in fp.name or 'kernel_tpipe' in fp.name or 'kernel_type' in fp.name or 'kernel_base_types' in fp.name or 'utils' in fp.name:
                continue
            files_meta[rel] = {'path': rel, 'sha256': sha256(fp)}
            text = fp.read_text(errors='replace')
            is_reg_ns = '/reg_compute/' in rel
            is_simt_ns = '/simt_api/cpp/' in rel
            ns = 'AscendC::Reg' if is_reg_ns else 'AscendC::Simt' if is_simt_ns else 'AscendC'
            for fn in parse_functions_in_header(text, rel, known_ccec):
                if fn['name'].startswith(('Check', 'Validate', '__', 'GetDivSpecificMode')):
                    continue
                qname = f'{ns}::{fn["name"]}'
                decl_by_qname[qname].append((ns, fn))

    items = []
    for qname in sorted(decl_by_qname):
        entries = decl_by_qname[qname]
        ns, sample = entries[0]
        name = sample['name']
        rel_file = sample['source']['file']
        stem = Path(rel_file).name.replace('_intf.h', '')

        # Match corresponding dav_3510 implementation functions (e.g. Add -> AddImpl, Mmad -> MmadCal, DataCopy -> CopyGmToUbufAlignV2 / DataCopyGM2L1Impl)
        is_reg_ns = ns == 'AscendC::Reg'
        def prefer_impl(fn_list):
            if is_reg_ns:
                return [x for x in fn_list if '/reg_compute/' in x['source']['file']]
            return [x for x in fn_list if '/reg_compute/' not in x['source']['file']]

        matched_impls = prefer_impl(list(impl_3510_funcs.get(name, [])) + list(impl_3510_funcs.get(name + 'Impl', [])) + list(impl_3510_funcs.get(name + 'Cal', [])))
        if not matched_impls:
            for cand in prefer_impl(impl_3510_by_stem.get(stem, [])):
                if cand['name'].lower().startswith(name.lower()):
                    matched_impls.append(cand)
        if not matched_impls and stem == 'kernel_operator_data_copy' and name.startswith('DataCopy'):
            matched_impls = [cand for cand in prefer_impl(impl_3510_by_stem.get(stem, [])) if any(k in cand['name'] for k in ('CopyGmTo', 'CopyUbufTo', 'CopyCbufTo', 'DataCopy'))][:12]
        if not matched_impls and stem == 'kernel_operator_mm' and name.startswith('Mmad'):
            matched_impls = [cand for cand in prefer_impl(impl_3510_by_stem.get(stem, [])) if 'Mmad' in cand['name'] or 'Mad' in cand['name']][:12]

        cond_vals = [eval_3510(fn['conditions']) for _, fn in entries]
        if 'matches' in cond_vals or matched_impls:
            cond_3510 = 'matches'
        elif all(v == 'excluded' for v in cond_vals):
            cond_3510 = 'excluded'
        else:
            cond_3510 = 'unknown'

        group = (
            'AscendC::Reg (寄存器编程接口)' if ns == 'AscendC::Reg'
            else 'AscendC::Simt (SIMT 线程编程接口)' if ns == 'AscendC::Simt'
            else 'AscendC Basic API (LocalTensor 接口)'
        )
        family, transfer = classify_ascendc_family(name, rel_file, sample['signature'])

        domain = 'reg' if is_reg_ns else 'basic'
        callee_set = resolve_transitive_callees(matched_impls + [f for _, f in entries], domain)
        callee_names = sorted(callee_set)
        callee_details = [ccec_index[c] for c in callee_names if c in ccec_index]
        ccec_op_ids = sorted({oid for cd in callee_details for oid in cd['op_ids']})
        core_guards = sorted({cg for fn in matched_impls for cg in fn['core_guards']})

        forms = []
        seen_sigs = set()
        for _, fn in entries:
            if fn['signature'] in seen_sigs:
                continue
            seen_sigs.add(fn['signature'])
            forms.append({
                'signature': fn['signature'],
                'template': fn['template'],
                'return_type': fn['return_type'],
                'parameters': fn['parameters'],
                'source': fn['source'],
            })

        rep_impl = matched_impls[0] if matched_impls else sample
        items.append({
            'id': f'ascendc_basic_{ns.lower().replace("::", "_")}_{name}',
            'layer': 'basic',
            'name': name,
            'qualified_name': qname,
            'namespace': ns,
            'group': group,
            'family': family,
            'transfer': transfer,
            'condition_3510': cond_3510,
            'core_guards': core_guards,
            'overload_count': len(forms),
            'impl_3510_functions': [
                {'name': im['name'], 'signature': im['signature'], 'source': im['source']}
                for im in matched_impls[:10]
            ],
            'forms': forms[:24],
            'ccec_callees': callee_details,
            'ccec_op_ids': ccec_op_ids[:16],
            'source': sample['source'],
            'impl_source': rep_impl['source'] if matched_impls else None,
            'excerpt': rep_impl['excerpt'],
        })
    return items


def extract(toolkit: Path = DEFAULT_TOOLKIT) -> dict:
    toolkit = toolkit.resolve()
    version_info = (toolkit / 'share/info/bisheng-compiler/version.info').read_text()
    if 'Version=9.3.0\n' not in version_info or 'timestamp=20261104_' not in version_info:
        raise ValueError('Toolkit version differs from pinned 9.3.0~weekly.20261104.01')

    db = Database()
    ops_model = Ops(db).model
    ccec_index = build_ccec_callee_index(db, ops_model)
    files_meta = {}

    basic_items = extract_basic_layer(toolkit, ccec_index, files_meta)
    capi_items = extract_capi_layer(toolkit, ccec_index, files_meta)

    payload = {
        'schema_version': SCHEMA_VERSION,
        'backend': 'ascendc',
        'version': VERSION,
        'target': {
            'chip': 'Ascend950PR_9579',
            'architecture': '__NPU_ARCH__=3510',
            'impl_directory': 'dav_3510 / reg_base_impl',
        },
        'counts': {
            'basic_api_total': len(basic_items),
            'basic_api_by_condition_3510': dict(Counter(x['condition_3510'] for x in basic_items)),
            'capi_total': len(capi_items),
            'capi_by_condition_3510': dict(Counter(x['condition_3510'] for x in capi_items)),
            'capi_by_group': dict(Counter(x['group'] for x in capi_items)),
            'scanned_files': len(files_meta),
        },
        'limitations': LIMITATIONS,
        'files': files_meta,
        'basic_api': basic_items,
        'c_api': capi_items,
    }
    return payload


def validate_model(data: dict) -> list[str]:
    errors = []
    if data.get('schema_version') != SCHEMA_VERSION:
        errors.append('Invalid schema_version')
    basic_ids = {x['id'] for x in data.get('basic_api', [])}
    capi_ids = {x['id'] for x in data.get('c_api', [])}
    if len(basic_ids) != len(data.get('basic_api', [])):
        errors.append('Duplicate IDs in AscendC basic_api')
    if len(capi_ids) != len(data.get('c_api', [])):
        errors.append('Duplicate IDs in AscendC c_api')
    if len(basic_ids) < 100:
        errors.append(f'Too few AscendC basic_api records: {len(basic_ids)}')
    if len(capi_ids) < 500:
        errors.append(f'Too few AscendC c_api records: {len(capi_ids)}')
    return errors


def web_payload(data: dict | None = None) -> dict:
    if data is None:
        data = json.loads(OUTPUT.read_text())
    return {
        'schema_version': data['schema_version'],
        'version': data['version'],
        'target': data['target'],
        'counts': data['counts'],
        'limitations': data['limitations'],
        'files': data['files'],
        'basic_api': [
            {
                **x,
                'forms': x.get('forms', [])[:12],
                'excerpt': (x.get('excerpt') or '')[:900],
            }
            for x in data['basic_api']
        ],
        'c_api': [
            {
                **x,
                'forms': x.get('forms', [])[:12],
                'excerpt': (x.get('excerpt') or '')[:900],
            }
            for x in data['c_api']
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    ext = sub.add_parser('extract')
    ext.add_argument('--toolkit', type=Path, default=DEFAULT_TOOLKIT)
    ext.add_argument('--output', type=Path, default=OUTPUT)
    val = sub.add_parser('validate')
    val.add_argument('--input', type=Path, default=OUTPUT)
    args = parser.parse_args()

    if args.cmd == 'extract':
        data = extract(args.toolkit)
        errors = validate_model(data)
        if errors:
            raise ValueError('; '.join(errors))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        print(f'Extracted AscendC knowledge base to {args.output}: {data["counts"]}')
    elif args.cmd == 'validate':
        data = json.loads(args.input.read_text())
        errors = validate_model(data)
        if errors:
            raise SystemExit('Validation failed: ' + '; '.join(errors))
        print(f'Validated {args.input}: {data["counts"]}')


if __name__ == '__main__':
    main()
