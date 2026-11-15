"""Shared audio features + tempo-grid helpers for training and inference."""
import numpy as np,librosa
SR=22050; HOP=256; NMELS=64; STEPS_PER_BEAT=12; TPQ=480; STEP_TICKS=TPQ//STEPS_PER_BEAT
FAMILIES=['drums','bass','synth','vox','guitar','keys','other']
def family(label):
    l=label.lower()
    for k,f in (('drum','drums'),('dms','drums'),('bass','bass'),('vox','vox'),('voc','vox'),('gtr','guitar'),('guit','guitar'),('key','keys'),('piano','keys'),('synth','synth'),('syn','synth'),('brass','other'),('sax','other')):
        if k in l: return FAMILIES.index(f)
    return FAMILIES.index('other')
def logmel(mono,sr):
    if sr!=SR: mono=librosa.resample(mono,orig_sr=sr,target_sr=SR)
    m=librosa.feature.melspectrogram(y=mono,sr=SR,n_fft=1024,hop_length=HOP,n_mels=NMELS,fmin=30,fmax=11000)
    return np.log1p(m*100).T.astype(np.float16)   # frames x NMELS
def tick_to_sec_fn(tempos,tpq):
    """tempos: [[tick, us_per_quarter], ...] -> vectorized tick->seconds."""
    tempos=sorted(tempos) or [[0,500000]]
    if tempos[0][0]!=0: tempos=[[0,tempos[0][1]]]+tempos
    t0=np.array([t for t,_ in tempos],float); us=np.array([u for _,u in tempos],float)
    sec0=np.concatenate([[0],np.cumsum(np.diff(t0)*us[:-1]/tpq/1e6)])
    def f(ticks):
        ticks=np.asarray(ticks,float); i=np.searchsorted(t0,ticks,side='right')-1
        return sec0[i]+(ticks-t0[i])*us[i]/tpq/1e6
    return f
def step_frames(n_steps,tempos,tpq):
    """frame index (float) of each grid step (step = STEP_TICKS at 480 tpq)."""
    f=tick_to_sec_fn(tempos,tpq); ticks=np.arange(n_steps)*STEP_TICKS*tpq/TPQ
    return f(ticks)*SR/HOP
