"""Render the first held-out pass where confidence decoding gains a packet."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import stft

ROOT = Path(__file__).resolve().parent


def main():
    with (ROOT / 'results/rsp03-final-packets.csv').open() as stream:
        rows = [row for row in csv.DictReader(stream) if row['station_match'] == 'True']
    hard = [row for row in rows if row['mode'] == 'hard']
    target = next((row for row in rows if row['mode'] == 'confidence' and not any(
        old['pass_start_utc'] == row['pass_start_utc'] and old['sha256'] == row['sha256']
        and abs(float(old['seconds']) - float(row['seconds'])) <= .05 for old in hard)), None)
    if target is None:
        return
    obs = target['observation']
    time = float(target['seconds'])
    rate = 57600
    begin = max(0, round((time - .45) * rate))
    end = round((time + .65) * rate)
    raw = np.memmap(ROOT / 'replays/rsp03' / f'iq_{obs}.raw', dtype='<i2', mode='r').reshape(-1, 2)
    window = raw[begin:end].astype(np.float32)
    iq = window[:, 0] + 1j * window[:, 1]
    freq, sec, bins = stft(iq, fs=rate, nperseg=512, noverlap=384,
                          return_onesided=False, boundary=None, padded=False)
    power = 20 * np.log10(np.maximum(np.abs(np.fft.fftshift(bins, axes=0)), 1e-6))
    sec += begin / rate
    fig, (signal, frames) = plt.subplots(2, 1, figsize=(9, 4.8), sharex=True,
                                         gridspec_kw={'height_ratios': [3, 1]})
    signal.pcolormesh(sec, np.fft.fftshift(freq) / 1000, power,
                      vmin=np.percentile(power, 40), vmax=np.percentile(power, 99),
                      cmap='magma', shading='auto')
    signal.set_ylim(-12, 12)
    signal.set_ylabel('Baseband frequency (kHz)')
    signal.set_title(f'RSP-03 held-out recording {obs}')
    for index, mode in enumerate(('hard', 'confidence', 'selective')):
        points = [float(row['seconds']) for row in rows if row['observation'] == obs
                  and row['mode'] == mode and sec[0] <= float(row['seconds']) <= sec[-1]]
        frames.scatter(points, [index] * len(points), color='#087f8c', s=27)
    frames.set_yticks([0, 1, 2], ['Hard decisions', 'Confidence retry', 'Selective frequency'])
    frames.invert_yaxis()
    frames.set_xlabel('Seconds from recording start')
    frames.set_xlim(sec[0], sec[-1])
    for ax in (signal, frames):
        ax.axvline(time, color='#888888', lw=1, linestyle='--')
    fig.tight_layout()
    fig.savefig(ROOT / 'results/rsp03-final-demo.png', dpi=170)
    print(obs, f'{time:.6f}')


if __name__ == '__main__':
    main()
