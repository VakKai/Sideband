#!/usr/bin/env python3
"""Compare hard decisions and bounded single-symbol retries on development passes."""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from scipy.signal import fftconvolve

RATES = (-200, -100, 0)
PHASES = np.arange(0, 6, 0.25)
FLAG_FILTER = [-1, 1, 1, 1, 1, 1, 1, -1]
RETRY_LIMIT = 8
# A wrong level affects two NRZI bits, each with three G3RUH taps.
ERROR_OFFSETS = np.array([-18, -17, -6, -5, -1, 0])
# Published RSP-03 housekeeping types, with their AX.25 UI header included.
HOUSEKEEPING = {101: (b'\x00\x18\x4a\x80\x01', 2),
                200: (b'\x00\x18\xad\x80\x01', 1),
                250: (b'\x00\x18\xdf\x80\x01', 3)}
AX25_UI_HEADER = bytes.fromhex('94a662b2a0826094a662b29eb2e103f0')


def load_decoder(root):
    spec = importlib.util.spec_from_file_location('diagnostic', root / 'replay-rsp03.py')
    decoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(decoder)
    return decoder


def is_housekeeping(payload):
    format_fields = HOUSEKEEPING.get(len(payload))
    if format_fields is None or not payload.startswith(AX25_UI_HEADER):
        return False
    header, packet_type = format_fields
    return payload[16:21] == header and payload[27] == packet_type


def add_occurrence(occurrences, seconds, payload):
    if not any(payload == old and abs(seconds - time) < .002 for time, old in occurrences):
        occurrences.append((seconds, payload))


def retry_frame(bits, confidence, first, stop, decoder):
    """Try one uncertain level, with both observed HDLC flags left intact."""
    if not 800 <= stop - first <= 2500:
        return []
    # All six flipped bits must lie strictly inside the stuffed frame.
    first_level = first + 18
    if first_level >= stop:
        return []
    scores = confidence[first_level:stop]
    ranking = np.argsort(scores, kind='stable')[:RETRY_LIMIT]
    candidate = bits[first:stop].copy()
    accepted = []
    for rank, index in enumerate(ranking, 1):
        errors = index + 18 + ERROR_OFFSETS
        candidate[errors] ^= True
        payload = decoder.decode_frame(candidate)
        candidate[errors] ^= True
        if payload is not None and is_housekeeping(payload):
            accepted.append((payload, rank))
    # Ambiguous repairs are discarded at this timing hypothesis.
    return accepted if len(accepted) == 1 else []


def symbol_level_offset(samples, begin, end, rate, taps):
    """Estimate the discriminator midpoint from energetic 20 ms blocks."""
    block = rate // 50
    count = (end - begin) // block
    if not count:
        return 0.
    x = samples[begin:begin + count * block].astype(np.float32)
    iq = (x[:, 0] + 1j * x[:, 1]) / 32767
    filtered = fftconvolve(iq, taps, mode='same')
    power = np.mean(np.abs(filtered.reshape(count, block)) ** 2, axis=1)
    active = power >= 0.5 * power.max()
    discriminator = np.angle(filtered[1:] * filtered[:-1].conj())
    # Exclude the last sample in each block, whose phase step crosses blocks.
    values = np.pad(discriminator, (0, 1)).reshape(count, block)[active, :-1]
    low, high = np.quantile(values, [0.20, 0.80], axis=1)
    return float(np.median((low + high) / 2) * rate / (2 * np.pi))


