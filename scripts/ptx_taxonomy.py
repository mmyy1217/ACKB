#!/usr/bin/env python3
"""Build structured PTX 9.7 instruction taxonomy and syntax qualifier profiles."""

import argparse
import json
import re
from pathlib import Path

from catalog import ROOT

DOMAINS = [
    {
        'id': 'arithmetic_logic',
        'title': '算术与逻辑',
        'summary': '整数、浮点、半精度、混合精度、FP8、比较选择、位运算与 SIMD 视频算术。',
        'categories': ['9.7.1', '9.7.2', '9.7.3', '9.7.4', '9.7.5', '9.7.6', '9.7.7', '9.7.8', '9.7.9', '9.7.20'],
    },
    {
        'id': 'memory_movement',
        'title': '访存、寻址与搬运',
        'summary': '寄存器/向量打包、状态空间转换、常规访存与缓存策略、cp.async、Bulk/TMA 异步搬运与稀疏压缩。',
        'categories': ['9.7.10'],
    },
    {
        'id': 'sync_atomics',
        'title': '同步、屏障与原子',
        'summary': 'CTA/Warp/Cluster 屏障、内存序与 Proxy Fence、原子归约、Warp 集合原语、mbarrier 与网格启动控制。',
        'categories': ['9.7.15'],
    },
    {
        'id': 'matrix_tensor',
        'title': '矩阵与 Tensor Core',
        'summary': '从 wmma、Warp 级 mma/ldmatrix 到 Hopper wgmma 与 B300 第五代 tcgen05 / TMEM 矩阵流水。',
        'categories': ['9.7.16', '9.7.17', '9.7.18'],
    },
    {
        'id': 'control_stack',
        'title': '控制流与栈',
        'summary': '指令块、谓词执行、分支跳转表、函数调用返回与线程本地动态栈分配。',
        'categories': ['9.7.14', '9.7.19'],
    },
    {
        'id': 'fabric_comm',
        'title': 'Fabric 跨节点互联',
        'summary': 'NVLink/Fabric 逻辑端点的异步读写、张量传输、多播归约与原子操作。',
        'categories': ['9.7.11'],
    },
    {
        'id': 'texture_misc',
        'title': '纹理、Surface 与杂项',
        'summary': '纹理采样、Surface 图像访存、调试断点、性能事件、休眠及动态寄存器重分配。',
        'categories': ['9.7.12', '9.7.13', '9.7.21'],
    },
]

