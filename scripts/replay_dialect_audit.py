"""Replay the audited dialect forms on a host cce-translate, without CANN or a device."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


AUDIT = Path(__file__).resolve().parents[1] / 'data/cce_dialect/translation-audit.json'
CALL = re.compile(r'\bcall\b[^\n]*?@([^ (]+)\(')


def matches(case, result):
    if 'diagnostic' in case:
        return result.returncode != 0 and case['diagnostic'] in result.stderr
    if result.returncode:
        return False
    calls = CALL.findall(result.stdout)
    if case.get('helper_only'):
        function = re.search(r'^define [^\n]+\{\n(.*?)^}', result.stdout, re.M | re.S)
        return function and case['name'] in calls and case['name'] not in CALL.findall(function[1])
    if 'emitted_instead' in case:
        return case['emitted_instead'] in calls and case['name'] not in calls
    return case['call'] in [line.strip() for line in result.stdout.splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('translator', type=Path)
    args = parser.parse_args()
    tool = args.translator.resolve()
    cases = json.loads(AUDIT.read_text())['cases']
    failures = []
    with tempfile.TemporaryDirectory() as cwd:
        for case in cases:
            result = subprocess.run([tool, '--cce-to-backend', *case.get('flags', [])],
                                    cwd=cwd, input=case['mlir'], text=True, capture_output=True, timeout=30)
            if not matches(case, result):
                failures.append(case['name'])
    if failures:
        raise SystemExit('Unexpected lowering: ' + ', '.join(failures))
    print(f'Reproduced all {len(cases)} lowering outcomes.')


if __name__ == '__main__':
    main()
