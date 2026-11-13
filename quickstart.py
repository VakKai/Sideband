"""Decode a deterministic synthetic AX.25 burst using Sideband's receiver."""
import hashlib

import numpy as np
from scipy.ndimage import gaussian_filter1d

from importlib import import_module

tracking = import_module('replay-rsp03-tracking')
receiver = import_module('replay-rsp03-confidence')
RATE = tracking.d.RATE
FLAG = [0, 1, 1, 1, 1, 1, 1, 0]
PAYLOAD = bytes.fromhex('86a2a040404060a692888a84826103f0') + b'Sideband synthetic packet'


def fcs(data):
    """Compute the wire FCS using the reflected AX.25 polynomial."""
    value = 0xffff
    for octet in data:
        value ^= octet
        for _ in range(8):
            value = (value >> 1) ^ (0x8408 if value & 1 else 0)
    return (value ^ 0xffff).to_bytes(2, 'little')


def stuff(data):
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder='little')
    stuffed = []
    ones = 0
    for bit in bits:
        stuffed.append(int(bit))
        ones = ones + 1 if bit else 0
        if ones == 5:
            stuffed.append(0)
            ones = 0
    return stuffed


def synthetic_iq():
    """Generate a Gaussian-shaped continuous-phase FSK burst in ten seconds of I/Q."""
    bits = FLAG * 32 + stuff(PAYLOAD + fcs(PAYLOAD)) + FLAG * 16
    scrambled = []
    level = 1
    symbols = []
    for index, bit in enumerate(bits):
        if index >= 12:
            bit ^= scrambled[index - 12]
        if index >= 17:
            bit ^= scrambled[index - 17]
        scrambled.append(bit)
        if not bit:
            level = -level
        symbols.append(level)
    frequency = gaussian_filter1d(np.repeat(symbols, 6).astype(float), 1.2) * 2400
    carrier = 0.7 * np.exp(2j * np.pi * np.cumsum(frequency) / RATE)
    rng = np.random.default_rng(12)
    iq = rng.normal(0, .005, (10 * RATE, 2))
    start = 2 * RATE + 3
    iq[start:start + len(carrier)] += np.column_stack((carrier.real, carrier.imag))
    return np.rint(iq * 32767).astype('<i2')


def decode(samples):
    ratios, _, _, labels, count = tracking.detect(samples)
    bursts = []
    for label in range(1, count + 1):
        indices = np.flatnonzero(labels == label)
        bursts.append(dict(start_seconds=indices[0] * .02,
                           stop_seconds=(indices[-1] + 1) * .02,
                           peak_power_ratio=float(ratios[indices].max())))
    hard, repaired, *_ = receiver.replay(samples, bursts, tracking.d, 0)
    return receiver.combined_occurrences(hard, repaired)


def main():
    matches = [(seconds, payload) for seconds, payload in decode(synthetic_iq())
               if payload == PAYLOAD]
    if len(matches) != 1:
        raise SystemExit(f'Expected one synthetic packet, recovered {len(matches)}')
    seconds, payload = matches[0]
    print(f'Synthetic AX.25 packet at {seconds:.3f} s: {payload[16:].decode("ascii")}')
    print(f'Payload SHA-256: {hashlib.sha256(payload).hexdigest()}')


if __name__ == '__main__':
    main()
