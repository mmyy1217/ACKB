"""Join the two independently pinned indices with versioned compile observations."""


def add_correspondence(dialect, llvm, audit):
    if (dialect['source']['commit'] != audit['dialect_commit']
            or llvm['version'] != audit['index_version']):
        raise ValueError('CANN correspondence evidence version mismatch')
    by_name = {op['name']: op for op in llvm['ops']}
    dialect['cann_versions'] = {key: audit[key] for key in ('index_version', 'compiler_version', 'target')}
    for item in dialect['intrinsics']:
        name = item['name']
        target = by_name.get(name)
        match = 'exact'
        if target is None:
            prefix = name
            while '.' in prefix:
                prefix = prefix.rsplit('.', 1)[0]
                candidate = by_name.get(prefix)
                if candidate and candidate.get('registry', {}).get('overloaded'):
                    target = candidate
                    break
            match = 'overload_base'
        evidence = {}
        if target:
            evidence.update(kind=match, name=target['name'], id=target['id'],
                            identity=target['identity_status'])
        if name in audit['installation_hits']:
            evidence['package_file'] = audit['installation_hits'][name]
        if name in audit['results']:
            evidence['experiment'] = audit['results'][name]
        item['cann_correspondence'] = evidence
