"""Weight-space charter: every weight below is written by hand, no gradient descent.
Layers: (1) per-band onset kernels on the stem log-mel, (2) divisive local normalization,
(3) beat-position prior bias per difficulty, (4) lateral inhibition (min spacing), (5) pitch-contour lane head.
The only numbers taken from data are counts of where human gems sit in the beat (POS_SHARE, measured on the
training songs) and one threshold per difficulty, set by the same calibration the trained model uses."""
import numpy as np,json,os
ROOT=os.path.dirname(os.path.abspath(__file__))
NM=64; SPB=12
# measured share of gems at each of the 12 positions of a beat (training songs), rows = difficulty
POS_SHARE=np.array([[0.883,0,0,0.003,0.002,0,0.104,0,0.002,0.006,0,0],[0.806,0,0,0.006,0.003,0,0.147,0,0.007,0.032,0,0],
 [0.501,0,0,0.042,0.014,0,0.359,0,0.031,0.052,0,0],[0.423,0,0.001,0.085,0.022,0,0.327,0,0.032,0.107,0.001,0]])
def build_weights():
    W={}
    # (1) onset kernels: +1 now, -1 one frame ago, summed over a band of mel bins; 4 bands
    bands=[(0,10),(10,24),(24,42),(42,64)]; K=np.zeros((4,NM,2),np.float32)
    for b,(lo,hi) in enumerate(bands): K[b,lo:hi,1]=1.0/(hi-lo); K[b,lo:hi,0]=-1.0/(hi-lo)
    W['onset_kernel']=K
    # band mixing per instrument family (drums, bass, synth, vox, guitar, keys, other): where that instrument's attacks live
    W['band_mix']=np.array([[1.0,0.6,0.5,0.9],[1.0,0.7,0.2,0.1],[0.3,0.8,1.0,0.6],[0.1,0.9,1.0,0.4],[0.3,1.0,0.9,0.5],[0.4,1.0,0.8,0.4],[0.4,0.8,0.8,0.5]],np.float32)
    # (2) divisive normalization window: 4 s moving average (in frames at 22050/256)
    W['norm_len']=np.array(int(4*22050/256)); W['eps']=np.array(1e-3,np.float32)
    # (3) position prior: log share, floored so rare positions stay possible on hard difficulties
    W['pos_bias']=np.log(POS_SHARE+np.array([[0.002],[0.003],[0.006],[0.01]])).astype(np.float32)
    W['onset_gain']=np.array([2.0,2.0,2.2,2.4],np.float32)
    # (4) lateral inhibition radius per difficulty, in grid steps (12 per beat)
    W['inhibit']=np.array([5,5,2,1])
    # (5) lane head: centroid weights = mel bin index; contour = centroid minus its 2-beat local mean; dead zone 0.5 std
    W['centroid_w']=np.arange(NM,dtype=np.float32); W['contour_win_steps']=np.array(2*SPB); W['dead_zone']=np.array(0.5,np.float32)
    # drums: lane = which band carries the hit (measured: low band -> left, top band -> right)
    W['drum_band_lane']=np.array([0,1,1,2])
    # melodic: lane steps the way the pitch proxy moves between gems; ties keep alternating
    W['step_thresh']=np.array(0.15,np.float32)
    return W
def save(path=os.path.join(ROOT,'weightspace_weights.npz')):
    import sys; sys.path.insert(0,ROOT); import weightspace_fun as WF
    W=build_weights(); W.update({'fun_'+k:np.array(v) for k,v in WF.FUN.items()}); np.savez(path,**W); return path
def _movavg(x,n):
    n=max(1,int(n)); c=np.cumsum(np.concatenate([[0],x])); i=np.arange(len(x)); a=np.clip(i-n//2,0,len(x)); b=np.clip(i+n//2+1,0,len(x))
    return (c[b]-c[a])/np.maximum(1,b-a)
def forward(stem_mel,step_frames,fam,W=None,th=None):
    """stem_mel: frames x 64 (log-mel); step_frames: float frame per step. Returns S x 4 x 4 probabilities."""
    W=W or build_weights(); m=stem_mel.astype(np.float32); T=len(m)
    d=np.vstack([np.zeros((1,NM),np.float32),m[1:]-m[:-1]])                  # kernel taps (-1,+1) per bin
    bands=np.maximum(np.einsum('tm,bm->tb',d,W['onset_kernel'][:,:,1]),0)     # rectified band flux
    o=bands@W['band_mix'][fam]
    o=o/(_movavg(o,W['norm_len'])+W['eps'])                                   # divisive normalization
    fr=np.clip(np.round(step_frames).astype(int),0,T-1)
    os_=np.maximum.reduce([o[np.clip(fr+k,0,T-1)] for k in (-1,0,1)])         # max over +-1 frame
    S=len(fr); pos=np.arange(S)%SPB
    cen=(m*W['centroid_w']).sum(1)/(m.sum(1)+1e-6); c=cen[fr]
    contour=c-_movavg(c,W['contour_win_steps']); sd=np.sqrt(_movavg(contour**2,W['contour_win_steps']*4))+1e-6
    z=contour/sd
    out=np.zeros((S,4,4),np.float32)
    for dd in range(4):
        logit=W['onset_gain'][dd]*np.log1p(os_)+W['pos_bias'][dd][pos]
        r=int(W['inhibit'][dd]); pad=np.pad(logit,(r,r),constant_values=-1e9)
        win=np.max(np.stack([pad[i:i+S] for i in range(2*r+1)]),0); keep=logit>=win   # lateral inhibition
        p=1/(1+np.exp(-(logit-2.0)))*keep
        if fam==0:
            lane=W['drum_band_lane'][bands[fr].argmax(1)]
        else:
            lane=np.where(z>W['dead_zone'],2,np.where(z<-W['dead_zone'],0,1))
            idx=np.where(p>=(th[dd] if th is not None else 0.5))[0]; cur=1; direction=1
            for i,s_ in enumerate(idx):
                if i==0: cur=int(lane[s_]); lane[s_]=cur; continue
                dlt=(c[s_]-c[idx[i-1]])/sd[s_]
                if dlt>W['step_thresh']: direction=1
                elif dlt<-W['step_thresh']: direction=-1
                nxt=cur+direction
                if nxt<0 or nxt>2: direction=-direction; nxt=cur+direction
                cur=nxt; lane[s_]=cur
        out[:,dd,0]=1-p; out[np.arange(S),dd,lane+1]=p
    return out
if __name__=='__main__': print('wrote',save())
