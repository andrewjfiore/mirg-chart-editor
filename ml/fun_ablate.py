import sys,os,json,numpy as np; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import train as T, evaluate as E, fun_metrics as FM, weightspace_fun as WF, decode as DEC, features as F, fun_eval as FE
calib=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'calib.json'))); thw=np.array(calib['weightspace'])
songs=sorted({'val':T.VAL,'test':T.TEST}[sys.argv[1] if len(sys.argv)>1 else 'val'])
cache={(n,k):E.ws_probs(n,k,thw) for n in songs for k in range(T.D[n]['mels'].shape[0])}
def run(**kw):
    M=[];A=[]
    for (n,k),p in cache.items():
        d=T.D[n]; act=DEC.active_steps(d['mels'][k],d['step_frames'])
        y=WF.chart(p,d['mels'][k],d['step_frames'],F.FAMILIES[int(d['fams'][k])],act,scale=DEC.DENS.get('_scale',[1]*4),**kw)
        M.append(FM.track_metrics(y.T,FE.energy(n,k))); A.append(E.score(y,d['y'][k]))
    f=FM.summarize(M); return [np.mean([a[d][2] for a in A]) for d in range(4)],[np.mean([a[d][3] for a in A]) for d in range(4)],f
if __name__=='__main__':
    for name,kw in [('ladder only',dict(quota=False,viterbi=False,motif=False)),('+bar quota',dict(quota=True,viterbi=False,motif=False)),('+lane grammar',dict(quota=True,viterbi=True,motif=False)),('+motif copy',dict(quota=True,viterbi=True,motif=True))]:
        f1,ln,fm=run(**kw)
        print('%-14s F1 %s lane %s | repeat %.2f jump %.2f same %.2f jack %.2f energy %.2f empty %.2f'%(name,np.round(f1,2),np.round(ln,2),np.mean([fm[d]['repeat'] for d in range(4)]),np.mean([fm[d]['jump'] for d in range(4)]),np.mean([fm[d]['same'] for d in range(4)]),np.mean([fm[d]['jack'] for d in range(4)]),np.mean([fm[d]['energy_corr'] for d in range(4)]),np.mean([fm[d]['empty_bars'] for d in range(4)])),flush=True)