CATEGORIES = [
    {
        'id': '9.7.1',
        'anchor': 'integer-arithmetic-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '整数算术与位域',
        'title_en': 'Integer Arithmetic Instructions',
        'summary': '标准整数加减乘除、饱和运算、无进位乘加 clmad、位域提取/插入与整数点积 dp4a/dp2a。',
        'compiler_focus': '区分低位 .lo / 高位 .hi / 扩宽 .wide 乘法；地址索引优先使用 mul.wide 与 mad.lo；量化推理关注 dp4a 4x8-bit 点积；位域操作（bfe/bfi/bfind/fns/bmsk）可替代移位掩码序列。',
        'key_qualifiers': [
            {'qualifier': '.u16/.s16/.u32/.s32/.u64/.s64', 'meaning': '整数位宽与有符号/无符号语义；部分指令支持打包向量 .u16x2/.s16x2/.u8x4/.s8x4'},
            {'qualifier': '.hi / .lo / .wide', 'meaning': '乘法或乘加输出截取高位、低位或扩宽至双倍位宽'},
            {'qualifier': '.sat / .relu', 'meaning': '有符号饱和截断或负值置零钳位'},
        ],
        'related_lessons': ['learn_arithmetic', 'learn_loads'],
        'subcategories': [
            {
                'id': '9.7.1.basic',
                'title_zh': '基础整数算术与点积',
                'summary': '加减乘、乘加、无进位乘加、24 位乘法、绝对差和、除余、绝对值取反极值与 dp4a/dp2a。',
                'anchors': [
                    'integer-arithmetic-instructions-add', 'integer-arithmetic-instructions-sub',
                    'integer-arithmetic-instructions-mul', 'integer-arithmetic-instructions-mad',
                    'integer-arithmetic-instructions-clmad', 'integer-arithmetic-instructions-mul24',
                    'integer-arithmetic-instructions-mad24', 'integer-arithmetic-instructions-sad',
                    'integer-arithmetic-instructions-div', 'integer-arithmetic-instructions-rem',
                    'integer-arithmetic-instructions-abs', 'integer-arithmetic-instructions-neg',
                    'integer-arithmetic-instructions-min', 'integer-arithmetic-instructions-max',
                    'integer-arithmetic-instructions-dp4a', 'integer-arithmetic-instructions-dp2a',
                ],
            },
            {
                'id': '9.7.1.bitfield',
                'title_zh': '位计数、前导零与位域操作',
                'summary': 'popc/clz/bfind/fns 位搜索，brev 位反转，bfe/bfi/szext/bmsk 位域提取与构造。',
                'anchors': [
                    'integer-arithmetic-instructions-popc', 'integer-arithmetic-instructions-clz',
                    'integer-arithmetic-instructions-bfind', 'integer-arithmetic-instructions-fns',
                    'integer-arithmetic-instructions-brev', 'integer-arithmetic-instructions-bfe',
                    'integer-arithmetic-instructions-bfi', 'integer-arithmetic-instructions-szext',
                    'integer-arithmetic-instructions-bmsk',
                ],
            },
        ],
    },
    {
        'id': '9.7.2',
        'anchor': 'extended-precision-integer-arithmetic-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '扩展精度整数算术',
        'title_en': 'Extended-Precision Integer Arithmetic Instructions',
        'summary': '通过隐式进位/借位标志 CC.CF 串联多字（128 位及以上）大整数加减与乘加。',
        'compiler_focus': 'add.cc/sub.cc 写入进位条件码寄存器 CC.CF，后续 addc/subc/madc 消费 CC.CF；指令调度器不可破坏两条指令之间的 CC 活跃区间。',
        'key_qualifiers': [
            {'qualifier': '.cc', 'meaning': '写回进位/借位标志到条件码寄存器 CC.CF'},
            {'qualifier': '.hi / .lo', 'meaning': 'mad.cc / madc 选择乘积高半部或低半部参与累加并传递进位'},
        ],
        'related_lessons': ['learn_arithmetic'],
    },
    {
        'id': '9.7.3',
        'anchor': 'floating-point-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '标准浮点运算',
        'title_en': 'Floating-Point Instructions',
        'summary': 'IEEE 754 .f32/.f32x2/.f64 加减乘、融合乘加 fma、除法、开方与特殊功能单元（SFU）近似超越函数。',
        'compiler_focus': 'fma.rn 仅一次舍入且不可随意拆为 mul+add；.ftz 将非正规数冲刷为零；sin/cos/lg2/ex2/rcp.approx/rsqrt.approx 走快速近似路径，精度不同于 IEEE 舍入版。',
        'key_qualifiers': [
            {'qualifier': '.rn / .rz / .rm / .rp', 'meaning': 'IEEE 754 舍入模式：向最近偶数、向零、向负无穷、向正无穷'},
            {'qualifier': '.ftz', 'meaning': 'Flush-to-Zero：将 f32 非正规输入与结果冲刷为零'},
            {'qualifier': '.sat / .approx / .full', 'meaning': '结果钳位到 [0,1]，或选择 SFU 快速近似/全范围近似计算'},
        ],
        'related_lessons': ['learn_arithmetic'],
        'subcategories': [
            {
                'id': '9.7.3.ieee',
                'title_zh': 'IEEE 算术、分类与极值',
                'summary': 'testp 浮点分类、copysign、add/sub/mul/fma/mad/div/abs/neg/min/max。',
                'anchors': [
                    'floating-point-instructions-testp', 'floating-point-instructions-copysign',
                    'floating-point-instructions-add', 'floating-point-instructions-sub',
                    'floating-point-instructions-mul', 'floating-point-instructions-fma',
                    'floating-point-instructions-mad', 'floating-point-instructions-div',
                    'floating-point-instructions-abs', 'floating-point-instructions-neg',
                    'floating-point-instructions-min', 'floating-point-instructions-max',
                ],
            },
            {
                'id': '9.7.3.sfu',
                'title_zh': '倒数、平方根与超越函数',
                'summary': 'rcp、sqrt、rsqrt 及 sin/cos/lg2/ex2/tanh 硬件近似与精确形式。',
                'anchors': [
                    'floating-point-instructions-rcp', 'floating-point-instructions-rcp-approx-ftz-f64',
                    'floating-point-instructions-sqrt', 'floating-point-instructions-rsqrt',
                    'floating-point-instructions-rsqrt-approx-ftz-f64', 'floating-point-instructions-sin',
                    'floating-point-instructions-cos', 'floating-point-instructions-lg2',
                    'floating-point-instructions-ex2', 'floating-point-instructions-tanh',
                ],
            },
        ],
    },
    {
        'id': '9.7.4',
        'anchor': 'half-precision-floating-point-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '半精度浮点 (.f16 / .bf16)',
        'title_en': 'Half Precision Floating-Point Instructions',
        'summary': '标量及打包双元素 .f16/.f16x2/.bf16/.bf16x2 运算，含硬件级 .tanh 与 .ex2。',
        'compiler_focus': '向量化 .f16x2/.bf16x2 在 32 位寄存器内打包两个半精度数，单指令吞吐翻倍；注意 .bf16 部分形式不带 .ftz，.NaN/.xorsign.abs 用于特殊值语义控制。',
        'key_qualifiers': [
            {'qualifier': '.f16 / .f16x2 / .bf16 / .bf16x2', 'meaning': 'IEEE FP16 与 Brain Float16 标量及 32 位打包双元素形式'},
            {'qualifier': '.relu / .sat / .NaN', 'meaning': '融合 ReLU 激活、结果饱和或保留 NaN 传播'},
        ],
        'related_lessons': ['learn_arithmetic'],
    },
    {
        'id': '9.7.5',
        'anchor': 'mixed-precision-floating-point-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '混合精度浮点',
        'title_en': 'Mixed Precision Floating-Point Instructions',
        'summary': '半精度输入与 .f32/.f32x2 累加或输出直接混合运算，减少显式 cvt 指令。',
        'compiler_focus': '当内核需要在半精度输入上维持 FP32 累加或融合标量缩放时，直接生成混合精度 add/sub/mul/fma 可省去中间类型转换开销。',
        'key_qualifiers': [
            {'qualifier': '.cdtype.atype / .dtype.atype.btype.ctype', 'meaning': '分别声明目的、第一/二/三操作数的混合浮点类型组合'},
        ],
        'related_lessons': ['learn_arithmetic'],
    },
    {
        'id': '9.7.6',
        'anchor': 'alternate-floating-point-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '备选浮点 (FP8 / FP4 打包运算)',
        'title_en': 'Alternate Floating-Point Instructions',
        'summary': '面向低比特 AI 推理/训练的 4 路打包 .e4m3x4/.e5m2x4/.e3m2x4/.e2m3x4/.e2m1x4 向量算术。',
        'compiler_focus': '注意这类指令目标条件高度受限（通常对应特定 Blackwell/sm_120 家族与精确目标），使用前须逐项核对 Target ISA Notes 与 .satfinite 语义。',
        'key_qualifiers': [
            {'qualifier': '.e4m3x4 / .e5m2x4 / .e2m1x4 等', 'meaning': '32 位寄存器内打包 4 个窄浮点格式元素'},
            {'qualifier': '.satfinite', 'meaning': '溢出时饱和到有限最大值而非生成无穷大'},
        ],
        'related_lessons': ['learn_b300'],
    },
    {
        'id': '9.7.7',
        'anchor': 'comparison-and-selection-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '比较与选择',
        'title_en': 'Comparison and Selection Instructions',
        'summary': '产生整型掩码（set）、谓词寄存器（setp）及无分支条件选择（selp / slct）。',
        'compiler_focus': '短分支在 PTX lowering 中应优先转换为 setp + selp 无分支选择，避免 warp 控制流分歧；浮点比较需明确 ordered（eq/lt）与 unordered（equ/ltu）对 NaN 的处理。',
        'key_qualifiers': [
            {'qualifier': '.CmpOp', 'meaning': '比较算子：整数 eq/ne/lt/le/gt/ge 等，浮点含 ordered/unordered 及 num/nan'},
            {'qualifier': '.BoolOp', 'meaning': '与第三谓词操作数融合布尔组合：.and / .or / .xor'},
        ],
        'related_lessons': ['learn_warp', 'learn_predication_divergence'],
    },
    {
        'id': '9.7.8',
        'anchor': 'half-precision-comparison-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '半精度比较',
        'title_en': 'Half Precision Comparison Instructions',
        'summary': '针对 .f16/.f16x2/.bf16/.bf16x2 的半精度比较（set / setp）。',
        'compiler_focus': '.f16x2 / .bf16x2 的 setp 可一次生成双谓词 p|q，分别对应低半部与高半部元素的比较结果。',
        'key_qualifiers': [
            {'qualifier': '.f16 / .f16x2 / .bf16 / .bf16x2', 'meaning': '半精度比较格式；x2 形式支持双谓词输出 p|q'},
        ],
        'related_lessons': ['learn_warp'],
    },
    {
        'id': '9.7.9',
        'anchor': 'logic-and-shift-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '逻辑与移位',
        'title_en': 'Logic and Shift Instructions',
        'summary': '按位/谓词逻辑运算、三输入查找表逻辑 lop3、漏斗移位 shf 与标准移位 shl/shr。',
        'compiler_focus': 'lop3.b32 用 8 位立即数 immLut 在单指令内实现任意三元布尔表达式；shf 实现 64 位拼接移位与循环移位；shr 根据 .u/.s 区分逻辑右移与算术右移。',
        'key_qualifiers': [
            {'qualifier': '.pred / .b16 / .b32 / .b64', 'meaning': '位宽或谓词逻辑类型；cnot 将 0/非0 规范化为 1/0'},
            {'qualifier': 'immLut (lop3) / .clamp/.wrap (shf)', 'meaning': 'lop3 真值表查表码与漏斗移位的移位量截断模式'},
        ],
        'related_lessons': ['learn_arithmetic'],
    },
    {
        'id': '9.7.10',
        'anchor': 'data-movement-and-conversion-instructions',
        'domain': 'memory_movement',
        'title_zh': '数据搬运、地址与转换',
        'title_en': 'Data Movement and Conversion Instructions',
        'summary': 'PTX 最庞大的指令族（41 条）：涵盖 mov/cvt/cvta、常规 ld/st 与缓存控制、多播 multimem、cp.async、Bulk/TMA 异步张量拷贝、tensormap 修改与稀疏压缩。',
        'compiler_focus': '核心在于区分地址空间（global/shared/local/param vs generic）、Proxy（generic vs async vs tensormap）、同步访存缓存逐出策略以及 TMA 1D–5D 异步数据通路。',
        'key_qualifiers': [
            {'qualifier': '.ss (.global/.shared/.local/.param/.const)', 'meaning': '显式状态空间，避免通用指针运行时空间解析开销'},
            {'qualifier': '.cop / .level::cache_hint / .level1/2::eviction_priority', 'meaning': 'L1/L2 缓存策略（.ca/.cg/.cs/.lu/.cv）与驱逐优先级'},
            {'qualifier': '.weak / .volatile / .relaxed / .acquire / .release', 'meaning': '访存的内存一致性语义（第 8 章）'},
            {'qualifier': '.completion_mechanism (.mbarrier / .bulk_group)', 'meaning': '异步搬运的完成通知机制：mbarrier 字节计数或 bulk_group 计数'},
        ],
        'related_lessons': ['learn_registers', 'learn_spaces', 'learn_loads', 'learn_cache_addressing', 'learn_tma_mbarrier'],
        'subcategories': [
            {
                'id': '9.7.10.move_addr',
                'title_zh': '寄存器、洗牌、地址空间与转换',
                'summary': 'mov（含向量打包）、shfl.sync、prmt 字节重排、isspacep、cvta、cvt/cvt.pack、mapa 与 getctarank。',
                'anchors': [
                    'data-movement-and-conversion-instructions-mov',
                    'data-movement-and-conversion-instructions-mov-2',
                    'data-movement-and-conversion-instructions-shfl',
                    'data-movement-and-conversion-instructions-shfl-sync',
                    'data-movement-and-conversion-instructions-prmt',
                    'data-movement-and-conversion-instructions-isspacep',
                    'data-movement-and-conversion-instructions-cvta',
                    'data-movement-and-conversion-instructions-cvt',
                    'data-movement-and-conversion-instructions-cvt-pack',
                    'data-movement-and-conversion-instructions-mapa',
                    'data-movement-and-conversion-instructions-getctarank',
                ],
            },
            {
                'id': '9.7.10.sync_mem',
                'title_zh': '常规访存、只读缓存与逐出策略',
                'summary': 'ld / ld.global.nc / ldu / st / st.async / st.bulk、prefetch/prefetchu、applypriority*、discard 与 createpolicy。',
                'anchors': [
                    'data-movement-and-conversion-instructions-ld',
                    'data-movement-and-conversion-instructions-ld-global-nc',
                    'data-movement-and-conversion-instructions-ldu',
                    'data-movement-and-conversion-instructions-st',
                    'data-movement-and-conversion-instructions-st-async',
                    'data-movement-and-conversion-instructions-st-bulk',
                    'data-movement-and-conversion-instructions-prefetch-prefetchu',
                    'data-movement-and-conversion-instructions-applypriority',
                    'data-movement-and-conversion-instructions-applypriority-async-bulk',
                    'data-movement-and-conversion-instructions-applypriority-async-bulk-tensor',
                    'data-movement-and-conversion-instructions-discard',
                    'data-movement-and-conversion-instructions-createpolicy',
                ],
            },
            {
                'id': '9.7.10.multimem',
                'title_zh': 'Multimem 多播访存与归约',
                'summary': '面向 NVLink Switch 多 GPU 多播地址空间的 multimem.ld_reduce/st/red 与 st.async。',
                'anchors': [
                    'data-movement-and-conversion-instructions-multimem',
                    'data-movement-and-conversion-instructions-multimem-st-async',
                ],
            },
            {
                'id': '9.7.10.cp_async',
                'title_zh': 'Non-Bulk 异步拷贝 (cp.async)',
                'summary': 'per-thread 发起 global → shared::cta 4/8/16B 异步搬运与 async-group 提交等待。',
                'anchors': [
                    'data-movement-and-conversion-instructions-cp-async',
                    'data-movement-and-conversion-instructions-cp-async-commit-group',
                    'data-movement-and-conversion-instructions-cp-async-wait-group',
                ],
            },
            {
                'id': '9.7.10.bulk_tma',
                'title_zh': 'Bulk 与 TMA 张量异步搬运',
                'summary': '1D 连续 bulk 搬运、1D–5D TMA tensor 搬运/归约/预取、bulk_group 等待及 tensormap 动态字段更新。',
                'anchors': [
                    'data-movement-and-conversion-instructions-cp-async-bulk',
                    'data-movement-and-conversion-instructions-cp-reduce-async-bulk',
                    'data-movement-and-conversion-instructions-cp-async-bulk-prefetch',
                    'data-movement-and-conversion-instructions-multimem-cp-async-bulk',
                    'data-movement-and-conversion-instructions-multimem-cp-reduce-async-bulk',
                    'data-movement-and-conversion-instructions-cp-async-bulk-tensor',
                    'data-movement-and-conversion-instructions-cp-reduce-async-bulk-tensor',
                    'data-movement-and-conversion-instructions-cp-async-bulk-prefetch-tensor',
                    'data-movement-and-conversion-instructions-cp-async-bulk-commit-group',
                    'data-movement-and-conversion-instructions-cp-async-bulk-wait-group',
                    'data-movement-and-conversion-instructions-tensormap-replace',
                ],
            },
            {
                'id': '9.7.10.sparse',
                'title_zh': '结构化稀疏压缩/解压',
                'summary': '2:4 结构化稀疏数据的寄存器压缩（spcompress）与解压（spdecompress）。',
                'anchors': [
                    'data-movement-and-conversion-instructions-spcompress',
                    'data-movement-and-conversion-instructions-spdecompress',
                ],
            },
        ],
    },
    {
        'id': '9.7.11',
        'anchor': 'fabric-instructions',
        'domain': 'fabric_comm',
        'title_zh': 'Fabric 互联通信',
        'title_en': 'Fabric Instructions',
        'summary': '面向逻辑端点句柄 [srcLeId/dstLeId, offset] 的跨设备异步 get/put、张量传输、多播归约与原子操作。',
        'compiler_focus': '所有操作均通过 async + mbarrier::complete_tx::bytes.mbarrier::report::fabric 完成，配合 fabric.submit 与 fabric.wait 控制在途事务与完成排序。',
        'key_qualifiers': [
            {'qualifier': '.async / .multimem', 'meaning': '异步传输与跨逻辑端点多播目标选择'},
            {'qualifier': '.mbarrier::complete_tx::bytes.mbarrier::report::fabric', 'meaning': '绑定 Fabric 事务报告与字节完成计数'},
        ],
        'related_lessons': ['learn_async'],
    },
    {
        'id': '9.7.12',
        'anchor': 'texture-instructions',
        'domain': 'texture_misc',
        'title_zh': '纹理采样指令',
        'title_en': 'Texture Instructions',
        'summary': '通过纹理引用与采样器进行 1D/2D/3D/Cube 硬件插值采样（tex）、4 纹素收集（tld4）与属性查询（txq/istypep）。',
        'compiler_focus': '统一与独立纹理对象模式使用不同操作数槽位；返回 v4 四分量寄存器组，可带稀疏驻留谓词输出 d|p。',
        'key_qualifiers': [
            {'qualifier': '.geom (.1d/.2d/.3d/.cube 等)', 'meaning': '纹理几何维度与数组/多重采样形态'},
            {'qualifier': '.v4.dtype.ctype', 'meaning': '返回四分量数据类型与坐标类型'},
        ],
        'related_lessons': ['learn_spaces'],
    },
    {
        'id': '9.7.13',
        'anchor': 'surface-instructions',
        'domain': 'texture_misc',
        'title_zh': 'Surface 表面读写',
        'title_en': 'Surface Instructions',
        'summary': '对 Surface 图像对象按字节或格式化的读写（suld / sust）、原子归约（sured）与维度查询（suq）。',
        'compiler_focus': '必须指定越界钳位模式（.trap / .clamp / .zero）；区分无格式 .b（字节寻址）与格式化 .p（像素格式自动转换）。',
        'key_qualifiers': [
            {'qualifier': '.trap / .clamp / .zero', 'meaning': '坐标越界时触发陷阱、钳位到边界或返回零'},
            {'qualifier': '.b vs .p', 'meaning': '按字节原始访问 vs 按像素格式读写'},
        ],
        'related_lessons': ['learn_spaces'],
    },
    {
        'id': '9.7.14',
        'anchor': 'control-flow-instructions',
        'domain': 'control_stack',
        'title_zh': '控制流与谓词执行',
        'title_en': 'Control Flow Instructions',
        'summary': '作用域块 {}、指令级谓词 @p、直接/收敛分支 bra{.uni}、索引跳转表 brx.idx、函数调用与退出。',
        'compiler_focus': '.uni 声明 warp 内所有活跃线程走向同一目标，允许编译器省略收敛栈维护；错误使用 .uni 属于未定义行为。brx.idx 用于 switch 跳转表 lowering。',
        'key_qualifiers': [
            {'qualifier': '@{!}p', 'meaning': '每条指令前缀谓词守卫，决定当前线程是否提交该指令效果'},
            {'qualifier': '.uni', 'meaning': '保证整个 warp 一致走同一控制流路径'},
        ],
        'related_lessons': ['learn_warp', 'learn_predication_divergence'],
    },
    {
        'id': '9.7.15',
        'anchor': 'parallel-synchronization-and-communication-instructions',
        'domain': 'sync_atomics',
        'title_zh': '并行同步、内存序、原子与 mbarrier',
        'title_en': 'Parallel Synchronization and Communication Instructions',
        'summary': 'CTA/Warp/Cluster 同步屏障、membar/fence、原子与归约、Warp 集合原语、mbarrier 完整对象协议及 Cluster Launch Control。',
        'compiler_focus': '把“线程会合（bar/bar.warp.sync）”、“内存可见性（fence/sem/scope）”和“异步完成计数（mbarrier）”严格拆开建模；Warp 原语须保证参与掩码 membermask 与未退出活跃线程一致。',
        'key_qualifiers': [
            {'qualifier': '.sem (.relaxed / .acquire / .release / .acq_rel)', 'meaning': '原子、栅栏和 mbarrier 的内存获取/释放次序'},
            {'qualifier': '.scope (.cta / .cluster / .gpu / .sys)', 'meaning': '内存同步所覆盖的线程作用范围'},
            {'qualifier': 'membermask', 'meaning': '32 位 warp 参与掩码，指定参与本次集合同步的 lane'},
            {'qualifier': '.layout::v0 / .layout::v1', 'meaning': 'mbarrier 对象内部布局版本选择'},
        ],
        'related_lessons': ['learn_sync', 'learn_async', 'learn_memory_consistency', 'learn_tma_mbarrier', 'learn_warp_collectives'],
        'subcategories': [
            {
                'id': '9.7.15.barrier',
                'title_zh': '线程会合屏障 (CTA / Warp / Cluster)',
                'summary': 'bar/barrier CTA 屏障、bar.warp.sync 掩码收敛屏障与 barrier.cluster 跨 CTA 屏障。',
                'anchors': [
                    'parallel-synchronization-and-communication-instructions-bar',
                    'parallel-synchronization-and-communication-instructions-bar-warp-sync',
                    'parallel-synchronization-and-communication-instructions-barrier-cluster',
                ],
            },
            {
                'id': '9.7.15.fence',
                'title_zh': '内存栅栏与 Proxy Fence',
                'summary': 'membar / fence（含 fence.proxy.async / tensormap）与 tensormap.cp_fenceproxy。',
                'anchors': [
                    'parallel-synchronization-and-communication-instructions-membar',
                    'parallel-synchronization-and-communication-instructions-tensormap-cp-fenceproxy',
                ],
            },
            {
                'id': '9.7.15.atomic',
                'title_zh': '原子读改写与异步归约',
                'summary': 'atom（带返回值）、red（无返回值归约）、red.async 与 multimem.red.async。',
                'anchors': [
                    'parallel-synchronization-and-communication-instructions-atom',
                    'parallel-synchronization-and-communication-instructions-red',
                    'parallel-synchronization-and-communication-instructions-red-async',
                    'parallel-synchronization-and-communication-instructions-multimem-red-async',
                ],
            },
            {
                'id': '9.7.15.warp',
                'title_zh': 'Warp 级集合原语',
                'summary': 'vote/vote.sync 表决、match.sync 相等分组、activemask、redux.sync 归约与 elect.sync 单线选举。',
                'anchors': [
                    'parallel-synchronization-and-communication-instructions-vote',
                    'parallel-synchronization-and-communication-instructions-vote-sync',
                    'parallel-synchronization-and-communication-instructions-match-sync',
                    'parallel-synchronization-and-communication-instructions-activemask',
                    'parallel-synchronization-and-communication-instructions-redux-sync',
                    'parallel-synchronization-and-communication-instructions-elect-sync',
                ],
            },
            {
                'id': '9.7.15.mbarrier',
                'title_zh': 'mbarrier 异步屏障生命周期',
                'summary': 'mbarrier.init/inval、expect_tx/complete_tx 事务跟踪、arrive/arrive_drop、cp.async 绑定与 test_wait/try_wait。',
                'anchors': [
                    'parallel-synchronization-and-communication-instructions-mbarrier-init',
                    'parallel-synchronization-and-communication-instructions-mbarrier-inval',
                    'parallel-synchronization-and-communication-instructions-mbarrier-expect-tx',
                    'parallel-synchronization-and-communication-instructions-mbarrier-complete-tx',
                    'parallel-synchronization-and-communication-instructions-mbarrier-arrive',
                    'parallel-synchronization-and-communication-instructions-mbarrier-arrive-drop',
                    'parallel-synchronization-and-communication-instructions-cp-async-mbarrier-arrive',
                    'parallel-synchronization-and-communication-instructions-mbarrier-test-wait-try-wait',
                    'parallel-synchronization-and-communication-instructions-mbarrier-pending-count',
                    'parallel-synchronization-and-communication-instructions-mbarrier-check-layout',
                ],
            },
            {
                'id': '9.7.15.grid_clc',
                'title_zh': 'Grid 依赖与 Cluster 启动控制',
                'summary': 'PDL 网格依赖发射（griddepcontrol）与动态工作窃取 cancel 控制（clusterlaunchcontrol）。',
                'anchors': [
                    'parallel-synchronization-and-communication-instructions-griddepcontrol',
                    'parallel-synchronization-and-communication-instructions-clusterlaunchcontrol-try-cancel',
                    'parallel-synchronization-and-communication-instructions-clusterlaunchcontrol-query-cancel',
                ],
            },
        ],
    },
    {
        'id': '9.7.16',
        'anchor': 'warp-level-matrix-instructions',
        'domain': 'matrix_tensor',
        'title_zh': 'Warp 级矩阵指令 (WMMA / MMA)',
        'title_en': 'Warp Level Matrix Multiply-Accumulate Instructions',
        'summary': '单 Warp 32 线程协同的 Tensor Core 指令：初代 wmma.* 与细粒度寄存器片段控制 mma / ldmatrix / stmatrix / movmatrix / mma.sp。',
        'compiler_focus': '整个 warp 的 32 个 lane 共同持有矩阵片段；ldmatrix 用每线程行指针一次从 shared 装载 8x8 tile 并自动分发给各 lane，与 mma.sync 布局严丝合缝。',
        'key_qualifiers': [
            {'qualifier': '.sync.aligned', 'meaning': '要求同一 warp 内全部 32 线程收敛执行并对齐'},
            {'qualifier': '.m16n8k16 / .m16n8k8 等', 'meaning': '指令级 M×N×K 矩阵砖块形状'},
            {'qualifier': '.row / .col / .trans', 'meaning': '操作数行列主序与 ldmatrix/stmatrix 硬件转置'},
        ],
        'related_lessons': ['learn_matrix', 'learn_mma_wgmma'],
        'subcategories': [
            {
                'id': '9.7.16.wmma',
                'title_zh': 'WMMA 透明片段指令',
                'summary': '早期的 wmma.load / wmma.store / wmma.mma（不透明 fragment 分布）。',
                'anchors': [
                    'warp-level-matrix-instructions-wmma-ld',
                    'warp-level-matrix-instructions-wmma-st',
                    'warp-level-matrix-instructions-wmma-mma',
                ],
            },
            {
                'id': '9.7.16.mma',
                'title_zh': '显式片段 MMA 与矩阵寄存器搬运',
                'summary': 'mma、mma.sp（2:4 稀疏）及配套共享内存/寄存器搬运转置指令 ldmatrix/stmatrix/movmatrix。',
                'anchors': [
                    'warp-level-matrix-instructions-mma',
                    'warp-level-matrix-instructions-ldmatrix',
                    'warp-level-matrix-instructions-stmatrix',
                    'warp-level-matrix-instructions-movmatrix',
                    'warp-level-matrix-instructions-sparse-mma',
                ],
            },
        ],
    },
    {
        'id': '9.7.17',
        'anchor': 'asynchronous-warpgroup-level-matrix-instructions',
        'domain': 'matrix_tensor',
        'title_zh': 'Warpgroup 异步矩阵 (WGMMA)',
        'title_en': 'Asynchronous Warpgroup Level Matrix Multiply-Accumulate Instructions',
        'summary': 'Hopper (sm_90a) 引入的 128 线程（4 个连续 warp）异步矩阵计算流水线：wgmma.mma_async / fence / commit_group / wait_group。',
        'compiler_focus': '注意架构边界：wgmma 是 sm_90a 专属指令，在 B300 (sm_103a) 上文档判定为排除；B300 应转向 tcgen05 指令族。',
        'key_qualifiers': [
            {'qualifier': '.m64nNkK', 'meaning': 'Warpgroup 级 M=64 固定、N=8..256 可变的大块矩阵形状'},
            {'qualifier': 'a-desc / b-desc', 'meaning': '64 位共享内存矩阵描述符，编码基址、leading/stride byte offset 与 swizzle 模式'},
        ],
        'related_lessons': ['learn_matrix', 'learn_mma_wgmma'],
    },
    {
        'id': '9.7.18',
        'anchor': 'tensorcore-5th-generation-instructions',
        'domain': 'matrix_tensor',
        'title_zh': '第五代 Tensor Core (tcgen05 / TMEM)',
        'title_en': 'TensorCore 5th Generation Family Instructions',
        'summary': 'Blackwell / B300 核心计算路径：基于 Tensor Memory (TMEM) 与 1/2 CTA 协同组（cta_group::1/2）的异步矩阵分配、搬运、计算与 mbarrier 提交体系。',
        'compiler_focus': '单线程（通常经 elect.sync 选出）即可发射 tcgen05.mma/cp/commit，无需整个 warpgroup 锁步；累加器驻留于 TMEM 而非通用寄存器，彻底释放寄存器压力。',
        'key_qualifiers': [
            {'qualifier': '.cta_group::1 / .cta_group::2', 'meaning': '单 CTA 执行或 Cluster 内相邻双 CTA 联合执行 MMA'},
            {'qualifier': '.kind::f16 / .tf32 / .f8f6f4 / .mxf8f6f4 / .mxf4 / .mxf4nvf4 / .i8', 'meaning': '第五代 Tensor Core 数据格式家族与块缩放（block scaling）种类'},
            {'qualifier': '.ws / .sp', 'meaning': 'Weight Stationary 权重驻留模式与 2:4 结构化稀疏模式'},
        ],
        'related_lessons': ['learn_matrix', 'learn_tmem', 'learn_tcgen05_pipeline'],
        'subcategories': [
            {
                'id': '9.7.18.alloc',
                'title_zh': 'TMEM 分配与释放',
                'summary': '动态申请、归还 TMEM 列空间与释放分配许可。',
                'anchors': ['tcgen05-instructions-tcgen05-alloc-dealloc-relinquish-alloc-permit'],
            },
            {
                'id': '9.7.18.tmem_ldst',
                'title_zh': 'TMEM 寄存器读写与等待',
                'summary': 'warp 协同将 TMEM 数据搬入/写出寄存器（tcgen05.ld/st）并等待完成（tcgen05.wait）。',
                'anchors': ['tcgen05-instructions-tcgen05-ld', 'tcgen05-instructions-tcgen05-st', 'tcgen05-instructions-tcgen05-wait'],
            },
            {
                'id': '9.7.18.copy',
                'title_zh': 'SMEM → TMEM 拷贝与行移位',
                'summary': 'tcgen05.cp 异步加载缩放因子/权重至 TMEM，tcgen05.shift 行下移。',
                'anchors': ['tcgen05-instructions-tcgen05-cp', 'tcgen05-instructions-tcgen05-shift'],
            },
            {
                'id': '9.7.18.mma',
                'title_zh': '第五代异步 MMA 计算',
                'summary': '常规、稀疏 (.sp) 与权重驻留 (.ws / .ws.sp) 异步矩阵乘累加。',
                'anchors': [
                    'tcgen05-mma-instructions-mma', 'tcgen05-mma-instructions-mma-sp',
                    'tcgen05-mma-instructions-mma-ws', 'tcgen05-mma-instructions-mma-ws-sp',
                ],
            },
            {
                'id': '9.7.18.sync',
                'title_zh': 'TMEM 专用栅栏与 mbarrier 提交',
                'summary': 'tcgen05.fence 管线排序与 tcgen05.commit 触发 mbarrier arrive。',
                'anchors': ['tcgen05-special-sync-operations-fence', 'tcgen-async-sync-operations-commit'],
            },
        ],
    },
    {
        'id': '9.7.19',
        'anchor': 'stack-manipulation-instructions',
        'domain': 'control_stack',
        'title_zh': '栈操作指令',
        'title_en': 'Stack Manipulation Instructions',
        'summary': '在线程私有 .local 栈帧上动态保存/恢复栈指针与动态内存分配（alloca）。',
        'compiler_focus': 'alloca 返回 .local 地址空间指针；过量或变长栈分配会增加本地内存流量并影响缓存效率。',
        'key_qualifiers': [
            {'qualifier': '.u32 / .u64', 'meaning': '与 .address_size 匹配的栈指针位宽'},
        ],
        'related_lessons': ['learn_spaces'],
    },
    {
        'id': '9.7.20',
        'anchor': 'video-instructions',
        'domain': 'arithmetic_logic',
        'title_zh': '标量与 SIMD 视频指令',
        'title_en': 'Video Instructions',
        'summary': '在 32 位寄存器上执行双 16 位（v*2）与四 8 位（v*4）打包整数算术、平均、绝对差、比较与二级合并。',
        'compiler_focus': '虽然命名为 Video，但在低比特量化与字节流处理中可用于 4x8-bit / 2x16-bit 打包运算，注意部分高架构仅由软件模拟而非原生单周期吞吐。',
        'key_qualifiers': [
            {'qualifier': '.u32 / .s32', 'meaning': '源与目标子元素有符号/无符号解释，支持每字节/半字选择掩码'},
            {'qualifier': '.add / .min / .max', 'meaning': '标量视频指令可选的第二级归并操作'},
        ],
        'related_lessons': ['learn_arithmetic'],
    },
    {
        'id': '9.7.21',
        'anchor': 'miscellaneous-instructions',
        'domain': 'texture_misc',
        'title_zh': '杂项与寄存器调控',
        'title_en': 'Miscellaneous Instructions',
        'summary': '调试断点 brkpt、纳秒休眠 nanosleep、性能监控事件 pmevent、异常陷阱 trap 与动态寄存器配额调控 setmaxnreg。',
        'compiler_focus': 'setmaxnreg.inc / .dec 在 warp-specialized 内核（如生产者 warp 释放寄存器给消费者 warpgroup）中极其关键，可打破静态每线程寄存器上限瓶颈。',
        'key_qualifiers': [
            {'qualifier': '.inc / .dec (setmaxnreg)', 'meaning': '增加或释放当前 warp 的每线程最大寄存器配额'},
            {'qualifier': '.mask (pmevent)', 'meaning': '按位掩码同时触发多个硬件性能监控事件'},
        ],
        'related_lessons': ['learn_predication_divergence', 'learn_registers'],
    },
]


