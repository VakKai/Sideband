import csv
from importlib import import_module
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np

import quickstart as demo


class ReceiverTests(unittest.TestCase):
    def test_known_fcs_and_stuffed_frame(self):
        self.assertEqual(demo.fcs(b'123456789'), bytes.fromhex('6e90'))
        payload = demo.PAYLOAD + b'\xff\xff'
        bits = demo.stuff(payload + demo.fcs(payload))
        self.assertEqual(demo.tracking.d.decode_frame(bits), payload)
        bits[0] ^= 1
        self.assertIsNone(demo.tracking.d.decode_frame(bits))

    def test_vector_frame_decoding_checks_stuffing(self):
        payload = demo.PAYLOAD + bytes.fromhex('ffffffff')
        stuffed = demo.stuff(payload + demo.fcs(payload))
        bits = np.array(stuffed, dtype=np.uint8)
        self.assertEqual(demo.tracking.d.decode_frame(bits), payload)
        invalid = np.concatenate((np.ones(6, dtype=np.uint8), bits))
        self.assertIsNone(demo.tracking.d.decode_frame(invalid))

    def test_confidence_retry_repairs_one_symbol(self):
        header, kind = demo.receiver.HOUSEKEEPING[101]
        payload = demo.receiver.AX25_UI_HEADER + header + bytes(6) + bytes([kind]) + bytes(73)
        bits = np.array(demo.stuff(payload + demo.fcs(payload)), dtype=bool)
        confidence = np.ones(len(bits) + 18)
        level = 120
        bits[level + demo.receiver.ERROR_OFFSETS] ^= True
        self.assertIsNone(demo.tracking.d.decode_frame(bits))
        confidence[level] = 0
        self.assertEqual(demo.receiver.retry_frame(
            bits, confidence, 0, len(bits), demo.tracking.d), [(payload, 1)])

    def test_synthetic_burst_recovers_at_different_symbol_phases(self):
        samples = demo.synthetic_iq()
        for delay in (0, 5):
            with self.subTest(delay=delay):
                frames = demo.decode(np.roll(samples, delay, axis=0))
                self.assertEqual([payload for _, payload in frames], [demo.PAYLOAD])
                self.assertAlmostEqual(frames[0][0], 2.026 + delay / demo.RATE, delta=.002)

    def test_overlap_deduplication_preserves_retransmission(self):
        frames = []
        for seconds in (2.0, 2.001, 2.12):
            demo.receiver.add_occurrence(frames, seconds, demo.PAYLOAD)
        self.assertEqual([seconds for seconds, _ in frames], [2.0, 2.12])

    def test_pass_summary_matches_polarizations_and_keeps_retransmissions(self):
        summary = import_module('summarize-rsp03-final')
        with TemporaryDirectory() as folder:
            root = Path(folder)
            results = root / 'results'
            results.mkdir()
            (results / 'rsp03-final-manifest.csv').write_text(
                'observation,pass_start_utc\n1,pass-a\n2,pass-a\n'
            )
            (results / 'rsp03-final-packets.csv').write_text(
                'observation,mode,seconds,sha256,station_match\n'
                '1,confidence,2.000,abc,True\n2,confidence,2.030,abc,True\n'
                '1,confidence,2.120,abc,True\n2,confidence,2.125,abc,True\n'
                '2,confidence,2.125,xyz,False\n'
            )
            (results / 'rsp03-final-timings.csv').write_text(
                'observation,mode,local_replay_seconds\n1,confidence,1.5\n'
                '2,confidence,2.5\n'
            )
            with patch.object(summary, 'ROOT', root), patch.object(sys, 'argv', ['', str(results)]):
                summary.main()
            with (results / 'rsp03-final-passes.csv').open() as stream:
                rows = {row['mode']: row for row in csv.DictReader(stream)}
            self.assertEqual(rows['hard']['station_matched_occurrences'], '0')
            confidence = rows['confidence']
            self.assertEqual(confidence['station_matched_occurrences'], '2')
            self.assertEqual(confidence['recording_matches'], '4')
            self.assertEqual(confidence['unmatched_recording_occurrences'], '1')
            self.assertEqual(confidence['replay_seconds'], '4.000000')


if __name__ == '__main__':
    unittest.main()
