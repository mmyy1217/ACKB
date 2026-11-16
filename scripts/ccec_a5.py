"""Fixed A5 interface summaries; keep source declarations and builtin identities separate."""
from collections import defaultdict
from database import stable_id
from ccec_ops import Ops
from ccec_transfer import transfer_for
from ccec_calls import load_calls

CHIP = 'Ascend950PR_9579'


def interfaces(db):
    index = Ops(db)
    calls = load_calls(db)
    direct = set(calls['direct_entry_ids'])
    target = db.target(chip=CHIP)
    groups = defaultdict(list)
    for r in db.records:
        if index.model['record_layers'].get(r['id'], {}).get('layer') == 'wrapper' or r['id'] in direct:
            groups[(r['namespace'], r['name'])].append(r)
    items = []
    for (namespace, name), records in sorted(groups.items()):
        conditions = {r['id']: db.condition(r, target) for r in records}
        values = conditions.values()
        condition = 'matches' if 'matches' in values else 'unknown' if 'unknown' in values else 'excluded'
        relevant = [r for r in records if conditions[r['id']] != 'excluded']
        items.append({'id': stable_id('ccec_interface_', [namespace, name]), 'name': name,
                      'namespace': namespace, 'chip': CHIP, 'npu_arch': 3510,
                      'transfer': transfer_for(name),
                      'condition': condition, 'support': 'unverified',
                      'entry_kind': 'direct_alias' if any(r['id'] in direct for r in records) else 'wrapper',
                      'record_conditions': conditions,
                      'record_ids': [r['id'] for r in relevant],
                      'op_ids': sorted({oid for r in relevant for oid in index.model['record_layers'][r['id']]['op_ids']}),
                      'relation_scope': 'potential_body_references_not_overload_or_runtime_resolution'})
    return items