def parse_syntax_profile(text):
    """Extract syntax form count, qualifier definitions, and optional inline qualifiers."""
    lines = [line.rstrip() for line in text.splitlines()]
    qualifier_defs = {}
    current_def = None
    form_lines = []

    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith('//') or set(stripped) <= {'-'}:
            current_def = None
            continue
        def_match = re.match(r'^(\.[A-Za-z0-9_:]+(?:\s*=\s*\.[A-Za-z0-9_:]+)*)\s*=\s*(.+)$', stripped)
        if def_match:
            lhs = [x.strip() for x in def_match.group(1).split('=')]
            rhs = def_match.group(2)
            current_def = lhs
            for name in lhs:
                qualifier_defs.setdefault(name, [])
                qualifier_defs[name].extend(re.findall(r'\.[A-Za-z0-9_:]+', rhs))
            if ';' in rhs or '}' in rhs:
                current_def = None
            continue
        if current_def:
            for name in current_def:
                qualifier_defs[name].extend(re.findall(r'\.[A-Za-z0-9_:]+', stripped))
            if ';' in stripped or '}' in stripped:
                current_def = None
            continue
        if stripped.endswith(';') or re.match(r'^[@{a-z]', stripped):
            form_lines.append(stripped)

    # Deduplicate qualifier values while preserving order
    clean_defs = {}
    for k, vals in qualifier_defs.items():
        seen = []
        for v in vals:
            if v not in seen:
                seen.append(v)
        clean_defs[k] = seen

    inline_opts = []
    for opt in re.findall(r'\{\s*(\.[A-Za-z0-9_:,.\s]+?)\s*\}', text):
        tok = opt.strip()
        if tok not in inline_opts and len(tok) <= 40:
            inline_opts.append(tok)

    # Count distinct statement templates (lines ending with ';')
    semicolons = sum(1 for l in form_lines if ';' in l)
    form_count = max(1, semicolons) if form_lines else 1
    return {
        'form_count': form_count,
        'qualifier_defs': clean_defs,
        'inline_qualifiers': inline_opts[:12],
    }


