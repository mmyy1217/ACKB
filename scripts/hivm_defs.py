"""Import the Issue 33 workbook's named intrinsic definitions."""
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

OUTPUT = Path(__file__).resolve().parents[1] / 'data/hivm_defs/index.json'


def read_rows(archive, number, strings):
    sheet = ET.fromstring(archive.read(f'xl/worksheets/sheet{number}.xml'))
    for row in sheet.findall('.//{*}sheetData/{*}row'):
        cells = {}
        for cell in row.findall('{*}c'):
            value = cell.findtext('{*}v', '')
            if cell.get('t') == 's':
                value = strings[int(value)]
            elif cell.get('t') == 'inlineStr':
                value = ''.join(cell.find('{*}is').itertext())
            cells[re.sub(r'\d+', '', cell.attrib['r'])] = value
        if cells.get('A', '').isdigit():
            yield int(row.attrib['r']), cells


def extract(path):
    with ZipFile(path) as archive:
        strings = ([''.join(node.itertext()) for node in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
                   if 'xl/sharedStrings.xml' in archive.namelist() else [])
        probes = {(r['A'], r['B']): r for _, r in read_rows(archive, 2, strings)}
        records = []
        names = set()
        empty = 0
        for row, item in read_rows(archive, 1, strings):
            lines = item.get('C', '').splitlines()
            if not lines:
                empty += 1
                continue
            name, signature, tag = lines
            if not re.fullmatch(r'int_hivm_\w+', name) or name in names:
                raise ValueError(f'Unexpected or repeated definition at C{row}: {name}')
            names.add(name)
            record = dict(name=name, family=item['B'], signature=signature, tag=tag,
                          number=int(item['A']), row=row)
            probe = probes.pop((item['A'], name), None)
            if probe:
                record['probe'] = dict(result=probe['F'], ir=probe['G'], assembly=probe['H'])
            records.append(record)
        if probes:
            raise ValueError('Probe rows do not match the definition sheet')
    return dict(schema='ackb.hivm-defs.v1', source=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                empty_rows=empty, probe_toolchain='CANN 9.1.0 / CCEC 15.0.5', records=records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    model = extract(parser.parse_args().workbook)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(model, ensure_ascii=False, indent=2) + '\n')