def replay(samples, bursts, decoder, shift_hz, frequency=None, symbol_levels=False):
    hard = []
    repaired = []
    ranks = {}
    retry_seconds = 0.
    estimates = []
    started = perf_counter()
    for burst in bursts:
        begin = round(float(burst['start_seconds']) * decoder.RATE)
        end = round(float(burst['stop_seconds']) * decoder.RATE)
        correction = shift_hz
        if frequency is not None:
            active = frequency[round(begin / 1152):round(end / 1152)]
            offsets = [float(row['raw_centroid_hz']) for row in active
                       if float(row['power_ratio']) > 10**.2]
            # The development sweep supports trying only small translations.
            correction = float(np.clip(-np.median(offsets), -50, 50)) if offsets else 0.
        if symbol_levels:
            offset = symbol_level_offset(samples, begin, end, decoder.RATE, decoder.FILTER)
            correction = float(np.clip(-offset, -50, 50))
            estimates.append((begin / decoder.RATE, end / decoder.RATE, offset, correction))
        for start in range(begin, end, decoder.RATE // 2):
            x = samples[start:min(start + decoder.RATE, end)].astype(np.float32)
            if len(x) < 100:
                continue
            iq = (x[:, 0] + 1j * x[:, 1]) / 32767
            # Use the same precision as the existing frequency bank's zero arm.
            phase = 2 * np.pi * correction * (np.arange(len(iq)) + start - begin) / decoder.RATE
            z = fftconvolve(iq * np.exp(1j * phase), decoder.FILTER, mode='same')
            y = np.convolve(np.angle(z[1:] * z[:-1].conj()), [.5, .5], mode='same')
            axis = np.arange(len(y))
            for ppm in RATES:
                spacing = 6 * (1 + ppm * 1e-6)
                for phase in PHASES:
                    positions = np.arange(phase, len(y) - 1, spacing)
                    values = np.interp(positions, axis, y)
                    levels = values > 0
                    nrzi = levels[1:] == levels[:-1]
                    bits = nrzi[17:] ^ nrzi[5:-12] ^ nrzi[:-17]
                    flags = np.flatnonzero(
                        np.convolve(bits.astype(np.int8), FLAG_FILTER, mode='valid') == 6
                    )
                    confidence = np.abs(values)
                    for left, right in zip(flags, flags[1:]):
                        if right - left > 2500:
                            continue
                        seconds = start / decoder.RATE + positions[left + 18] / decoder.RATE
                        payload = decoder.decode_frame(bits[left + 8:right])
                        if payload is not None:
                            add_occurrence(hard, seconds, payload)
                            continue
                        before_retry = perf_counter()
                        for payload, rank in retry_frame(bits, confidence, left + 8, right, decoder):
                            add_occurrence(repaired, seconds, payload)
                            ranks[payload] = min(rank, ranks.get(payload, RETRY_LIMIT))
                        retry_seconds += perf_counter() - before_retry
    elapsed = perf_counter() - started
    return hard, repaired, ranks, elapsed, retry_seconds, estimates


def replay_selective(samples, bursts, decoder, min_peak_ratio=10.):
    """Keep the zero-shift output and retry sufficiently prominent bursts."""
    baseline = replay(samples, bursts, decoder, 0)
    selected = [burst for burst in bursts if float(burst['peak_power_ratio']) >= min_peak_ratio]
    corrected = replay(samples, selected, decoder, 0, symbol_levels=True)
    return baseline, corrected, len(selected)


def combined_occurrences(hard, repaired):
    combined = hard.copy()
    for seconds, payload in repaired:
        add_occurrence(combined, seconds, payload)
    return combined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--observation', action='append', required=True)
    correction = parser.add_mutually_exclusive_group()
    correction.add_argument('--shift', type=int, default=0)
    correction.add_argument('--centroid', action='store_true',
                            help='Use the clipped per-burst spectral median')
    correction.add_argument('--symbol-levels', action='store_true',
                            help='Use the clipped discriminator midpoint per burst')
    correction.add_argument('--selective', action='store_true',
                            help='Keep zero shift and retry bursts with peak band-power ratio >= 10')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    decoder = load_decoder(args.root)
    split = json.loads((args.root / 'results/rsp03-split-v1.json').read_text())
    development = {obs for group in split['passes'] if group['split'] == 'development'
                   for obs in group['observations']}
    if set(args.observation) - development:
        parser.error('Only development observations may be used in this diagnostic.')

    args.output.mkdir(parents=True, exist_ok=True)
    summary = []
    burst_estimates = []
    with (args.output / 'rsp03-confidence-occurrences.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['observation', 'seconds', 'bytes', 'sha256', 'method',
                         'station_match', 'best_retry_rank_for_payload'])
        for obs in args.observation:
            path = args.root / 'replays/rsp03' / f'iq_{obs}.raw'
            with path.open('rb') as recording:
                if hashlib.file_digest(recording, 'sha256').hexdigest() != decoder.CHECKSUMS[obs]:
                    raise ValueError(f'Checksum mismatch for {path}')
            samples = np.memmap(path, dtype='<i2', mode='r').reshape(-1, 2)
            with (args.root / 'results' / f'rsp03-tracking-{obs}-bursts.csv').open() as table:
                bursts = list(csv.DictReader(table))
            frequency = None
            if args.centroid:
                with (args.root / 'results' / f'rsp03-tracking-{obs}-frequency.csv').open() as table:
                    frequency = list(csv.DictReader(table))
            selective = None
            if args.selective:
                baseline, corrected, selected = replay_selective(samples, bursts, decoder)
                hard, repaired, ranks, elapsed, retry_seconds, _ = baseline
                corrected_hard, corrected_retry, _, second_seconds, _, estimates = corrected
                selective = (combined_occurrences(corrected_hard, corrected_retry),
                             second_seconds, selected)
            else:
                hard, repaired, ranks, elapsed, retry_seconds, estimates = replay(
                    samples, bursts, decoder, args.shift, frequency, args.symbol_levels
                )
            burst_estimates.extend((obs, *item) for item in estimates)
            # Station records are opened after candidate discovery and acceptance.
            references = decoder.station_frames(obs, args.root / 'replays/rsp03/references', allow_empty=True)
            reference_source = obs
            if not references:
                group = next(group for group in split['passes'] if obs in group['observations'])
                for peer in group['observations']:
                    if peer != obs:
                        references = decoder.station_frames(
                            peer, args.root / 'replays/rsp03/references', allow_empty=True
                        )
                        if references:
                            reference_source = peer
                            break
            union = combined_occurrences(hard, repaired)
            added = [item for item in union if item not in hard]
            methods = [('hard', hard), ('confidence_retry', added)]
            if selective is not None:
                candidates, second_seconds, selected = selective
                baseline_union = union.copy()
                for seconds, payload in candidates:
                    add_occurrence(union, seconds, payload)
                second_added = union[len(baseline_union):]
                methods.append(('selective_frequency_retry', second_added))
            for label, occurrences in methods:
                for seconds, payload in sorted(occurrences):
                    writer.writerow([obs, f'{seconds:.6f}', len(payload),
                                     hashlib.sha256(payload).hexdigest(), label, payload in references,
                                     ranks[payload] if label == 'confidence_retry' else ''])
            row = dict(observation=obs, shift_hz=None if args.centroid or args.symbol_levels else args.shift,
                       correction=('symbol_levels' if args.symbol_levels else
                                   'centroid' if args.centroid else 'fixed'), reference_source=reference_source if references else None,
                       reference_payloads=len(references), hard_crc=len(hard),
                       hard_verified=sum(payload in references for _, payload in hard),
                       added_verified=sum(payload in references for _, payload in added),
                       added_unmatched=sum(payload not in references for _, payload in added),
                       processing_seconds=elapsed, retry_seconds=retry_seconds)
            if selective is not None:
                row.update(
                    correction='selective_symbol_levels', shift_hz=None,
                    baseline_verified=sum(payload in references for _, payload in baseline_union),
                    second_verified=sum(payload in references for _, payload in second_added),
                    second_unmatched=sum(payload not in references for _, payload in second_added),
                    total_bursts=len(bursts), selected_bursts=selected,
                    second_processing_seconds=second_seconds,
                    total_processing_seconds=elapsed + second_seconds,
                )
            summary.append(row)
            print(json.dumps(row), flush=True)
    if args.symbol_levels or args.selective:
        with (args.output / 'rsp03-symbol-level-estimates.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['observation', 'start_seconds', 'stop_seconds',
                             'offset_hz', 'applied_translation_hz'])
            writer.writerows(burst_estimates)
    (args.output / 'rsp03-confidence-summary.json').write_text(json.dumps(summary, indent=2) + '\n')


if __name__ == '__main__':
    main()