def infer_granularity(anchor, section_number, syntax_text):
    """Classify execution granularity from instruction semantics and qualifiers."""
    if section_number.startswith('9.7.17.'):
        return 'Warpgroup 异步 (128 线程)'
    if section_number.startswith('9.7.18.'):
        if any(x in anchor for x in ('tcgen05-ld', 'tcgen05-st', 'tcgen05-wait', 'tcgen05-alloc')):
            return 'Warp / CTA 协同 (TMEM)'
        return '单线程发射 · CTA_Group 异步'
    if section_number.startswith('9.7.16.'):
        return 'Warp 协同 (32 线程)'
    if any(x in anchor for x in ('cp-async-bulk', 'tensormap-replace', 'tensormap-cp-fenceproxy', 'applypriority-async-bulk')):
        return '单线程发起 · 异步引擎 (TMA/Bulk)'
    if any(x in anchor for x in ('bar-warp-sync', 'vote-sync', 'match-sync', 'redux-sync', 'elect-sync', 'shfl-sync', 'shfl', 'vote', 'activemask')):
        return 'Warp 协同 (32 线程)'
    if any(x in anchor for x in ('barrier-cluster', 'clusterlaunchcontrol')):
        return 'Cluster 协同'
    if anchor == 'parallel-synchronization-and-communication-instructions-bar':
        return 'CTA 协同'
    if '.sync' in syntax_text and 'membermask' in syntax_text:
        return 'Warp 协同 (32 线程)'
    if section_number.startswith('9.7.11.'):
        return '异步 Fabric 引擎'
    if section_number.startswith(('9.7.14.', '9.7.19.', '9.7.21.')):
        return '控制流 / 线程环境'
    return '单线程 SIMT'


