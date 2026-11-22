#!/usr/bin/env python3
"""Extract and validate the two-layer CCE Dialect knowledge base (Dialect Ops & Dialect Intrinsics)."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess

from catalog import ROOT, VERSION
from ccec_transfer import transfer_for
from database import Database, stable_id

DEFAULT_REPO = Path('/home/zuomin/Projects/Compiler/CCEDialect')
OUTPUT = ROOT / 'data/cce_dialect/index.json'
SCHEMA_VERSION = 'ackb.cce-dialect.v1'

SCANNED_FILES = (
    'include/Dialect/CCE/IR/CCEBase.td',
    'include/Dialect/CCE/IR/CCEAttrs.td',
    'include/Dialect/CCE/IR/CCEEnums.td',
    'include/Dialect/CCE/IR/CCETypeConstraints.td',
    'include/Dialect/CCE/IR/CCEOps.td',
    'include/Dialect/CCE/IR/CCEIntrinsicOps.td',
    'include/Dialect/CCE/IR/CCESIMTOps.td',
    'include/Target/CCE/CCEHardwareConstants.h',
    'include/Target/CCE/CCETargetInfo.h',
    'include/Target/CCE/CCEIntrinsicMap.td',
    'include/Target/CCE/CCESIMTIntrinsicMap.td',
    'include/Utils/AddressSpaces.td',
    'cmake/GenerateCCEIntrinsicMap.cmake',
    'lib/Dialect/CCE/CCETranslate.cpp',
    'lib/Dialect/CCE/CCETranslateSIMT.cpp',
    'lib/Dialect/CCE/CCEBackendAdapt.cpp',
    'lib/Dialect/CCE/CCEPrintLibrary.cpp',
    'lib/Dialect/CCE/CCEDialect.cpp',
    'doc/CCESpec.md',
    'doc/DebugPrintUserGuide.md',
)

LIMITATIONS = [
    'CppNameRule enumerates possible translator spellings before verifier or backend checks. Global SIMT load/store widths come from IR; 8/16/32/64 are indexed, other widths are open.',
    'Static extraction from CCEDialect TableGen (.td), translation passes (.cpp) and specification docs (.md); no MLIR compilation or NPU execution was performed.',
    'Upper-layer memref operations (e.g. cce.mad, cce.vgatherb) require upstream conversion to cce.intr.* before standalone cce-translate --cce-to-backend.',
    'Target hardware constants in CCEDialect are fixed to dav-351x (UB 248KiB/256KiB, 256-byte vector registers, Ascend 950 / A5 class).',
    'Cross-links to CCEC __builtin_cce_* ops are heuristic/lexical correspondences across LLVM IR (llvm.hivm.*) and Clang builtins, not formal equivalence proofs.',
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_family(mnemonic: str, summary: str = '', op_class: str = '') -> tuple[str, dict | None]:
    low = mnemonic.lower()
    text = f'{low} {summary.lower()} {op_class.lower()}'
    transfer = dialect_transfer(low)
    if transfer or any(k in low for k in ('mov.', 'mov_', 'load.', 'load_', 'fix.', 'fix_', 'copy', 'nd2nz', 'dn2nz')):
        return '搬运 / DMA', transfer
    if any(k in low for k in ('mad', 'mmad', 'gemm', 'cbuf.matrix', 'create_cbuf_matrix')):
        return '矩阵 / Cube', None
    if low.startswith(('simt.', 'intr.simt.', 'simt_')) or 'simt' in op_class.lower():
        if 'atomic' in low or 'atom' in low:
            return '原子操作', None
        if 'sync' in low or 'bar' in low:
            return '同步 / 流水', None
        if 'ld' in low or 'st' in low:
            return '访存 / 布局', None
        return '计算 / 其他', None
    if any(k in low for k in ('atomic', 'atom')):
        return '原子操作', None
    if any(k in low for k in ('barrier', 'membar', 'mem.bar', 'set_flag', 'wait_flag', 'set.flag', 'wait.flag', 'get_buf', 'rls_buf', 'get.buf', 'rls.buf', 'intra_block')):
        return '同步 / 流水', None
    if any(k in low for k in ('vcvt', 'vtrc', 'cvt')):
        return '类型转换', None
    if any(k in low for k in ('vld', 'vst', 'vgather', 'vscatter', 'vsstb', 'vsldb', 'pld', 'pst', 'pload', 'pstore', 'vintlv', 'vdintlv', 'pintlv', 'pdintlv', 'vpack', 'vunpack', 'ppack', 'punpack', 'vsqz', 'vusqz', 'vslide', 'initalign')):
        return '访存 / 布局', None
    if any(k in low for k in ('set_', 'get_', 'set.', 'get.', 'spr', 'sbitset', 'fmatrix', 'l3d_rpt', 'padding', 'fpc', 'ctrl', 'channel_para', 'loop')):
        return '控制 / 寄存器', None
    return '计算 / 其他', None


def dialect_transfer(name: str) -> dict | None:
    n = name.lower().replace('.', '_')
    routes = [
        (('out_to_ub', 'gm_to_ub'), ('gm', 'ubuf', 'GM → UB')),
        (('ub_to_out', 'ub_to_gm'), ('ubuf', 'gm', 'UB → GM')),
        (('out_to_l1', 'gm_to_l1', 'gm_to_cbuf'), ('gm', 'cbuf', 'GM → L1')),
        (('l1_to_l0a', 'cbuf_to_ca'), ('cbuf', 'ca', 'L1 → L0A')),
        (('l1_to_l0b', 'cbuf_to_cb'), ('cbuf', 'cb', 'L1 → L0B')),
        (('l1_to_l0',), ('cbuf', 'ca', 'L1 → L0A')),
        (('l0c_to_out', 'cc_to_gm'), ('cc', 'gm', 'L0C → GM')),
        (('l0c_to_l1', 'cc_to_cbuf'), ('cc', 'cbuf', 'L0C → L1')),
        (('l0c_to_ub', 'cc_to_ub'), ('cc', 'ubuf', 'L0C → UB')),
        (('ub_to_l1', 'ubuf_to_cbuf'), ('ubuf', 'cbuf', 'UB → L1')),
        (('l1_to_ub', 'cbuf_to_ubuf'), ('cbuf', 'ubuf', 'L1 → UB')),
        (('ub_to_ub', 'ubuf_to_ubuf'), ('ubuf', 'ubuf', 'UB → UB')),
    ]
    for keys, (src, dst, label) in routes:
        if any(k in n for k in keys):
            return {
                'id': f'transfer:{src}:{dst}',
                'src': src,
                'dst': dst,
                'label': label,
                'search_alias': label.replace(' → ', '2').replace(' ', ''),
            }
    return transfer_for(n)


def parse_td_blocks(text: str) -> list[dict]:
    """Extract top-level class and def blocks with line numbers from a TableGen file."""
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^\s*(def|class)\s+([A-Za-z0-9_]+)\b', line)
        if not m:
            i += 1
            continue
        kind, name = m.groups()
        start = i + 1
        chunk = [line]
        in_code = '[{' in line and '}]' not in line
        clean_line = re.sub(r'\[\{.*?\}\]', '', line) if not in_code else line.split('[{')[0]
        brace = clean_line.count('{') - clean_line.count('}')
        seen_open_brace = '{' in clean_line
        while i + 1 < len(lines):
            stripped = chunk[-1].split('//')[0].rstrip()
            if not in_code:
                if seen_open_brace and brace <= 0:
                    break
                if not seen_open_brace and stripped.endswith(';'):
                    break
            i += 1
            nxt = lines[i]
            chunk.append(nxt)
            if in_code:
                if '}]' in nxt:
                    in_code = False
                    after = nxt.split('}]', 1)[1]
                    if '{' in after:
                        seen_open_brace = True
                    brace += after.count('{') - after.count('}')
            else:
                if '[{' in nxt and '}]' not in nxt:
                    in_code = True
                    before = nxt.split('[{', 1)[0]
                    if '{' in before:
                        seen_open_brace = True
                    brace += before.count('{') - before.count('}')
                else:
                    cleaned = re.sub(r'\[\{.*?\}\]', '', nxt)
                    if '{' in cleaned:
                        seen_open_brace = True
                    brace += cleaned.count('{') - cleaned.count('}')
        end = i + 1
        raw = '\n'.join(chunk)
        blocks.append({'kind': kind, 'name': name, 'start_line': start, 'end_line': end, 'raw': raw})
        i += 1
    return blocks


def extract_td_field(raw: str, field: str) -> str:
    m_code = re.search(rf'let\s+{field}\s*=\s*\[\{{(.*?)\}}\]\s*;', raw, re.S)
    if m_code:
        return m_code.group(1).strip()
    m_str = re.search(rf'let\s+{field}\s*=\s*((?:"[^"]*"\s*)+);', raw, re.S)
    if m_str:
        parts = re.findall(r'"([^"]*)"', m_str.group(1))
        return ''.join(parts).strip()
    m_paren = re.search(rf'let\s+{field}\s*=\s*\((.*?)\)\s*;', raw, re.S)
    if m_paren:
        return re.sub(r'\s+', ' ', m_paren.group(1)).strip()
    return ''


def resolve_op_mnemonic(def_name: str, base_cls: str, base_args: list[str], class_templates: dict[str, dict]) -> tuple[str, dict]:
    """Resolve full mnemonic (without cce. prefix) and inherited fields from TableGen class templates."""
    tmpl = class_templates.get(base_cls, {})
    arg0 = base_args[0] if base_args else ''
    arg1 = base_args[1] if len(base_args) > 1 else ''
    prefix_map = {
        'CCE_Op': arg0,
        'CCE_IntrOp': arg0,
        'CCE_SetParamOp': arg0,
        'CCE_AtomicConfigOp': arg0,
        'CCE_LoadL1ToMx2Dv2Op': arg0,
        'UnaryVector': arg0,
        'BinaryVector': arg0,
        'BinaryVectorShift': arg0,
        'BinaryVectorShiftByVector': arg0,
        'BinaryVectorMull': arg0,
        'VecScalarOp': arg0,
        'CCE_CarryBinaryOp': arg0,
        'CCE_CarryBinaryWithInputOp': arg0,
        'ReductionOp': arg0,
        'ReductionCbOp': arg0,
        'CCE_PintlvOp': f'pintlv.{arg0}',
        'CCE_PDintlvOp': f'pdintlv.{arg0}',
        'CCE_PLoadOp': f'plds.{arg0}',
        'CCE_PStoreOp': f'psts.{arg0}',
        'CCE_SIMTInfoOp': f'simt.{arg0}',
        'CCE_SIMTShflOp': f'simt.shfl.{arg0}',
        'CCE_SIMTUnaryMathOp': f'simt.{arg0}',
        'CCE_IntrMadOp': f'intr.mad.{arg0}',
        'CCE_IntrMovOutToL1Nd2nzOp': f'intr.mov.out.to.l1.multi.nd2nz.{arg0}.v310',
        'CCE_IntrCreateCbufMatrixOp': f'intr.create.cbuf.matrix.{arg0}',
        'CCE_IntrFixpipeOp': f'intr.fix.l0c.{arg0}.ext',
        'CCE_IntrLoadL1ToL0A2Dv2Op': f'intr.load.l1.to.l0a.2dv2.{arg0}',
        'CCE_IntrLoadL1ToL0B2Dv2Op': f'intr.load.l1.to.l0b.2dv2.{arg0}',
        'CCE_IntrLoadL1ToL0A3Dv2Op': f'intr.load.l1.to.l0a.3dv2.{arg0}',
        'CCE_IntrLoadL1ToL0B3Dv2Op': f'intr.load.l1.to.l0b.3dv2.{arg0}',
        'CCE_IntrVLdsX1Op': f'intr.vldsx1.{arg0}',
        'CCE_IntrVStsX1Op': f'intr.vstsx1.{arg0}',
        'CCE_IntrVSstbOp': f'intr.vsstb.{arg0}',
        'CCE_IntrVSldbOp': f'intr.vsldb.{arg0}',
        'CCE_IntrVGather2Op': f'intr.vgather2.{arg0}',
        'CCE_IntrVBitSortOp': f'intr.vbitsort.{arg0}',
        'CCE_IntrVMrgSort4Op': f'intr.vmrgsort4.{arg0}',
        'CCE_IntrVGatherBOp': f'intr.vgatherb.{arg0}',
        'CCE_IntrMovOutToL1AlignV2DvOp': f'intr.mov.out.to.l1.align.v2.{arg0}.dv',
        'CCE_IntrMadMxOp': f'intr.mad.mx.{arg0}{arg1}',
        'CCE_IntrPstuOp': f'intr.pstu.{arg0}',
        'CCE_IntrVLdusOp': f'intr.vldus.{arg0}',
        'CCE_IntrMovOutToUbOp': f'intr.mov.out.to.ub.align.v2.{arg0}.dv',
    }
    mnemonic = prefix_map.get(base_cls, arg0 or def_name)
    return mnemonic, tmpl


SPEC_DEF_ALIASES = {
    'CCE_Vabs': 'CCE_AbsOp',
    'CCE_Vexp': 'CCE_ExpOp',
    'CCE_Vln': 'CCE_LnOp',
    'CCE_Vneg': 'CCE_NegOp',
    'CCE_Vnot': 'CCE_NotOp',
    'CCE_Vrelu': 'CCE_ReluOp',
    'CCE_Vsqrt': 'CCE_SqrtOp',
    'CCE_Vrsqrt': 'CCE_VRsqrtOp',
    'CCE_Vrec': 'CCE_VRecOp',
    'CCE_VAddS': 'CCE_VAddSOp',
    'CCE_VMulS': 'CCE_VMulSOp',
    'CCE_VDivFOp': 'CCE_VDivfOp',
    'CCE_VPreluOp': 'CCE_VPReluOp',
    'CCE_VMullOp': 'CCE_VmullOp',
    'CCE_PintlvB32Op': 'CCE_PintlvOp',
    'CCE_PintlvB16Op': 'CCE_PintlvOp',
    'CCE_PintlvB8Op': 'CCE_PintlvOp',
    'CCE_PDintlvB32Op': 'CCE_PDintlvOp',
    'CCE_PDintlvB16Op': 'CCE_PDintlvOp',
    'CCE_PDintlvB8Op': 'CCE_PDintlvOp',
    'CCE_VcvtffCastOp': 'CCE_VcvtffF16ToBF16Op',
    'CCE_VcvtfiCastOp': 'CCE_VcvtfiSameWidthOp',
    'CCE_VcvtifCastOp': 'CCE_VcvtifSameWidthOp',
    'CCE_LoadL1ToL0A3Dv2Op': 'CCE_LoadL1ToL03Dv2Op',
    'CCE_LoadL1ToL0B3Dv2Op': 'CCE_LoadL1ToL03Dv2Op',
    'CCE_LoadL1ToL0AMx2Dv2Op': 'CCE_LoadL1ToL0Mx2Dv2Op',
    'CCE_LoadL1ToL0BMx2Dv2Op': 'CCE_LoadL1ToL0Mx2Dv2Op',
    'CCE_SetAtomicF16Op': 'CCE_SetAtomicDtypeF16Op',
    'CCE_SetAtomicF32Op': 'CCE_SetAtomicDtypeF32Op',
    'CCE_SetAtomicS16Op': 'CCE_SetAtomicDtypeS16Op',
}


def parse_spec_doc(spec_path: Path, print_path: Path) -> dict[str, dict]:
    """Parse doc/CCESpec.md and doc/DebugPrintUserGuide.md keyed by Op def_name or mnemonic."""
    text = spec_path.read_text()
    sections = {}
    pattern = re.compile(r'(?:<a id="([^"]+)"></a>\s*)?###\s+(\d+)\.\s+(CCE_[A-Za-z0-9_]+)\s*—\s*([^\n]+)\n(.*?)(?=\n(?:<a id="[^"]+"></a>\s*)?###\s+\d+\.\s+CCE_|\Z)', re.S)
    for m in pattern.finditer(text):
        anchor, num, op_def, title_zh, body = m.groups()
        line = text.count('\n', 0, m.start()) + 1
        end_line = text.count('\n', 0, m.end()) + 1
        syntax_blocks = re.findall(r'```(?:mlir|text|c\+\+)?\n(.*?)```', body, re.S)
        sections[op_def] = {
            'section_number': int(num),
            'anchor': anchor or op_def.lower().replace('_', '-'),
            'op_def': op_def,
            'title_zh': title_zh.strip(),
            'body': body.strip(),
            'syntax_examples': [b.strip() for b in syntax_blocks if b.strip()],
            'source': {'file': 'doc/CCESpec.md', 'line': line, 'end_line': end_line},
        }
    if print_path.exists():
        ptext = print_path.read_text()
        if 'CCE_PrintOp' in sections:
            sections['CCE_PrintOp']['user_guide'] = {
                'file': 'doc/DebugPrintUserGuide.md',
                'summary': 'cce.print 调试打印完整使用指南（支持 GM/UB/L0C memref、vector、标量与专用降级 pass）',
                'excerpt': '\n'.join(ptext.splitlines()[:45]),
            }
    return sections


def parse_intrinsic_maps(repo: Path) -> list[dict]:
    """Parse all TableGen mapping defs in CCEIntrinsicMap.td and CCESIMTIntrinsicMap.td."""
    records = []
    for rel in ('include/Target/CCE/CCEIntrinsicMap.td', 'include/Target/CCE/CCESIMTIntrinsicMap.td'):
        path = repo / rel
        text = path.read_text()
        for blk in parse_td_blocks(text):
            if blk['kind'] != 'def':
                continue
            raw = blk['raw']
            m = re.search(r':\s*(CCE\w+Intrinsic)\s*<(.*?)>\s*;', raw, re.S)
            if not m:
                continue
            cls_name, arg_str = m.groups()
            tokens = [t.strip() for t in re.findall(r'"[^"]*"|-?\d+', arg_str)]
            vals = [t[1:-1] if t.startswith('"') else int(t) for t in tokens]
            entry = {
                'def_name': blk['name'],
                'mapping_class': cls_name,
                'source': {'file': rel, 'line': blk['start_line'], 'end_line': blk['end_line']},
                'raw': raw,
            }
            if cls_name == 'CCEVectorIntrinsic' and len(vals) >= 8:
                entry.update({
                    'op_key': vals[0],
                    'operand_count': vals[1],
                    'result_count': vals[2],
                    'lanes': vals[3],
                    'element_type': vals[4],
                    'signedness': vals[5],
                    'merge_mode': vals[6],
                    'llvm_intrinsic': vals[7],
                })
            elif cls_name in ('CCENameMappedIntrinsic', 'CCESIMTNameMappedIntrinsic') and len(vals) >= 4:
                entry.update({
                    'op_key': vals[0],
                    'operand_count': vals[1],
                    'result_count': vals[2],
                    'llvm_intrinsic': vals[3],
                })
            elif cls_name == 'CCEEnumIntrinsic' and len(vals) >= 4:
                entry.update({
                    'op_key': vals[0],
                    'operand_count': vals[1],
                    'result_count': vals[2],
                    'llvm_intrinsic': vals[3],
                    'enum_attrs': vals[4] if len(vals) > 4 else '',
                })
            elif cls_name == 'CCEPredIntrinsic' and len(vals) >= 5:
                entry.update({
                    'op_key': vals[0],
                    'operand_count': vals[1],
                    'result_count': vals[2],
                    'mask_bitwidth': vals[3],
                    'llvm_intrinsic': vals[4],
                })
            elif cls_name == 'CCEMembarIntrinsic' and len(vals) >= 2:
                entry.update({
                    'op_key': 'membar',
                    'barrier_kind': vals[0],
                    'operand_count': 0,
                    'result_count': 0,
                    'llvm_intrinsic': vals[1],
                })
            elif cls_name == 'CCEVcvtIntrinsic' and len(vals) >= 10:
                entry.update({
                    'op_key': vals[0],
                    'operand_count': vals[1],
                    'result_count': vals[2],
                    'src_lanes': vals[3],
                    'src_element_type': vals[4],
                    'res_lanes': vals[5],
                    'res_element_type': vals[6],
                    'signedness': vals[7],
                    'llvm_intrinsic': vals[8],
                    'variant': vals[9],
                    'operand_mask': vals[10] if len(vals) > 10 else 0,
                })
            elif cls_name == 'CCESIMTDtypeIntrinsic' and len(vals) >= 3:
                entry.update({
                    'op_key': vals[0],
                    'element_type': vals[1],
                    'llvm_intrinsic': vals[2],
                })
            elif cls_name == 'CCESIMTReduceIntrinsic' and len(vals) >= 3:
                entry.update({
                    'op_key': f'simt.reduce.{vals[0]}',
                    'reduce_kind': vals[0],
                    'element_type': vals[1],
                    'llvm_intrinsic': vals[2],
                })
            if 'llvm_intrinsic' in entry:
                records.append(entry)
    return records


def normalize_op_key_to_mnemonic(op_key: str) -> list[str]:
    """Map an op_key from CCEIntrinsicMap.td back to upper-layer CCE Dialect Op mnemonics."""
    if op_key.startswith(('cmp.', 'cmps.')):
        return [op_key.split('.')[0]]
    if op_key in ('dhistv2', 'chistv2'):
        return ['histv2']
    if op_key.startswith('simt.reduce.'):
        return ['simt.reduce']
    if op_key.startswith('intr.'):
        # Map cce.intr.* back to its memref user-facing op in CCEOps.td
        intr = op_key.removeprefix('intr.')
        if intr.startswith('mad.mx.'):
            return ['mad.mx']
        if intr.startswith('mad.'):
            return ['mad']
        if intr.startswith('mov.out.to.l1.multi.nd2nz.'):
            return ['mov.out.to.l1.multi.nd2nz']
        if intr.startswith('mov.out.to.l1.align.v2.'):
            return ['mov.out.to.l1.align.v2.dv']
        if intr.startswith('mov.out.to.ub.align.v2.'):
            return ['mov.out.to.ub.align.v2.dv']
        if intr.startswith('create.cbuf.matrix.'):
            return ['create.cbuf.matrix']
        if intr.startswith('fix.l0c.to.ub.'):
            return ['fix.l0c.to.ub']
        if intr.startswith('fix.l0c.to.l1.'):
            return ['fix.l0c.to.l1']
        if intr.startswith('fix.l0c.to.out.'):
            return ['fix.l0c.to.out']
        if intr.startswith('load.l1.to.l0a.2dv2.'):
            return ['load.l1.to.l0a.2dv2']
        if intr.startswith('load.l1.to.l0b.2dv2.'):
            return ['load.l1.to.l0b.2dv2']
        if intr.startswith(('load.l1.to.l0a.3dv2.', 'load.l1.to.l0b.3dv2.')):
            return ['load.l1.to.l0.3dv2']
        if intr.startswith('load.l1.to.l0a.mx.2dv2'):
            return ['load.l1.to.l0a.mx.2dv2']
        if intr.startswith('load.l1.to.l0b.mx.2dv2'):
            return ['load.l1.to.l0b.mx.2dv2']
        for prefix in ('vldsx1', 'vstsx1', 'vsstb', 'vsldb', 'vgather2', 'vbitsort', 'vmrgsort4', 'vgatherb', 'pstu', 'vldus'):
            if intr.startswith(prefix + '.'):
                return [prefix]
        return [intr]
    return [op_key]


def match_ccec_ops(llvm_intrinsic: str, ccec_ops_by_short: dict[str, list[str]]) -> list[str]:
    """Find lexical candidates only; spelling normalization does not prove lowering equivalence."""
    stem = llvm_intrinsic.removeprefix('llvm.hivm.').lower().replace('.', '_')
    candidates = set()
    if stem in ccec_ops_by_short:
        candidates.update(ccec_ops_by_short[stem])
    # Try stripping trailing merge mode (_x, _z, _m) or swapping order (e.g. vadd_x_v128f16 -> vadd_v128f16_x)
    m = re.match(r'^([a-z0-9_]+)_([xzm])_(v\d+[a-z0-9]+)$', stem)
    if m:
        alt = f'{m.group(1)}_{m.group(3)}_{m.group(2)}'
        if alt in ccec_ops_by_short:
            candidates.update(ccec_ops_by_short[alt])
        base = f'{m.group(1)}_{m.group(3)}'
        if base in ccec_ops_by_short:
            candidates.update(ccec_ops_by_short[base])
        if m.group(1) in ccec_ops_by_short:
            candidates.update(ccec_ops_by_short[m.group(1)])
    # Normalize HIVM DMA/Cube naming conventions to CCEC builtin naming conventions
    norm = stem
    for src_tok, dst_tok in (
        ('mov_out_to_ub', 'copy_gm_to_ubuf'),
        ('mov_ub_to_out', 'copy_ubuf_to_gm'),
        ('mov_out_to_l1', 'copy_gm_to_cbuf'),
        ('mov_l1_to_ub', 'copy_cbuf_to_ubuf'),
        ('mov_ub_to_l1', 'copy_ubuf_to_cbuf'),
        ('mov_ub_to_ub', 'copy_ubuf_to_ubuf'),
        ('load_l1_to_l0a', 'load_cbuf_to_ca'),
        ('load_l1_to_l0b', 'load_cbuf_to_cb'),
        ('fix_l0c_to_out', 'copy_matrix_cc_to_gm'),
        ('fix_l0c_to_l1', 'copy_matrix_cc_to_cbuf'),
        ('fix_l0c_to_ub', 'copy_matrix_cc_to_ubuf'),
        ('mmad_mx', 'mad_mx'),
    ):
        norm = norm.replace(src_tok, dst_tok)
    norm_clean = re.sub(
        r'(?:_(?:f322f16|f322bf16|f162f32|bf162f32|s322f16|f32|f16|bf16|s32|u32|s16|u16|s8|u8|s4|e4m3|e5m2|e2m1x2|e1m2x2|dv|v310|c310|l300|ext|cfg|no_dual|ori|h|v|x|z|m))+$',
        '',
        norm,
    )
    for probe in (norm, norm_clean):
        if probe in ccec_ops_by_short:
            candidates.update(ccec_ops_by_short[probe])
    # Also handle exact base match for e.g. mad_bf162f32_c310 -> mad, pipe_barrier -> pipe_barrier
    base0 = norm.split('_')[0]
    if not candidates and base0 in ccec_ops_by_short and len(ccec_ops_by_short[base0]) <= 4:
        candidates.update(ccec_ops_by_short[base0])
    return sorted(candidates)


def cpp_mappings(repo, files_meta):
    """Enumerate name-building branches of the pinned translator, before verifier checks."""
    from itertools import product

    fp = ('f32', 'bf16', 'f16', 'f8e4m3', 'f8e5m2')
    atom = ('ADD', 'SUB', 'AND', 'OR', 'XOR', 'INC', 'DEC', 'MIN', 'MAX', 'EXCH')
    floats = ('fp32', 'fp64', 'fp16', 'bf16')
    integers = [s + w for s, w in product('su', ('8', '16', '32', '64'))]
    # Load/store additionally accepts widths supplied by the input IR. Enumerate
    # common scalar widths and preserve the open rule separately in limitations.
    widths = ('8', '16', '32', '64')
    cache = ('cache', 'uncache')
    rules = {
        241: ('simt.reduce', 'redux.{}.{}32', [('add', 'max', 'min'), 'su']),
        306: ('simt.cast', '{}x2.to.{}x2', [fp, fp]),
        458: ('simt.atomic_rmw', 'atom.{}.{}.{}', [atom, 'GS', [*floats, 'f16x2', 'bf16x2', *integers]]),
        517: ('simt.atomic_cas', 'atom.CAS.{}.{}', ['GS', [*floats, 's32', 's64']]),
        688: ('simt.load', 'ldg.{}.s{}', [cache, widths]),
        690: ('simt.store', 'stg.{}.b{}', [cache, widths]),
        852: ('simt.vote', 'vote.{}', [('all', 'any', 'uni', 'ballot')]),
        886: ('simt.mulhi', 'mulhi_{}', [('i', 'ui')]),
        888: ('simt.mul_i32toi64', 'mul_i32toi64_{}', [('i', 'ui')]),
    }
    simt = 'lib/Dialect/CCE/CCETranslateSIMT.cpp'
    if files_meta[simt]['sha256'] != 'ab8cce489b57ce8dce37748c42dc68055f1a08b29d38b6c2c200327ab0e6bcff':
        raise ValueError('Review SIMT name-building rules for the changed translator')
    literal_keys = {'GET.BLOCK.IDX': 'get_block_idx', 'DCCI_DST_CONTEXT': 'simt.dcci',
                    'DCCI': 'simt.dcci', 'ffma_f32_rrr': 'simt.ffma', 'mul64hi_ui': 'simt.mul64hi'}
    for path in sorted(files_meta):
        if not path.endswith('.cpp'):
            continue
        for number, raw in enumerate((repo / path).read_text().splitlines(), 1):
            line = raw.partition('//')[0]
            values = []
            if path == simt and number in rules:
                key, template, parts = rules[number]
                values = [('llvm.hivm.' + template.format(*v), key, 'CppNameRule') for v in product(*parts)]
            elif '"llvm.hivm.' in line:
                for suffix in re.findall(r'"llvm\.hivm\.([A-Za-z0-9_.]+)"', line):
                    if suffix.startswith(('SET.', 'WAIT.')):
                        key = suffix.lower() if not suffix.endswith(('.IMM', '.REG')) or 'FLAG.DEV' in suffix else suffix.split('.')[0].lower() + '_flag'
                    elif suffix in ('isgm', 'isub', 'islocal'):
                        key = 'simt.query_ptr'
                    elif suffix.startswith('fence'):
                        key = 'simt.fence'
                    else:
                        if suffix.startswith('vcvtff.') and path.endswith('CCEBackendAdapt.cpp'):
                            key = 'vcvtff'
                        else:
                            key = literal_keys[suffix]
                    values.append(('llvm.hivm.' + suffix, key, 'CppLiteral'))
            elif 'call ' in line and '@llvm.hivm.' in line:
                values = [(name, 'print', 'EmbeddedIRCall') for name in re.findall(r'@(llvm\.hivm\.[\w.]+)\(', line)]
            for name, key, kind in values:
                extra = {}
                if kind == 'CppNameRule' and key in ('simt.load', 'simt.store', 'simt.atomic_rmw', 'simt.atomic_cas'):
                    extra['intr_op_key'] = 'intr.' + key
                if key in ('simt.load', 'simt.store'):
                    extra['name_pattern'] = ('llvm.hivm.ldg.{cache|uncache}.s<N>' if key == 'simt.load'
                                             else 'llvm.hivm.stg.{cache|uncache}.b<N>')
                restriction = ''
                if key in ('simt.atomic_rmw', 'simt.atomic_cas') and name.rsplit('.', 1)[-1] in (
                        's8', 'u8', 's16', 'u16', 'fp16', 'bf16'):
                    restriction = 'Semantic atomic op verifier rejects this scalar type'
                yield {**extra, 'op_key': key, 'llvm_intrinsic': name, 'mapping_class': kind, 'restriction': restriction,
                       'def_name': Path(path).name + ':' + str(number), 'raw': raw.strip(),
                       'source': {'file': path, 'line': number, 'end_line': number}}


def assess_paths(mappings, upper, lower):
    """Construct witnesses only for dispatch branches reviewed at the source pin."""
    paths = []
    cpp = 'lib/Dialect/CCE/CCETranslate.cpp'
    simt = 'lib/Dialect/CCE/CCETranslateSIMT.cpp'

    def add(op, status, witness, file, line):
        paths.append({'entry': op['mnemonic'] if op.get('op_key') else op['name'],
                      'status': status, 'condition': witness,
                      'definition': op['source'], 'dispatch': {'file': file, 'line': line}})

    for m in mappings:
        key, cls, name = m['op_key'], m['mapping_class'], m['llvm_intrinsic']
        suffix = name.rsplit('.', 1)[1]
        op = next(iter(upper.get(key, [])), None)
        if key in ('simt.atomic_rmw', 'simt.atomic_cas'):
            low = lower[m['intr_op_key']]
            if m['restriction']:
                add(op, 'rejected', '上层 verifier 拒绝该标量类型。', 'lib/Dialect/CCE/CCEDialect.cpp',
                    869 if key.endswith('rmw') else 902)
            else:
                add(op, 'rejected' if '.S.' in name else 'pending',
                    '当前翻译分支要求 LLVM 指针，memref 入口需先转换，低层原子入口仅接收 GM。', simt, 370)
            if '.S.' in name:
                add(low, 'rejected', 'LLVM_PointerGM 只接受地址空间 1，S 分支要求地址空间 6。', simt, m['source']['line'])
            else:
                _, kind, _, dtype = name.split('.')[-4:]
                add(low, 'confirmed', f'地址空间 1，{kind}，类型键 {dtype}，返回类型与值相同。', simt, m['source']['line'])
        elif cls == 'CppNameRule' and key in ('simt.load', 'simt.store'):
            add(lower[m['intr_op_key']], 'confirmed', '地址空间 1，标量 i' + suffix[1:] + '，' + name.split('.')[-2], simt, m['source']['line'])
        elif cls == 'CppNameRule' and key == 'simt.cast':
            # LLVM conversion of the vendor FP8 type needs a carrier path.
            status = 'pending' if 'f8e' in name else 'confirmed'
            add(op, status, name.removeprefix('llvm.hivm.').replace('.to.', ' → ') +
                ('，待追踪 FP8 的 LLVM 类型转换。' if status == 'pending' else ''), simt, 306)
        elif cls == 'CCESIMTDtypeIntrinsic' and op:
            add(op, 'confirmed', '源与结果同型 ' + m['element_type'] + ('，三个控制操作数 i32' if '.shfl.' in key else ''),
                simt, 77 if '.shfl.' in key else 181)
        elif cls in ('CCESIMTReduceIntrinsic', 'CppNameRule') and key.startswith('simt.reduce'):
            add(upper['simt.reduce'][0], 'confirmed', name.removeprefix('llvm.hivm.redux.'), simt, 241 if cls == 'CppNameRule' else 247)
        elif cls == 'CppNameRule' and op and key in ('simt.vote', 'simt.mulhi', 'simt.mul_i32toi64'):
            add(op, 'confirmed', name.removeprefix('llvm.hivm.'), simt, m['source']['line'])
        elif cls == 'CppLiteral' and op and key in ('simt.fence', 'simt.query_ptr', 'simt.ffma', 'simt.dcci', 'simt.mul64hi'):
            condition = {'isgm': 'kind=global', 'isub': 'kind=ubuf', 'islocal': 'kind=local',
                         'DCCI': '省略 dst_context', 'DCCI_DST_CONTEXT': '设置 dst_context',
                         'fence.workitems': 'scope=device', 'fenceblock.workitems': 'scope=block',
                         'ffma_f32_rrr': '三个 f32 操作数', 'mul64hi_ui': '两个 i64 操作数'}
            add(op, 'confirmed', condition[name.removeprefix('llvm.hivm.')], simt, m['source']['line'])
        elif cls in ('CCENameMappedIntrinsic', 'CCESIMTNameMappedIntrinsic'):
            entry = lower.get(key) or op
            if not entry or entry.get('has_verifier') or key in ('intr.simt.print', 'intr.print'):
                continue
            args = re.findall(r'(\w+):\$\w+', entry['arguments'])
            results = re.findall(r'(\w+):\$\w+', entry['results'])
            if entry['op_class'] == 'CCE_SIMTInfoOp':
                results = ['I64' if key == 'simt.clock64' else 'I32']
            witness_types = {'CCE_PredVecType': 'vector<256xi1>', 'CCE_AlignVecType': 'vector<32xi8>'}
            if key in lower:
                vector = re.search(r'\.v(\d+)(bf16|f16|f32|[siu]\d+)$', name)
                if entry['op_class'] == 'CCE_IntrCreateCbufMatrixOp':
                    witness_types['valueType'] = 'I64' if key.endswith('f32') else 'bf16' if '.bf16.' in key else 'f16'
                if vector:
                    lanes, dtype = vector.groups()
                    dtype = re.sub(r'^[su]', 'i', dtype)
                    witness_types['AnyType'] = f'vector<{lanes}x{dtype}>'
                    witness_types['CCE_MemVecElemVecType'] = witness_types['AnyType']
                elif key in ('intr.vstus', 'intr.vstur'):
                    witness_types['CCE_MemVecElemVecType'] = 'vector<256xi8>'
                # A predicate operand uses the predicate register type even if
                # the raw-pointer ODS entry accepts AnyType for that operand.
                args = [witness_types['CCE_PredVecType'] if arg == 'AnyType' and role in ('mask', 'preg') else arg
                        for arg, role in re.findall(r'(\w+):\$(\w+)', entry['arguments'])]
            fixed = r'LLVM_(?:AnyPointer|Pointer(?:UB|GM|L1|L0[ABC]))|I(?:1|8|16|32|64)'
            if (all(re.fullmatch(fixed, t) or t in witness_types or t in witness_types.values() for t in args + results)
                    and len(args) == m['operand_count'] and len(results) == m['result_count']):
                types = [witness_types.get(t, t) for t in args + results]
                add(entry, 'confirmed', '(' + ', '.join(types[:len(args)]) + ') → ' +
                    (', '.join(types[len(args):]) or 'void'), cpp, 977)
        elif cls == 'CCEPredIntrinsic' and op and m['mask_bitwidth'] in (8, 16, 32):
            add(op, 'confirmed', f"mask_bitwidth={m['mask_bitwidth']}；谓词取同型，pset 的 pat 可取 0。", cpp, 615)
        elif cls == 'CCEMembarIntrinsic' and m['barrier_kind'] == 0:
            add(op, 'confirmed', 'i32 函数参数，翻译器选择默认 barrierKind=0。', cpp, 1612)
        elif cls == 'CCEVectorIntrinsic' and key.startswith(('cmp.', 'cmps.')):
            base, predicate = key.split('.')
            sign = 'u' if predicate in ('ule', 'uge', 'ult', 'ugt') else 's'
            if (m['signedness'], m['merge_mode'], m['operand_count'], m['result_count']) == (sign, 'z', 3, 1):
                add(upper[base][0], 'confirmed', f"vector<{m['lanes']}x{m['element_type']}>，predicate={predicate}，结果为谓词向量",
                    cpp, 1142 if base == 'cmp' else 1185)
        elif cls == 'CCEVectorIntrinsic' and op and not op['has_verifier'] and op['op_class'] in (
                'UnaryVector', 'BinaryVector', 'BinaryVectorShift', 'BinaryVectorShiftByVector', 'VecScalarOp', 'ReductionOp'):
            if key == 'vmuls' and m['element_type'] == 'bf16':
                add(op, 'rejected', 'bf16 分支调用 vdups 和 vmul。', cpp, 757)
                continue
            if key in ('vrec', 'vrsqrt'):
                add(op, 'rejected', '翻译器将该操作分解为 vbr、vdiv 及可选 vsqrt。', cpp, 688)
                continue
            if key in ('vand', 'vor', 'vxor') and m['signedness'] != 's':
                add(op, 'rejected', '翻译器固定使用 s 查表。', cpp, 809)
                continue
            dtype = m['element_type']
            if ('Shift' in op['op_class'] and dtype not in ('i8', 'i16', 'i32')
                    or m['result_count'] != 1 or m['operand_count'] != (2 if op['op_class'] in ('UnaryVector', 'ReductionOp') else 3)):
                continue
            add(op, 'confirmed', f"vector<{m['lanes']}x{dtype}>，mode=[{m['merge_mode']}]，signedness={m['signedness']}", cpp, 825)
        elif key == 'barrier' and cls == 'CCEEnumIntrinsic':
            add(op, 'confirmed', 'pipe 属性选择 PIPE_V', cpp, 998)
    states = {p['status'] for p in paths}
    status = 'confirmed' if 'confirmed' in states else 'rejected' if states == {'rejected'} else 'pending'
    return {'path_status': status, 'entry_paths': paths}


def extract(repo: Path = DEFAULT_REPO) -> dict:
    repo = repo.resolve()
    if not repo.exists():
        raise ValueError(f'CCEDialect repository not found at {repo}')
    head_commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    files_meta = {}
    for rel in SCANNED_FILES:
        fp = repo / rel
        if not fp.exists():
            raise ValueError(f'Missing expected CCEDialect file: {rel}')
        files_meta[rel] = {'path': rel, 'sha256': sha256(fp), 'bytes': fp.stat().st_size}

    # The witness rules depend on verifier bodies, ODS constraints and dispatch order.
    reviewed = '5639e581ef516650412b3f06104f27a3e7c661b5'
    if head_commit != reviewed or subprocess.run(
            ['git', '-C', str(repo), 'diff', '--quiet', reviewed, '--', 'include', 'lib', 'cmake']).returncode:
        raise ValueError('Review dialect reachability rules against the changed source tree')

    spec_sections = parse_spec_doc(repo / 'doc/CCESpec.md', repo / 'doc/DebugPrintUserGuide.md')

    # Collect class templates across the 3 Op .td files
    class_templates = {}
    for rel in ('include/Dialect/CCE/IR/CCEOps.td', 'include/Dialect/CCE/IR/CCEIntrinsicOps.td', 'include/Dialect/CCE/IR/CCESIMTOps.td'):
        text = (repo / rel).read_text()
        for blk in parse_td_blocks(text):
            if blk['kind'] == 'class':
                class_templates[blk['name']] = {
                    'summary': extract_td_field(blk['raw'], 'summary'),
                    'description': extract_td_field(blk['raw'], 'description'),
                    'arguments': extract_td_field(blk['raw'], 'arguments'),
                    'results': extract_td_field(blk['raw'], 'results'),
                    'assembly_format': extract_td_field(blk['raw'], 'assemblyFormat'),
                }

    # Parse upper-layer Ops (CCEOps.td + CCESIMTOps.td)
    upper_ops = []
    upper_by_mnemonic = {}
    seen_op_ids = set()
    for rel, domain in (('include/Dialect/CCE/IR/CCEOps.td', 'CCE Semantic Ops'),
                        ('include/Dialect/CCE/IR/CCESIMTOps.td', 'CCE SIMT Ops')):
        text = (repo / rel).read_text()
        for blk in parse_td_blocks(text):
            if blk['kind'] != 'def':
                continue
            raw = blk['raw']
            m_inh = re.search(r'def\s+\w+\s*:\s*([A-Za-z0-9_]+)\s*(?:<\s*(.*?)\s*>)?\s*(?:\{|;)', raw, re.S)
            if not m_inh:
                continue
            base_cls, arg_str = m_inh.group(1), m_inh.group(2) or ''
            if base_cls in ('Type', 'AnyTypeOf'):
                continue
            base_args = re.findall(r'"([^"]*)"', arg_str)
            mnemonic, tmpl = resolve_op_mnemonic(blk['name'], base_cls, base_args, class_templates)
            full_name = f'cce.{mnemonic}'
            summary = extract_td_field(raw, 'summary') or tmpl.get('summary', '')
            description = extract_td_field(raw, 'description') or tmpl.get('description', '')
            arguments = extract_td_field(raw, 'arguments') or tmpl.get('arguments', '')
            results = extract_td_field(raw, 'results') or tmpl.get('results', '')
            assembly = extract_td_field(raw, 'assemblyFormat') or tmpl.get('assembly_format', '')
            regions = extract_td_field(raw, 'regions')
            family, transfer = classify_family(mnemonic, summary, base_cls)
            spec_key = blk['name'] if blk['name'] in spec_sections else SPEC_DEF_ALIASES.get(blk['name'], blk['name'])
            spec = spec_sections.get(spec_key)
            uses_memref = 'MemRef' in arguments or 'MemRef' in results
            if regions:
                lowering_mode = 'scope_or_region'
            elif uses_memref and not mnemonic.startswith('simt.'):
                lowering_mode = 'lowers_to_cce_intr'
            elif mnemonic.startswith('simt.'):
                lowering_mode = 'simt_translation'
            elif mnemonic == 'print':
                lowering_mode = 'lowers_to_cce_intr'
            else:
                lowering_mode = 'direct_to_llvm_ir'

            op_id = f'cce_dialect_op_{mnemonic.replace(".", "_")}'
            # Disambiguate if two defs share the same mnemonic (e.g. set_loop3_para)
            if op_id in seen_op_ids:
                op_id = f'cce_dialect_op_{blk["name"].lower()}'
            seen_op_ids.add(op_id)
            record = {
                'id': op_id,
                'name': full_name,
                'mnemonic': mnemonic,
                'def_name': blk['name'],
                'op_class': base_cls,
                'group': domain,
                'family': family,
                'transfer': transfer,
                'summary': summary or (spec['title_zh'] if spec else ''),
                'description': description,
                'arguments': arguments,
                'results': results,
                'regions': regions,
                'assembly_format': assembly,
                'has_verifier': 'hasVerifier = 1' in raw,
                'lowering_mode': lowering_mode,
                'lowering_mode_basis': 'type_and_name_heuristic',
                'relation_resolution': 'lexical_name_candidate',
                'spec': spec,
                'intrinsic_ids': [],
                'ccec_candidate_op_ids': [],
                'source': {
                    'file': rel,
                    'line': blk['start_line'],
                    'end_line': blk['end_line'],
                    'sha256': files_meta[rel]['sha256'],
                },
                'excerpt': raw,
            }
            upper_ops.append(record)
            upper_by_mnemonic.setdefault(mnemonic, []).append(record)

    # Parse explicit MLIR intrinsic ops in CCEIntrinsicOps.td
    mlir_intr_ops = {}
    intr_rel = 'include/Dialect/CCE/IR/CCEIntrinsicOps.td'
    intr_text = (repo / intr_rel).read_text()
    for blk in parse_td_blocks(intr_text):
        if blk['kind'] != 'def':
            continue
        raw = blk['raw']
        m_inh = re.search(r'def\s+\w+\s*:\s*([A-Za-z0-9_]+)\s*(?:<\s*(.*?)\s*>)?\s*(?:\{|;)', raw, re.S)
        if not m_inh:
            continue
        base_cls, arg_str = m_inh.group(1), m_inh.group(2) or ''
        if base_cls in ('Type', 'AnyTypeOf'):
            continue
        base_args = re.findall(r'"([^"]*)"', arg_str)
        mnemonic, tmpl = resolve_op_mnemonic(blk['name'], base_cls, base_args, class_templates)
        mlir_intr_ops[mnemonic] = {
            'def_name': blk['name'],
            'mnemonic': f'cce.{mnemonic}',
            'op_key': mnemonic,
            'op_class': base_cls,
            'summary': extract_td_field(raw, 'summary') or tmpl.get('summary', ''),
            'description': extract_td_field(raw, 'description') or tmpl.get('description', ''),
            'arguments': extract_td_field(raw, 'arguments') or tmpl.get('arguments', ''),
            'results': extract_td_field(raw, 'results') or tmpl.get('results', ''),
            'assembly_format': extract_td_field(raw, 'assemblyFormat') or tmpl.get('assembly_format', ''),
            'source': {
                'file': intr_rel,
                'line': blk['start_line'],
                'end_line': blk['end_line'],
                'sha256': files_meta[intr_rel]['sha256'],
            },
            'excerpt': raw,
        }

    # Build CCEC op lookup for cross-referencing
    db = Database()
    from ccec_ops import Ops
    ccec_ops_model = Ops(db).model
    ccec_ops_by_short = defaultdict(list)
    for o in ccec_ops_model['ops']:
        short = o['name'].lower()
        ccec_ops_by_short[short].append(o['id'])

    # Parse all backend llvm.hivm.* mappings and group into unique lower-layer CCE Dialect Intrinsics
    raw_mappings = parse_intrinsic_maps(repo)
    intr_groups = {}
    for m in [*raw_mappings, *cpp_mappings(repo, files_meta)]:
        llvm_name = m['llvm_intrinsic']
        if llvm_name not in intr_groups:
            intr_groups[llvm_name] = {
                'llvm_intrinsic': llvm_name,
                'mappings': [],
                'mlir_intr_ops': [],
                'op_keys': set(),
            }
        intr_groups[llvm_name]['mappings'].append(m)
        intr_groups[llvm_name]['op_keys'].add(m['op_key'])
        if 'intr_op_key' in m:
            intr_groups[llvm_name]['op_keys'].add(m['intr_op_key'])

    unresolved_lowerings = []
    # Attach mlir_intr_ops (from CCEIntrinsicOps.td) to their corresponding intr_group or create standalone entry
    for op_key, intr_op in mlir_intr_ops.items():
        matched = False
        for g in intr_groups.values():
            if op_key in g['op_keys']:
                g['mlir_intr_ops'].append(intr_op)
                matched = True
        if not matched:
            # Preserve the concrete MLIR op without inventing an LLVM target symbol.
            unresolved_lowerings.append({**intr_op, 'resolution': 'no_static_table_mapping'})

    lower_intrinsics = []
    for llvm_name in sorted(intr_groups):
        g = intr_groups[llvm_name]
        safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', llvm_name.removeprefix('llvm.hivm.').lower())
        intr_id = f'cce_dialect_intr_{safe_id}'
        primary_map = g['mappings'][0]
        primary_op_key = sorted(g['op_keys'])[0]
        family, transfer = classify_family(primary_op_key + ' ' + llvm_name, '', primary_map['mapping_class'])
        upstream_ids = set()
        for ok in g['op_keys']:
            for mn in normalize_op_key_to_mnemonic(ok):
                for up in upper_by_mnemonic.get(mn, []):
                    upstream_ids.add(up['id'])
                    up['intrinsic_ids'].append(intr_id)
        ccec_ids = match_ccec_ops(llvm_name, ccec_ops_by_short)
        for uid in upstream_ids:
            for up in upper_ops:
                if up['id'] == uid:
                    up['ccec_candidate_op_ids'].extend(ccec_ids)

        group_domain = (
            'SIMT Backend Intrinsics' if any('SIMT' in m['mapping_class'] or 'simt' in m.get('op_key', '') for m in g['mappings'])
            else 'CCE IntrOp Lowerings' if g['mlir_intr_ops']
            else 'Vector & Control Intrinsics'
        )
        lower_intrinsics.append({
            'id': intr_id,
            'name': llvm_name,
            'llvm_intrinsic': llvm_name,
            **assess_paths(g['mappings'], upper_by_mnemonic, mlir_intr_ops),
            'group': group_domain,
            'family': family,
            'transfer': transfer,
            'mapping_classes': sorted({m['mapping_class'] for m in g['mappings']}),
            'op_keys': sorted(g['op_keys']),
            'mlir_intr_ops': g['mlir_intr_ops'],
            'mappings': [{k: v for k, v in m.items() if k != 'raw'} for m in g['mappings']],
            'upstream_op_ids': sorted(upstream_ids),
            'ccec_candidate_op_ids': ccec_ids,
            'relation_resolution': 'lexical_name_candidate',
            'source': {
                **primary_map['source'],
                'sha256': files_meta[primary_map['source']['file']]['sha256'],
            },
            'excerpt': g['mlir_intr_ops'][0]['excerpt'] if g['mlir_intr_ops'] else primary_map.get('raw', ''),
        })

    for up in upper_ops:
        up['intrinsic_ids'] = sorted(set(up['intrinsic_ids']))
        up['ccec_candidate_op_ids'] = sorted(set(up['ccec_candidate_op_ids']))

    matched_specs = {up['spec']['op_def'] for up in upper_ops if up.get('spec')}
    unmatched_specs = sorted(set(spec_sections) - matched_specs)

    payload = {
        'schema_version': SCHEMA_VERSION,
        'backend': 'cce-dialect',
        'version': f'git-{head_commit[:7]}',
        'generator_sha256': sha256(Path(__file__)),
        'catalog_sha256': sha256(ROOT / 'data' / VERSION / 'catalog.json'),
        'target': {
            'architecture': 'dav-351x',
            'chip': 'Ascend950PR_9579',
            'ub_bytes': 256 * 1024,
            'vector_register_bytes': 256,
            'address_spaces': {'GM': 1, 'L1': 2, 'L0A': 3, 'L0B': 4, 'L0C': 5, 'UB': 6, 'PRIVATE': 9},
        },
        'source': {
            'repository': 'https://gitcode.com/AICompile/CCEDialect',
            'commit': head_commit,
            'working_tree_dirty': bool(subprocess.check_output(['git', '-C', str(repo), 'status', '--porcelain'], text=True).strip()),
            'files': files_meta,
        },
        'counts': {
            'ops': len(upper_ops),
            'ops_with_spec_doc': sum(1 for u in upper_ops if u.get('spec')),
            'ops_by_lowering_mode': dict(Counter(u['lowering_mode'] for u in upper_ops)),
            'intrinsics': len(lower_intrinsics),
            'path_status': dict(Counter(i['path_status'] for i in lower_intrinsics)),
            'tablegen_names': len({m['llvm_intrinsic'] for m in raw_mappings}),
            'unresolved_lowerings': len(unresolved_lowerings),
            'explicit_mlir_intr_ops': len(mlir_intr_ops),
            'tablegen_mapping_rows': len(raw_mappings),
            'spec_sections': len(spec_sections),
            'unmatched_spec_sections': unmatched_specs,
        },
        'ordinary_lowerings': [
            {'entry': 'cce.intr.simt.' + op, 'opcode': op, 'condition': '地址空间 6，i32',
             'source': {'file': 'lib/Dialect/CCE/CCETranslateSIMT.cpp', 'line': line}}
            for op, line in [('load', 583), ('store', 587)]
        ] + [
            {'entry': 'cce.simt.cast', 'opcode': op, 'condition': witness,
             'source': {'file': 'lib/Dialect/CCE/CCETranslateSIMT.cpp', 'line': line}}
            for op, witness, line in [('sitofp', 'i32 → f32，signed', 329), ('uitofp', 'i32 → f32，unsigned', 328),
                                      ('fptosi', 'f32 → i32，signed', 333), ('fptoui', 'f32 → i32，unsigned', 332)]
        ],
        'limitations': LIMITATIONS,
        'unresolved_lowerings': unresolved_lowerings,
        'ops': sorted(upper_ops, key=lambda x: x['name']),
        'intrinsics': sorted(lower_intrinsics, key=lambda x: x['name']),
    }
    return payload


def validate_model(data: dict) -> list[str]:
    errors = []
    if data.get('schema_version') != SCHEMA_VERSION:
        errors.append('Invalid schema_version')
    op_ids = {o['id'] for o in data.get('ops', [])}
    intr_ids = {i['id'] for i in data.get('intrinsics', [])}
    if len(op_ids) != len(data.get('ops', [])):
        errors.append('Duplicate op IDs in CCE Dialect ops')
    if len(intr_ids) != len(data.get('intrinsics', [])):
        errors.append('Duplicate intrinsic IDs in CCE Dialect intrinsics')
    if len(op_ids) < 200:
        errors.append(f'Too few CCE Dialect ops extracted: {len(op_ids)}')
    if len(intr_ids) < 1000:
        errors.append(f'Too few CCE Dialect intrinsics extracted: {len(intr_ids)}')
    for o in data.get('ops', []):
        for iid in o.get('intrinsic_ids', []):
            if iid not in intr_ids:
                errors.append(f'Dangling intrinsic_id {iid} in {o["id"]}')
    for i in data.get('intrinsics', []):
        for oid in i.get('upstream_op_ids', []):
            if oid not in op_ids:
                errors.append(f'Dangling upstream_op_id {oid} in {i["id"]}')
    if data.get('generator_sha256') != sha256(Path(__file__)):
        errors.append('Stale CCE Dialect generator snapshot')
    if data.get('catalog_sha256') != sha256(ROOT / 'data' / VERSION / 'catalog.json'):
        errors.append('Stale CCEC catalog binding')
    for item in data.get('intrinsics', []):
        if not re.fullmatch(r'llvm\.hivm\.[A-Za-z0-9_.]+', item['name']):
            errors.append('Non-concrete LLVM symbol: ' + item['name'])
        if not item['mappings'] or any(m['llvm_intrinsic'] != item['name'] for m in item['mappings']):
            errors.append('Inconsistent static mapping: ' + item['id'])
    states = Counter(i.get('path_status') for i in data.get('intrinsics', []))
    if states != data.get('counts', {}).get('path_status') or set(states) - {'confirmed', 'rejected', 'pending'}:
        errors.append('Invalid lowering coverage counts')
    for item in data.get('intrinsics', []):
        paths = item.get('entry_paths', [])
        if (item.get('path_status') == 'confirmed') != any(p['status'] == 'confirmed' for p in paths):
            errors.append('Missing or inconsistent entry witness: ' + item['name'])
    if data.get('counts', {}).get('intrinsics') != len(intr_ids):
        errors.append('Incorrect concrete intrinsic count')
    return errors


def web_payload(data: dict | None = None) -> dict:
    if data is None:
        data = json.loads(OUTPUT.read_text())
    errors = validate_model(data)
    if errors:
        raise ValueError('; '.join(errors))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    ext = sub.add_parser('extract')
    ext.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    ext.add_argument('--output', type=Path, default=OUTPUT)
    val = sub.add_parser('validate')
    val.add_argument('--input', type=Path, default=OUTPUT)
    args = parser.parse_args()

    if args.cmd == 'extract':
        data = extract(args.repo)
        errors = validate_model(data)
        if errors:
            raise ValueError('; '.join(errors))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        print(f'Extracted CCE Dialect knowledge base to {args.output}: {data["counts"]}')
    elif args.cmd == 'validate':
        data = json.loads(args.input.read_text())
        errors = validate_model(data)
        if errors:
            raise SystemExit('Validation failed: ' + '; '.join(errors))
        print(f'Validated {args.input}: {data["counts"]}')


if __name__ == '__main__':
    main()
