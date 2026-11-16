"""Conservative navigation paths from explicit CCEC transfer names."""
import re

SPACES = {'gm': 'GM', 'ubuf': 'UB', 'cbuf': 'L1'}


def transfer_for(name):
    match = re.search(r'(?:^|_)(gm|ubuf|cbuf)_to_(gm|ubuf|cbuf)(?:_|$)', name)
    if not match:
        return None
    source, destination = match.groups()
    return {'id': f'transfer:{source}:{destination}',
            'label': f'{SPACES[source]} → {SPACES[destination]}',
            'search_alias': f'{SPACES[source]}2{SPACES[destination]}',
            'source': source, 'destination': destination,
            'basis': 'explicit_name_tokens', 'spelling': name}
