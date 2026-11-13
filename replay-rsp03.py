#!/usr/bin/env python3
"""Replay station-confirmed RSP-03 bursts and count reference matches."""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

import numpy as np
from scipy.signal import fftconvolve, firwin

RATE = 57600
BAUD = 9600
# Seconds from the start of each I/Q file. Selected using station packet
# times and the corresponding broadband bursts in the recordings.
WINDOWS = {
    '12511021': ((94, 101), (332, 341)),
    '12511022': ((213, 222),),
    '13415454': ((104, 112),),
    '13415455': ((104, 112),),
}
CHECKSUMS = {
    '12620261': '025538b088b9b735b972eda1eafcc17ffddecee5d9b2b22ee3982057972bbf20',
    '12620260': 'b4a506a037a70281219dbf05b53f8a24a08e03a2c3f23d1a96e264bd38283117',
    '12579358': '7961fbadc0335f0eca24d4ab76735a3c65e9ba6e3379448b482f7f2c85064278',
    '12579357': 'fbc842c0d6b7d3eff06ecdca6fe99f12d5dd33759fefa21de7035c3d8c221e6c',
    '12512779': 'c0ba5be9d4d99d9b44d0bc0f3de0447cde1726f9f5ac6be9cf138115dc9fbd86',
    '12512778': '5a8d1afa78ef9afdf766c158e29e2387232ec252a3f59623eeca7986c494ca71',
    '12512297': 'c3637e79b9b4c3fbb94947c5569f251d25aaa7c8e16530ef0955289aa0495146',
    '12512296': '57a3b6481e24e9d686307714d4b866d6a55c616f48ea250a2053907752d513ea',
    '12511719': 'e6b25c409f115ec4cd3f3811f44d6da0e41fbf80f5b7d6e47a8a05be92849cd8',
    '12511720': '49d8b99ded9dbe89bfceee0e04534ae5dfce950bf3551c34a33a713701bc07d2',
    '12511021': 'a05d8d07e04b240ca7856bb747f8de8b7d21ac5c82a17e78acc91a5014021750',
    '12511022': 'd597b885a439bb41c1827c14d8a1f4a69d20d58ad5498e644b4d66ed8169662a',
    '13415454': '15c938a8ab17cc2c991fc4903e3f2f7d5f9d8123bdb79342163599dec4f786e9',
    '13415455': 'a71db1995f2d2e28da75b62706821810414906eb5fac07d369537597400744a7',
}
BIT_REVERSE = bytes(int(f'{b:08b}'[::-1], 2) for b in range(256))
FILTER = firwin(65, 5000, fs=RATE).astype(np.float32)


def station_frames(obs, directory, *, allow_empty=False):
    files = sorted(directory.glob(f'data_{obs}_*'))
    if not files:
        directory.mkdir(parents=True, exist_ok=True)
        with urlopen(f'https://network.satnogs.org/api/observations/{obs}/', timeout=30) as response:
            links = json.load(response)['demoddata']
        for entry in links:
            url = entry['payload_demod']
            path = directory / url.rsplit('/', 1)[1]
            with urlopen(url, timeout=30) as response:
                path.write_bytes(response.read())
            files.append(path)
    if not files and not allow_empty:
        raise ValueError(f'No station frames for {obs}')
    return {path.read_bytes() for path in files}


def decode_frame(bits):
    unstuffed = []
    ones = 0
    for bit in bits:
        if ones == 5:
            if bit:
                return None
            ones = 0
            continue
        unstuffed.append(bit)
        ones = ones + 1 if bit else 0
    if len(unstuffed) % 8 or len(unstuffed) < 18 * 8:
        return None

    frame = np.packbits(unstuffed, bitorder='little').tobytes()
    # AX.25 uses the reflected CRC-16/X.25 with a final XOR.
    crc = binascii.crc_hqx(frame[:-2].translate(BIT_REVERSE), 0xffff)
    reflected = (BIT_REVERSE[crc & 255] << 8) | BIT_REVERSE[crc >> 8]
    if frame[-2:] == (reflected ^ 0xffff).to_bytes(2, 'little'):
        return frame[:-2]
    return None


def recover(iq, shift_hz, references):
    if shift_hz:
        phase = 2 * np.pi * shift_hz * np.arange(len(iq)) / RATE
        iq = iq * np.exp(1j * phase).astype(np.complex64)
    filtered = fftconvolve(iq, FILTER, mode='same')
    discriminator = np.angle(filtered[1:] * filtered[:-1].conj())
    smoothed = np.convolve(discriminator, [0.5, 0.5], mode='same')

    samples_per_symbol = RATE // BAUD
    matches = []
    for phase in range(samples_per_symbol):
        levels = smoothed[phase::samples_per_symbol] > 0
        nrzi = levels[1:] == levels[:-1]
        # G3RUH taps are at delays 12 and 17.
        bits = nrzi[17:] ^ nrzi[5:-12] ^ nrzi[:-17]
        flags = np.flatnonzero(
            np.convolve(bits.astype(np.int8), [-1, 1, 1, 1, 1, 1, 1, -1], mode='valid') == 6
        )
        for left, right in zip(flags, flags[1:]):
            if right - left > 2500:
                continue
            frame = decode_frame(bits[left + 8:right])
            if frame in references:
                seconds = ((left + 18) * samples_per_symbol + phase) / RATE
                matches.append((seconds, frame))

    # The same physical occurrence can decode at adjacent sampling phases.
    occurrences = []
    for seconds, frame in sorted(matches):
        if not any(frame == previous and abs(seconds - earlier) < 0.002
                   for earlier, previous in occurrences):
            occurrences.append((seconds, frame))
    return occurrences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording_dir', type=Path)
    parser.add_argument('--references', type=Path, default=Path('replays/rsp03/references'))
    parser.add_argument('--observation', choices=WINDOWS, action='append')
    parser.add_argument('--shift', type=int, action='append', help='Frequency translation in Hz')
    args = parser.parse_args()

    print('observation,shift_hz,seconds_from_iq_start,payload_bytes,payload_sha256')
    for obs in args.observation or WINDOWS:
        path = args.recording_dir / f'iq_{obs}.raw'
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != CHECKSUMS[obs]:
                raise ValueError(f'Unexpected SHA-256 for {path}')
        references = station_frames(obs, args.references)
        samples = np.memmap(path, dtype='<i2', mode='r').reshape(-1, 2)
        for shift in args.shift or [0]:
            for start, stop in WINDOWS[obs]:
                window = samples[start * RATE:stop * RATE].astype(np.float32)
                iq = (window[:, 0] + 1j * window[:, 1]) / 32767
                for time, frame in recover(iq, shift, references):
                    digest = hashlib.sha256(frame).hexdigest()
                    print(f'{obs},{shift},{start + time:.6f},{len(frame)},{digest}')


if __name__ == '__main__':
    main()
