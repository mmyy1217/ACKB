"""Transfer paths are source names, never inferred hardware support."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccec_transfer import transfer_for


class TransferTests(unittest.TestCase):
    def test_direction_and_aliases(self):
        self.assertEqual(transfer_for('copy_gm_to_cbuf_align_v2')['label'], 'GM → L1')
        self.assertEqual(transfer_for('__builtin_cce_copy_ubuf_to_gm')['search_alias'], 'UB2GM')
        self.assertEqual(transfer_for('copy_gm_to_ubuf')['id'], 'transfer:gm:ubuf')
        self.assertEqual(transfer_for('copy_cbuf_to_ubuf')['source'], 'cbuf')

    def test_no_guessed_or_partial_paths(self):
        for name in ['copy_data', 'load2d', 'nddma_out_to_ub', 'copy_gm_to_cbuffer', 'notgm_to_ubuf']:
            self.assertIsNone(transfer_for(name), name)
