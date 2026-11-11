"""Compare declaration inventories without claiming a first introduction date."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from compatibility import analyze


def compare(before, after):
    def inventory(data):
        groups = defaultdict(set)
        for r in analyze(data)['records']:
            key = json.dumps([r.get('namespace', ''), r['name'], r['kind']], ensure_ascii=False)
            groups[key].add(json.dumps({'signature': r['signature'], 'conditions': sorted(r['conditions']),
                                       'deprecation': r['deprecation']['status']}, ensure_ascii=False, sort_keys=True))
        return groups
    old, new = inventory(before), inventory(after)
    return {'before': before['version'], 'after': after['version'],
            'extractor_revisions': [before.get('extractor_revision'), after.get('extractor_revision')],
            'added': [json.loads(k) for k in sorted(new.keys() - old.keys())],
            'removed': [json.loads(k) for k in sorted(old.keys() - new.keys())],
            'changed': [{'identity': json.loads(k), 'before': [json.loads(x) for x in sorted(old[k])],
                         'after': [json.loads(x) for x in sorted(new[k])]} for k in sorted(old.keys() & new.keys()) if old[k] != new[k]]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(json.loads(args.before.read_text()), json.loads(args.after.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
