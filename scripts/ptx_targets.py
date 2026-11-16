"""Evaluate documented PTX target alternatives without changing source snapshots."""
from collections import Counter
from copy import deepcopy
from ptx_index import sm_parts

TARGETS = ('sm_103', 'sm_103f', 'sm_103a', 'sm_89')
DEFAULT_TARGET = 'sm_103a'


def judge(statement, target):
    relation = statement['relation']
    if relation in ('performance_note', 'cross_reference', 'legacy_target_limit', 'advisory'):
        return 'not_applicable'
    if relation == 'all_architectures':
        return 'yes'
    current = sm_parts(target)
    required = sm_parts(statement.get('sm') or '')
    if not current or not required:
        return 'unknown'
    if relation == 'excluded_minimum':
        return 'no' if current[:2] >= required[:2] else 'yes'
    def accepts(token):
        rule = sm_parts(token)
        if not rule:
            return False
        if rule[2] == 'a':
            return target == token
        if rule[2] == 'f':
            return current[2] in ('f', 'a') and current[0] == rule[0] and current[1] >= rule[1]
        if relation == 'exact_sm':
            return current[:2] == rule[:2]
        return current[:2] >= rule[:2]
    if relation in ('exact_sm', 'minimum_sm'):
        return 'yes' if any(accepts(t) for t in [statement['sm'], *statement.get('aliases', [])]) else 'no'
    return 'unknown'


def assess(record, target=DEFAULT_TARGET):
    if target not in TARGETS:
        raise ValueError('Unsupported target: ' + target)
    block = record.get('target_isa', {})
    statements = deepcopy(block.get('statements', []))
    groups = {}
    entry_denied = False
    for s in statements:
        s['applies'] = judge(s, target)
        if s['applies'] == 'not_applicable':
            continue
        groups.setdefault(s.get('subject'), []).append(s)
        if s.get('scope') == 'entry' and s['relation'] == 'excluded_minimum' and s['applies'] == 'no':
            entry_denied = True
    statuses = []
    for group in groups.values():
        if any(s['relation'] == 'excluded_minimum' and s['applies'] == 'no' for s in group):
            statuses.append('no')
        elif any(s['applies'] == 'unknown' for s in group):
            statuses.append('unknown')
        else:
            statuses.append('yes' if any(s['applies'] == 'yes' for s in group) else 'no')
    if not statuses or block.get('unparsed') or 'unknown' in statuses:
        support = 'unknown'
    elif entry_denied or all(s == 'no' for s in statuses):
        support = 'documented_not_supported'
    elif all(s == 'yes' for s in statuses) and not record.get('sm_89', {}).get('deferred_detail'):
        support = 'documented_supported'
    else:
        support = 'partial'
    return {'target': target, 'support': support, 'statements': statements,
            'rule': 'documented_target_alternatives_v1', 'verification': 'documentation_only'}


def counts(records, target=DEFAULT_TARGET):
    result = Counter(assess(r, target)['support'] for r in records if r['kind'] == 'instruction')
    return dict(result)