def build_taxonomy(root=ROOT / 'data/ptx'):
    instructions = json.loads((root / 'instructions.json').read_text())
    syntax = json.loads((root / 'syntax.json').read_text())['entries']

    cat_by_id = {c['id']: c for c in CATEGORIES}
    sub_by_anchor = {}
    for c in CATEGORIES:
        for sub in c.get('subcategories', []):
            for a in sub['anchors']:
                sub_by_anchor[a] = (c['id'], sub['id'], sub['title_zh'])

    inst_map = {}
    for inst in instructions:
        anchor = inst['anchor']
        parts = [p for p in inst['section_number'].split('.') if p]
        if len(parts) < 3 or parts[:2] != ['9', '7']:
            raise ValueError(f'Unexpected instruction section: {inst["section_number"]} ({anchor})')
        cat_id = f'9.7.{parts[2]}'
        cat = cat_by_id.get(cat_id)
        if not cat:
            raise ValueError(f'Missing category definition for {cat_id}')

        sub_info = sub_by_anchor.get(anchor)
        if sub_info and sub_info[0] != cat_id:
            raise ValueError(f'Subcategory mismatch for {anchor}: {sub_info[0]} != {cat_id}')

        stext = syntax[anchor]['text']
        profile = parse_syntax_profile(stext)
        inst_map[anchor] = {
            'domain': cat['domain'],
            'category': cat_id,
            'subcategory': sub_info[1] if sub_info else None,
            'subcategory_title': sub_info[2] if sub_info else None,
            'granularity': infer_granularity(anchor, inst['section_number'], stext),
            **profile,
        }

    # Verify every anchor listed in subcategories is a real instruction
    all_anchors = {i['anchor'] for i in instructions}
    for c in CATEGORIES:
        seen_sub = set()
        for sub in c.get('subcategories', []):
            for a in sub['anchors']:
                if a not in all_anchors:
                    raise ValueError(f'Unknown subcategory anchor: {a}')
                if a in seen_sub:
                    raise ValueError(f'Duplicate subcategory anchor: {a}')
                seen_sub.add(a)
        # Ensure if category defines subcategories, all instructions in that category are covered
        if c.get('subcategories'):
            cat_anchors = {a for a, info in inst_map.items() if info['category'] == c['id']}
            missing = cat_anchors - seen_sub
            if missing:
                raise ValueError(f'Category {c["id"]} subcategories missing anchors: {sorted(missing)}')

    return {
        'schema_version': 'ackb.ptx-taxonomy.v1',
        'domains': DOMAINS,
        'categories': CATEGORIES,
        'instructions': inst_map,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data/ptx')
    args = parser.parse_args()
    data = build_taxonomy(args.data_dir)
    out = args.data_dir / 'taxonomy.json'
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'Wrote {out} ({len(data["domains"])} domains, {len(data["categories"])} categories, {len(data["instructions"])} instructions)')


if __name__ == '__main__':
    main()
