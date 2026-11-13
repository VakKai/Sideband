#!/usr/bin/env python3
"""Development-only blind energy detector and spectral-centroid tracking control.
References score CRC-valid output only. No station windows enter this experiment.
"""
import argparse, csv, hashlib, importlib.util, json, time
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_closing, binary_dilation, label
spec=importlib.util.spec_from_file_location('decoder',Path(__file__).with_name('replay-rsp03.py'))
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
class Valid:
    def __contains__(self, f): return f is not None

def spectrum(iq):
    n=1152 # 20 ms, exact integer symbols
    count=len(iq)//n
    x=iq[:count*n].reshape(-1,n)
    ps=np.abs(np.fft.fft(x*np.hanning(n),axis=1))**2
    freq=np.fft.fftfreq(n,1/d.RATE)
    inner=np.abs(freq)<7000
    outer=(np.abs(freq)>10000)&(np.abs(freq)<20000)
    noise=np.mean(ps[:,outer],axis=1)
    ratio=np.mean(ps[:,inner],axis=1)/np.maximum(noise,1e-20)
    excess=np.maximum(ps[:,inner]-noise[:,None],0)
    center=np.sum(excess*freq[inner],axis=1)/np.maximum(excess.sum(axis=1),1e-20)
    return ratio,center

def detect(raw):
    # Bound spectral memory; contiguous 10-second chunks have 500 full blocks.
    ratios=[];centers=[]
    for start in range(0,len(raw),10*d.RATE):
        x=raw[start:start+10*d.RATE].astype(np.float32)
        r,c=spectrum((x[:,0]+1j*x[:,1])/32767)
        ratios.extend(r);centers.extend(c)
    ratios=np.asarray(ratios);centers=np.asarray(centers)
    # 2 dB signal-band excess, bridge gaps <=100 ms, pad 100 ms.
    mask=binary_dilation(binary_closing(ratios>10**(.2),structure=np.ones(6)),structure=np.ones(11))
    labels,count=label(mask)
    return ratios, centers, mask, labels, count

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('recording_dir',type=Path)
    p.add_argument('--observation',required=True,choices=list(d.CHECKSUMS))
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();obs=a.observation
    path=a.recording_dir/f'iq_{obs}.raw'
    with path.open('rb') as f:
        assert hashlib.sha256(f.read()).hexdigest()==d.CHECKSUMS[obs]
    refs=d.station_frames(obs,a.recording_dir/'references', allow_empty=True)
    raw=np.memmap(path,dtype='<i2',mode='r').reshape(-1,2)
    started=time.perf_counter()
    ratios, centers, mask, labels, count = detect(raw)
    found={'raw':[], 'centroid':[], 'burst_median':[]};bursts=[]
    for i in range(1,count+1):
        idx=np.flatnonzero(labels==i)
        first,last=idx[0],idx[-1]+1
        start,stop=first*1152,min(last*1152,len(raw))
        x=raw[start:stop].astype(np.float32);iq=(x[:,0]+1j*x[:,1])/32767
        # Median across five spectral blocks (100 ms); interpolation gives a
        # smoothly varying frequency, integrated to a continuous phase.
        from scipy.ndimage import median_filter
        hz=median_filter(centers[first:last],size=5,mode='nearest')
        correction=np.interp(np.arange(len(iq)),np.arange(len(hz))*1152+576,hz)
        phase=2*np.pi*np.cumsum(correction)/d.RATE
        corrected=iq*np.exp(-1j*phase).astype(np.complex64)
        bursts.append([obs,start/d.RATE,stop/d.RATE,float(np.max(ratios[first:last])),float(np.median(hz)),float(np.min(hz)),float(np.max(hz))])
        active = ratios[first:last] > 10**(.2)
        burst_hz = float(np.median(centers[first:last][active])) if np.any(active) else 0.
        steady = iq*np.exp(-2j*np.pi*burst_hz*np.arange(len(iq))/d.RATE).astype(np.complex64)
        for mode,signal in [('raw',iq),('centroid',corrected),('burst_median',steady)]:
            for t,f in d.recover(signal,0,Valid()):
                absolute=start/d.RATE+t
                if not any(f==old and abs(absolute-ot)<.002 for ot,old in found[mode]):
                    found[mode].append((absolute,f))
    elapsed=time.perf_counter()-started
    a.output_dir.mkdir(parents=True,exist_ok=True)
    prefix=a.output_dir/f'rsp03-tracking-{obs}'
    with Path(str(prefix)+'-bursts.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['observation','start_seconds','stop_seconds','peak_power_ratio','median_offset_hz','min_offset_hz','max_offset_hz']);w.writerows(bursts)
    with Path(str(prefix)+'-frequency.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['seconds','power_ratio','raw_centroid_hz','detected']);w.writerows(zip((np.arange(len(centers))+.5)*.02,ratios,centers,mask))
    with Path(str(prefix)+'-packets.csv').open('w') as f:
        w=csv.writer(f);w.writerow(['mode','seconds','bytes','sha256','station_match'])
        for mode,items in found.items():
            for t,payload in items:w.writerow([mode,t,len(payload),hashlib.sha256(payload).hexdigest(),payload in refs])
    summary=dict(observation=obs,detected_bursts=count,processing_seconds=elapsed,counts={mode:dict(crc_valid=len(items),station_matched=sum(f in refs for _,f in items)) for mode,items in found.items()},limitations='Exploratory centroid baseline. Detector/estimator not validated on held-out passes. Timing remains fixed. Phase continuous within each detected segment only.')
    Path(str(prefix)+'.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
