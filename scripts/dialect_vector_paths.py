"""Static witnesses for vector dispatch at CCEDialect 5639e58."""

TRANSLATE = 'lib/Dialect/CCE/CCETranslate.cpp'
VL = {'i8': 256, 'i16': 128, 'i32': 64, 'i64': 32, 'f16': 128, 'bf16': 128,
      'f32': 64, 'f8e4m3fn': 256, 'f8e5m2': 256}
# Each row describes one constructible op with a single result. D, V and P
# are expanded to concrete types before publishing the witness.
SINGLE = {
    'vabsdif': ('i8 i16 i32 f16 f32', 'V V P', 1537),
    'vaxpy': ('f16 f32', 'V V D P', 1622),
    'vbr': ('f16 f32 i8 i16 i32', 'D', None),
    'vci': ('f16 f32 i16 i32', 'D i32=0', 1469),
    'vdupv': ('bf16 f16 f32 i8 i16 i32', 'V i1=0', 1458),
    'vdups': ('bf16 f16 f32 i8 i16 i32', 'D P i32=0', 1256),
    'vexpdif': ('bf16 f16 f32', 'V V P i32=0', 1560),
    'vgather': ('bf16 f16 f32 i8 i16 i32 f8e4m3fn f8e5m2', 'UB V P', 1000),
    'vld': ('bf16 f16 f32 i8 i16 i32 i64 f8e4m3fn f8e5m2', 'UB i32=0 P', 928),
    'vlrelu': ('f16 f32', 'V D P', 1586),
    'vmadd': ('bf16 f16 f32', 'V V V P', 1605),
    'vmula': ('bf16 f16 f32 i16 i32', 'V V V P', None),
    'vsel': ('bf16 f16 f32 i8 i16 i32 f8e4m3fn f8e5m2', 'V V P', 371),
    'vslide': ('f16 f32 i8 i16 i32', 'V V i16=0', 1519),
    'vsqz': ('f16 f32 i8 i16 i32', 'V P i32=0', 1718),
    'vusqz': ('i8 i16 i32', 'V P', 1738),
}


