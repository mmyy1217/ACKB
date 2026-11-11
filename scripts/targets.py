"""Extract target metadata without executing the installed toolchain."""
import argparse
import configparser
import hashlib
import json
import re
from pathlib import Path


def extract(toolkit):
    targets = []
    root = toolkit / 'x86_64-linux/data/platform_config'
    for path in sorted(root.glob('*.ini')):
        config = configparser.ConfigParser(strict=False, interpolation=None)
        config.read(path)
        if not config.has_section('version'):
            raise ValueError(f'Missing version section: {path}')
        version = config['version']
        arch = version.get('NpuArch', '')
        if not arch.isdigit():
            raise ValueError(f'Missing or invalid NpuArch in {path}: {arch!r}')
        targets.append({'chip': version.get('SoC_version', path.stem),
                        'family': version.get('Short_SoC_version', ''),
                        'aic_version': version.get('AIC_version', ''),
                        'npu_arch': int(arch),
                        'cores': {key: version[key] for key in ('ccec_aic_version', 'ccec_aiv_version', 'ccec_cube_version', 'ccec_vector_version') if key in version},
                        'source': {'file': path.relative_to(toolkit).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'section': 'version', 'package_verified': False}})
    if not targets:
        raise ValueError('No platform targets with NpuArch found')
    return targets


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--toolkit', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    expected = re.fullmatch(r'(\d+\.\d+\.\d+)~weekly\.(\d{8})\.\d+', args.version)
    metadata = (args.toolkit / 'share/info/bisheng-compiler/version.info').read_text()
    if not expected or 'Version=' + expected[1] + '\n' not in metadata or 'timestamp=' + expected[2] + '_' not in metadata:
        raise ValueError('Target metadata toolkit does not match requested weekly version')
    args.output.write_text(json.dumps({'version': args.version, 'targets': extract(args.toolkit)}, ensure_ascii=False, indent=2) + '\n')
