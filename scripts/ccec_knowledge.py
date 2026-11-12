#!/usr/bin/env python3
"""Build source-linked CCEC topics and a complete scanned-header builtin index."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from catalog import ROOT, VERSION, validate

TOPICS = [
    ('execution', '执行入口与核角色', ['__vector__', '__cube__', '__mix__', '__simt_vf__', '__global__'],
     '头文件用属性宏表达入口与核角色；__vector__ 的定义有条件分支，不能仅凭宏名确定执行核。SIMT 入口标记与普通 aicore 声明也应分别记录。',
     ['完整线程调度模型与核间拓扑尚待官方架构资料补充。', '宏定义存在不代表 950PR 下所有入口都可编译。']),
    ('memory', '地址空间与存储接口', ['__gm__', '__ubuf__', '__cbuf__', '__ca__', '__cb__', '__cc__', '__private__'],
     '地址空间宏分别展开为 CCE 属性。生成签名时应保留这些限定符；不同属性的指针不能在知识层当作同一接口类型。',
     ['各空间的设备容量、对齐及跨空间转换合法性未由这些宏定义证明。']),
    ('movement', '数据搬运与参数', ['copy_gm_to_cbuf', 'copy_gm_to_ubuf', 'copy_ubuf_to_gm'],
     'copy_gm_to_cbuf 同时有打包 config 与分立参数形式。查询应保留各声明的完整参数和条件，不能把名字相同视作参数可以互换。',
     ['参数单位、范围、对齐和不同数据布局下的解释仍需逐项核验。']),
    ('synchronization', '流水与同步入口', ['pipe_t', 'set_flag', 'wait_flag', 'pipe_barrier'],
     'pipe_t 枚举与同步入口是不同层次的证据。当前 set_flag、wait_flag、pipe_barrier 声明使用可变参数并关联 builtin，省略号不能提供精确调用约束。',
     ['事件配对、可见性与必要同步规则未通过编译或设备实验确认。']),
    ('types', '类型、精度与布局', ['half', 'half2', 'bfloat16_t', 'vector_bool', 'vector_f32'],
     '类型声明、向量类型和操作接口分别建索引。名称中的精度和形状需要回到类型与重载定义核对，不能由分类标签推定数据布局。',
     ['物理布局、数值精度误差和舍入行为需逐接口补充。']),
    ('compute', '计算接口与重载', ['__abs', 'mad', 'mmad'],
     '计算接口通过重载、模板或 builtin alias 暴露。跨文件的同名声明仍保留各自来源；函数名不是硬件指令编码的身份证明。',
     ['吞吐量、延迟和实际机器指令序列尚无测量。']),
    ('lifecycle', '弃用与兼容入口', ['DEPRECATED', 'DEPRECATED_AFTER_V210'],
     '弃用标记有无条件和条件定义。DEPRECATED_AFTER_V210 的展开受架构分支控制，名称包含 Legacy 不能替代对具体标记的核对。',
     ['首次弃用版本和逐项替代接口需要其他版本及文档证据。']),
    ('control', '寄存器与控制', ['get_block_idx', 'get_block_num', 'set_ctrl', 'get_ctrl'],
     '控制入口按名称建立可追溯导航，使用前仍需核对声明形式、参数与目标条件；名称规则仅用于发现。',
     ['控制位含义、运行时副作用及跨核作用范围尚未评审。'])
]


def build(source, output):
    data = json.loads(source.read_text())
    validate(data)
    files = {x['path']: x for x in data['files']}
    records = data['records']
    def evidence(r):
        return {'record_id': r['id'], **r['source'], 'sha256': files[r['source']['file']]['sha256'],
                'package_verified': bool(data['source']['package_verified'])}
    topics = []
    for key, title, seeds, body, unknowns in TOPICS:
        matched = [r for r in records if r['name'] in seeds]
        topics.append({'id': 'ccec_topic_' + key, 'backend': 'ccec', 'kind': 'execution_model',
                       'title': title, 'depth': 'selected', 'body': body, 'seed_names': seeds,
                       'missing_seeds': [n for n in seeds if not any(r['name'] == n for r in matched)],
                       'record_ids': [r['id'] for r in matched], 'evidence': [evidence(r) for r in matched],
                       'unknowns': unknowns, 'verification': {'compile': 'unverified', 'runtime': 'unverified'},
                       'model_scope': 'header_surface_only', 'experiments': []})
    builtins = []
    for name in data['report']['raw_builtin_names']:
        linked = [r for r in records if name in r['builtins']]
        builtins.append({'id': 'ccec_builtin_' + hashlib.sha256(name.encode()).hexdigest()[:24],
                         'name': name, 'kind': 'builtin_reference', 'record_ids': [r['id'] for r in linked],
                         'status': 'linked_header_reference' if linked else 'unlinked_header_reference'})
    result = {'schema_version': 'ackb.ccec-index.v1', 'backend': 'ccec', 'version': data['version'],
              'source_catalog_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'target': 'Ascend950PR_9579', 'topics': topics, 'builtins': builtins,
              'coverage': {'headers': len(files), 'records': len(records), 'record_kinds': dict(Counter(r['kind'] for r in records)),
                           'topics': len(topics), 'builtin_references': len(builtins),
                           'unlinked_builtin_references': sum(not b['record_ids'] for b in builtins),
                           'unresolved_declarations': len(data['report']['unresolved']), 'experiments': 0},
              'limitations': ['Header builtin references are not a compiler-internal builtin inventory.',
                              'Execution-model notes cover exposed headers, not complete hardware semantics.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'data' / VERSION / 'catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/ccec/knowledge.json')
    args = parser.parse_args()
    result = build(args.data, args.output)
    print(json.dumps(result['coverage']))
