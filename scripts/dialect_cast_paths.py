"""Reachability witnesses for the pinned CCE vector and SIMT cast translators."""

import re


TRANSLATE = 'lib/Dialect/CCE/CCETranslate.cpp'
SIMT = 'lib/Dialect/CCE/CCETranslateSIMT.cpp'
ADAPT = 'lib/Dialect/CCE/CCEBackendAdapt.cpp'

FP8_TYPES = {'fp8e4m3': 'f8E4M3FN', 'fp8e5m2': 'f8E5M2',
             'f8e4m3': 'f8E4M3FN', 'f8e5m2': 'f8E5M2'}


def vector(lanes, key):
    element = FP8_TYPES.get(key, re.sub(r'^u', 'i', key))
    return f'vector<{lanes}x{element}>'


def assess(m, upper, lower, add):
    """Record the semantic entry even when a backend text rewrite emits the name."""
    name = m['llvm_intrinsic']
    key = m['op_key']
    if key == 'simt.cast':
        src, dst = name.removeprefix('llvm.hivm.').removesuffix('x2').split('x2.to.')
        entry = upper[key][0]
        if dst in FP8_TYPES:
            add(entry, 'rejected',
                f'名称分支接受 {vector(2, dst)}，但 SIMT 单结果调用必须转换 LLVM 结果类型。'
                '独立主机 LLVM 不接受 FP8 向量结果，vcvtff 的字节载体分支仅供 vcvt 使用。',
                TRANSLATE, 233)
        elif src in FP8_TYPES:
            add(entry, 'confirmed',
                f'cce.vcvtff.trunc 产生 {vector(256, src)}，以 <256 x i8> 传给 simt.cast，'
                f'结果取 {vector(2, dst)}。拼名分支只检查元素类型，另附两个 i32 0。'
                '此见证发出 x2 名称，实参是 256 个字节。',
                SIMT, 310)
        return

    if m['mapping_class'] == 'CppLiteral':
        # These literals are the end of the same four table-driven FP8 paths.
        trunc = '.f322' in name
        key = 'vcvtff.trunc' if trunc else 'vcvtff.ext'
        bridge = 'e4' if 'f8e4m3' in name else 'e5'
        marker = f'__opentileas.fp8.{bridge}.vcvt.{key.split(".")[1]}'
        add(upper[key][0], 'confirmed',
            f'{marker} 通过 <256 x i8> 传递 FP8，后端文本重写调用和声明，'
            f'在{"结果后" if trunc else "源操作数前"}插入载体 bitcast。',
            ADAPT, 94 if trunc else 135)
        return

    entry = upper[key][0]
    src, dst = m['src_element_type'], m['res_element_type']
    src_type = vector(m['src_lanes'], src)
    dst_type = vector(m['res_lanes'], dst)
    # Integer element types are signless in MLIR. Independent flags allow
    # mixed-sign conversions; sat=1 preserves the table key for truncation.
    roles = re.findall(r'(?:VectorTypeConstraint|I32):\$(\w+)', entry['arguments'])
    controls = {'sat': 1, 'part': 0, 'round': 0, 'param': 0}
    operands = {'src': src_type, 'mask': 'vector<256xi1>',
                **{role: f'{role}=i32 {value}' for role, value in controls.items()}}
    actual = [operands[role] for role in roles]
    mask = m['operand_mask']
    forwarded = [role for i, role in enumerate(roles) if not mask or mask & (1 << i)]
    if len(forwarded) != m['operand_count'] or m['result_count'] != 1:
        raise ValueError(f'Operand projection changed for {name}')
    condition = '(' + ', '.join(actual) + ') → ' + dst_type
    signedness_flags = [flag for flag, dtype in [('src_unsigned', src), ('dst_unsigned', dst)]
                        if dtype.startswith('u')]
    if signedness_flags:
        condition += '，设置 ' + ' 和 '.join(signedness_flags)
    if mask:
        condition += '，按位掩码传递 ' + ', '.join(forwarded)
    if dst in FP8_TYPES or src in FP8_TYPES:
        if src in FP8_TYPES:
            condition += '。源取同格式 vcvtff.trunc 的 <256 x i8> 结果'
        condition += '。先生成字节载体占位调用，再由 CCEBackendAdapt.cpp 恢复 FP8 调用'
        add(entry, 'confirmed', condition, TRANSLATE, 1557)
    else:
        add(entry, 'confirmed', condition, TRANSLATE, 1531)