def assess(m, upper, lower, add):
    """Emit reviewed paths, leaving keys outside these families to the caller."""
    if m['mapping_class'] != 'CCEVectorIntrinsic':
        return
    key, dtype, lanes = m['op_key'], m['element_type'], m['lanes']
    sign, mode = m['signedness'], m['merge_mode']
    arity = m['operand_count'], m['result_count']
    entry = 'histv2' if key in ('chistv2', 'dhistv2') else key
    vec = f'vector<{lanes}x{dtype}>'
    pred = 'vector<256xi1>'
    sign_attr = '附加 is_unsigned 单位属性' if sign == 'u' else '省略 unsigned 与 is_unsigned'
    details = f'查表键 ({key}, {lanes}, {dtype}, {sign}, {mode})。'

    def record(status, condition, line):
        add(upper[entry][0], status, details + condition, TRANSLATE, line)

    if key in SINGLE:
        types, operands, verifier = SINGLE[key]
        allowed_signs = ('s', 'u') if key == 'vabsdif' and dtype.startswith('i') else ('s',)
        if (dtype not in types.split() or lanes != VL[dtype] or sign not in allowed_signs
                or mode != ('z' if key == 'vdups' else 'x') or arity != (len(operands.split()), 1)):
            return
        if dtype.startswith('f8'):
            record('rejected', f'{vec} 可匹配生成表，但单结果发射器直接转换 FP8 结果。'
                   '本版本 LLVM 无该类型（CCETranslate.cpp:1542），此分支没有 i8 载体。', 233)
            return
        substitutions = {'D': dtype, 'V': vec, 'P': pred, 'UB': '!llvm.ptr<6>'}
        signature = ', '.join(substitutions.get(t, t) for t in operands.split())
        condition = f'({signature}) → {vec}，{sign_attr}。'
        if verifier:
            condition += f'见 CCEDialect.cpp:{verifier}。'
        if key == 'vdups':
            condition += '翻译器固定选 z。'
        record('confirmed', condition, 827)
    elif key in ('vaddc', 'vsubc', 'vaddcs', 'vsubcs'):
        carry_in = key.endswith('cs')
        if (dtype, lanes, mode, arity) == ('i32', 64, 'x', (4 if carry_in else 3, 2)) and sign in ('s', 'u'):
            masks = f'{pred}, {pred}' if carry_in else pred
            record('confirmed', f'({vec}, {vec}, {masks}) → ({vec}, {pred})，{sign_attr}。'
                   'CCEDialect.cpp:1660–1692 核对两输入、掩码与进借位。', 874)
    elif key in ('vcbmax', 'vcbmin'):
        if (dtype in ('i8', 'i16', 'i32', 'f16', 'f32') and lanes == VL[dtype]
                and mode in ('m', 'x') and arity == (2, 2) and (sign == 's' or sign == 'u' and dtype.startswith('i'))):
            record('confirmed', f'({vec}, {pred}) → ({vec}, {pred})，{sign_attr}，'
                   f'附加 mode=["{mode}"]。专用双结果分支从第一个源向量取键。', 1395)
    elif key in ('vintlv', 'vdintlv'):
        if dtype == 'i64' or lanes != VL.get(dtype) or (sign, mode, arity) != ('s', 'x', (2, 2)):
            return
        if dtype.startswith('f8'):
            emitted = {'f8e4m3fn': 'fp8e4m3', 'f8e5m2': 'fp8e5m2'}[dtype]
            record('rejected', f'双结果专用分支在 CCETranslate.cpp:1366 生成元素键 {emitted}，'
                   f'与生成表的 {dtype} 不匹配；入口在第 417 行直接返回。', 1395)
        else:
            record('confirmed', f'两个输入与两个结果均取 {vec}。CCEDialect.cpp:1481–1517 '
                   '核对向量长度和四者类型相同。', 1395)
    elif key == 'vdup':
        if (dtype not in ('bf16', 'f16', 'f32', 'i8', 'i16', 'i32') or lanes != VL[dtype]
                or sign != 's' or mode not in ('m', 'x', 'z') or arity != (4, 1)):
            return
        if mode != 'm':
            record('rejected', f'专用分支固定用 m 查表，i32 mode 操作数不参与选择 {mode}。', 1653)
        else:
            record('confirmed', f'({vec}, {vec}, {pred}, i32=0) → {vec}。'
                   'CCEDialect.cpp:1443 核对元素和长度。专用分支固定用 m。', 1656)
    elif key in ('chistv2', 'dhistv2') and (dtype, lanes, sign, mode, arity) == ('i16', 128, 's', 'x', (4, 1)):
        kind = 'frequency' if key == 'dhistv2' else 'cumulative'
        record('confirmed', f'histv2 的 kind={kind}。({vec}, vector<256xi8>, {pred}, i32=0) → {vec}，'
               '符合 CCEDialect.cpp:1695 的累加器、输入和 bin 限制。', 408)
    elif key == 'vmull':
        no_pass = (lanes, dtype, sign, mode, arity) == (64, 'i32', 'u', 'x', (3, 2))
        if not no_pass and not (
                (lanes, dtype) in ((32, 'i32'), (64, 'i16'), (64, 'f32'), (128, 'f16'))
                and (sign == 's' or sign == 'u' and dtype.startswith('i'))
                and mode in ('x', 'm', 'z') and arity == (4, 2)):
            return
        src = vec if no_pass else f'vector<{lanes * 2}x{dtype}>'
        tail = '三操作数表项直接发射。' if no_pass else '省略 pass_thru，第 600 行补入同结果类型的 undef。'
        record('confirmed', f'({src}, {src}, {pred}) → ({vec}, {vec})，{sign_attr}，'
               f'mode=["{mode}"]。{tail}', 590)
    elif key in ('vpack', 'vunpack'):
        pack = key == 'vpack'
        if lanes != VL.get(dtype) or mode != 'x' or arity != (2, 1):
            return
        if pack and dtype in ('f32', 'i32', 'i16', 'f16', 'bf16') and sign == 's':
            dst = 'vector<128xi16>' if lanes == 64 else 'vector<256xi8>'
            record('confirmed', f'({vec}, i32=0) → {dst}，vpack 按第一个操作数查表。', 749)
        elif not pack and dtype in ('i16', 'i32') and sign in ('s', 'u'):
            src = f'vector<{lanes * 2}xi{int(dtype[1:]) // 2}>'
            record('confirmed', f'({src}, i32=0) → {vec}，{sign_attr}。CCEDialect.cpp:1753 '
                   '要求元素位宽翻倍、结果 lane 数减半。', 827)
    elif key in ('vst', 'vscatter'):
        if (lanes != VL.get(dtype) or dtype == 'i64' and key == 'vscatter'
                or (sign, mode, arity) != ('s', 'x', (4, 0))):
            return
        index = vec if key == 'vscatter' else 'i32=0'
        carrier = ('语义 FP8 操作数取自 cce.intr.vldsx1.i8，其结果在 CCETranslate.cpp:944–973 '
                   '映射为 vector<256xi8>。void 分支直接使用该 LLVM 值。' if dtype.startswith('f8') else '')
        record('confirmed', f'({vec}, !llvm.ptr<6>, {index}, {pred}) → void。{carrier}', 669)
