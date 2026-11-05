"""Fixed SOS filters applied to continuous finite runs, never to isolated beats."""
from dataclasses import asdict,dataclass
import numpy as np
from scipy.signal import butter,sosfiltfilt,sosfreqz


@dataclass(frozen=True)
class FilterConfig:
    low_hz: float=.5
    high_hz: float=40.
    prototype_order: int=4
    guard_s: float=5.

    def coefficients(self,fs):
        if not 0<self.low_hz<self.high_hz<fs/2:
            raise ValueError('Require 0 < low < high < Nyquist')
        return butter(self.prototype_order,[self.low_hz,self.high_hz],btype='bandpass',fs=fs,output='sos')

    def parameters(self,fs):
        sos=self.coefficients(fs)
        padlen=int(3*(2*len(sos)+1-min((sos[:,2]==0).sum(),(sos[:,5]==0).sum())))
        return {**asdict(self),'fs_hz':fs,'single_pass_bandpass_order':2*self.prototype_order,
                'method':'sosfiltfilt','padtype':'odd','padlen':padlen,'sos':sos.tolist(),
                'causal':False,'effective_amplitude_response':'abs(H_single_pass)**2'}


def finite_runs(mask):
    edges=np.diff(np.r_[False,np.asarray(mask,dtype=bool),False].astype(np.int8))
    return list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))


def filter_continuous(signal,fs,config):
    values=np.asarray(signal,dtype=np.float64)
    filtered=np.full(values.shape,np.nan)
    safe=np.zeros(values.shape,dtype=bool)
    settings=config.parameters(fs); sos=np.asarray(settings['sos'])
    guard=round(config.guard_s*fs)
    for start,stop in finite_runs(np.isfinite(values)):
        if stop-start<=settings['padlen']+1: continue
        filtered[start:stop]=sosfiltfilt(sos,values[start:stop],padtype='odd',padlen=settings['padlen'])
        if stop-start>2*guard:
            safe[start+guard:stop-guard]=True
    return filtered,safe


def morphology_metrics(raw,filtered,fs,center_index):
    a=raw-np.median(raw,axis=1,keepdims=True)
    b=filtered-np.median(filtered,axis=1,keepdims=True)
    # Correlation is mean-centered; median removal above also supports peak comparison.
    ac=a-a.mean(axis=1,keepdims=True); bc=b-b.mean(axis=1,keepdims=True)
    denominator=np.sqrt(np.square(ac).sum(axis=1)*np.square(bc).sum(axis=1))
    corr=np.divide((ac*bc).sum(axis=1),denominator,out=np.full(len(a),np.nan),where=denominator>1e-20)
    original_ptp=np.ptp(raw,axis=1)
    ratio=np.divide(np.ptp(filtered,axis=1),original_ptp,out=np.full(len(a),np.nan),where=original_ptp>1e-12)
    radius=round(.08*fs); left=max(0,center_index-radius); right=min(a.shape[1],center_index+radius+1)
    original_peak=np.argmax(np.abs(a[:,left:right]),axis=1)
    processed_peak=np.argmax(np.abs(b[:,left:right]),axis=1)
    shift=(processed_peak-original_peak)/fs*1000
    return {'raw_filtered_correlation':corr,'filtered_raw_ptp_ratio':ratio,'local_peak_shift_ms':shift}
