"""Lane grammar on top of the trained model: tune keep_lane on validation songs, report on test songs."""
import sys,os,json,numpy as np,torch; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import train as T, evaluate as E, fun_metrics as FM, weightspace_fun as WF, decode as DEC, features as F
from model import Charter
m=Charter().to(T.dev); m.load_state_dict(torch.load(os.path.join(os.path.dirname(os.path.abspath(__file__)),'charter.pt'),map_location=T.dev))
def cache(songs): return {(n,k):T.predict(m,n,k) for n in sorted(songs) for k in range(T.D[n]['mels'].shape[0])}
def run(C,grammar,keep=None,jump=None):
    if keep is not None: WF.FUN['keep_lane']=keep
    if jump is not None: WF.FUN['jump_bonus']=jump
    M=[];A=[]
    for (n,k),p in C.items():
        d=T.D[n]; act=DEC.active_steps(d['mels'][k],d['step_frames'])
        y=WF.chart(p,d['mels'][k],d['step_frames'],F.FAMILIES[int(d['fams'][k])],act,scale=DEC.DENS.get('_scale',[1]*4),quota=False,viterbi=grammar,motif=False)
        M.append(FM.track_metrics(y.T)); A.append(E.score(y,d['y'][k]))
    f=FM.summarize(M); g=lambda key: np.mean([f[d][key] for d in range(4)])
    return [round(float(np.mean([a[d][2] for a in A])),3) for d in range(4)],[round(float(np.mean([a[d][3] for a in A])),3) for d in range(4)],{k:round(float(g(k)),3) for k in ('jump','same','jack','repeat')}
if __name__=='__main__':
    split=sys.argv[1]; C=cache({'val':T.VAL,'test':T.TEST}[split])
    if split=='val':
        print('no grammar',run(C,False))
        for keep in (1.0,1.5,2.0,3.0):
            for jump in (1.0,1.5): print('keep %.1f jump %.1f'%(keep,jump),run(C,True,keep,jump),flush=True)
    else:
        keep,jump=float(sys.argv[2]),float(sys.argv[3]); print('test no grammar',run(C,False)); print('test grammar keep %.1f jump %.1f'%(keep,jump),run(C,True,keep,jump))
