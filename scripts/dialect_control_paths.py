"""Audit control dispatch and embedded print-library calls at the source pin."""

TRANSLATE = 'lib/Dialect/CCE/CCETranslate.cpp'
DRIVER = 'tools/cce-translate/cce-translate.cpp'

# For each intrinsic, retain both call sites and the enclosing helper.
PRINT_HELPERS = {
    'llvm.hivm.DCCI.DST': {
        103: 'DebugTunnel_Finish.vector 经 OnKernelFinish 调用 PrintPayload 的收尾函数，数据指针非空时执行 DCCI',
        257: 'printf.vector 在取得调试实例、写入缓冲并处理非空格式串后执行 DCCI',
    },
    'llvm.hivm.get.sycl.fix.stack.object': {
        112: 'DebugTunnel_Initialize.vector 经 OnKernelInitialize 读取栈对象',
        170: 'printf.vector 与 Write 调用 GetKernelInstance，后者读取栈对象',
    },
}


def assess(m, upper, lower, add):
    key = m['op_key']
    kind = m['mapping_class']
    name = m['llvm_intrinsic']
    if kind == 'EmbeddedIRCall' and name in PRINT_HELPERS:
        helpers = PRINT_HELPERS[name]
        line = m['source']['line']
        if line == min(helpers):
            add(upper['print'][0], 'rejected',
                '独立翻译器遇到 cce.print 会要求先降低为 cce.intr.print，然后返回失败。',
                TRANSLATE, 1697)
        add(lower['intr.print'], 'rejected',
            f'{helpers[line]}。--enable-print 将整段辅助函数写入输出。cce.intr.print 生成的 '
            '_mlir_ciface_print_* 和附加的 _mlir_ciface_{init,finish}_debug 均为外部入口，'
            '固定源码内缺少从这些入口到该辅助函数的调用边。',
            m['source']['file'], line)
    elif kind == 'CCEMembarIntrinsic' and m['barrier_kind'] != 0:
        add(upper[key][0], 'rejected',
            f"barrierKind={m['barrier_kind']} 要求输入由 arith.constant 定义"
            '（CCETranslate.cpp 第 1613–1615 行）。独立驱动只注册 Builtin、LLVM 和 CCE，'
            'llvm.mlir.constant 和 i32 函数参数都会保留默认值 0。',
            DRIVER, 30)
    elif kind == 'CCEEnumIntrinsic' and key == 'wait.flag.dev.pipe.imm':
        add(upper[key][0], 'confirmed', 'pipe=PIPE_V、flag_id=0（i64 属性），枚举查表收集两个 i64 实参。',
            TRANSLATE, 1015)
    elif kind == 'CppLiteral' and key in ('set.cross.core', 'wait.flag.dev.pipe.reg'):
        operand = 'config' if key == 'set.cross.core' else 'flag_id'
        add(upper[key][0], 'confirmed',
            f'pipe=PIPE_V，{operand} 为 i64 函数参数。枚举表只提供 pipe，'
            '随后专用分支补上 SSA 操作数并发出调用。', TRANSLATE, 1067)
    elif kind == 'CppLiteral' and key in ('set.intra.blocki.mode', 'wait.intra.blocki.mode'):
        add(upper[key][0], 'confirmed', 'pipe=PIPE_V，syncid 为唯一的 i64 函数参数。',
            TRANSLATE, 1047)
    elif kind == 'CppLiteral' and key in ('set_flag', 'wait_flag'):
        if name.endswith('.IMM'):
            add(upper[key][0], 'confirmed',
                'pipe=PIPE_V、tpipe=PIPE_M，仅设置 static_event_id=EVENT_ID0，传入三个 i64 立即值。',
                TRANSLATE, 1086)
        else:
            add(upper[key][0], 'confirmed',
                'pipe=PIPE_V、tpipe=PIPE_M，仅设置 dynamic_event_id（i64 函数参数），选择 REG 分支。',
                TRANSLATE, 1092)
