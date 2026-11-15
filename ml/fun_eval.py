import sys,os,json,numpy as np; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import train as T, evaluate as E, fun_metrics as FM, weightspace as WS, weightspace_fun as WF, decode as DEC, features as F
DIFF=['Beginner','Intermediate','Advanced','Expert']
def energy(n,k):
    d=T.D[n]; m=d['mels'][k].astype(np.float32); e=np.expm1(m).sum(1); fr=np.clip(np.round(d['step_frames']).astype(int),0,len(e)-1); return e[fr]
def run(songs,which):
    calib=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'calib.json'))); thw=np.array(calib['weightspace'])
    H=[];W=[]; global ACC; ACC=[]
    for n in sorted(songs):
        for k in range(T.D[n]['mels'].shape[0]):
            en=energy(n,k); H.append(FM.track_metrics(T.D[n]['y'][k],en))
            if which=='fun':
                d=T.D[n]; act=DEC.active_steps(d['mels'][k],d['step_frames'])
                yy=WF.chart(E.ws_probs(n,k,thw),d['mels'][k],d['step_frames'],F.FAMILIES[int(d['fams'][k])],act,scale=DEC.DENS.get('_scale',[1]*4)); W.append(FM.track_metrics(yy.T,en)); ACC.append(E.score(yy,d['y'][k]))
            elif which: W.append(FM.track_metrics(E.ladder_labels(E.ws_probs(n,k,thw),n,k).T,en))
    return FM.summarize(H),(FM.summarize(W) if which else None)
if __name__=='__main__':
    split=sys.argv[1] if len(sys.argv)>1 else 'test'; songs={'test':T.TEST,'val':T.VAL,'train':[x for x in T.TRAIN if not x.startswith('ps2_')]}[split]
    mode=sys.argv[2] if len(sys.argv)>2 else 'plain'; h,w=run(songs,'fun' if mode=='fun' else True)
    keys=list(h[3].keys()); print('%-14s'%'metric'+''.join('%-22s'%DIFF[d] for d in range(4))); print(' '*14+'human  weight-space   '*4)
    for k in keys: print('%-14s'%k+''.join('%6.2f %6.2f         '%(h[d].get(k,np.nan),w[d].get(k,np.nan)) for d in range(4)))
    if mode=='fun':
        print('accuracy (exact step) F1 / lane: '+'  '.join('%s %.3f / %.3f'%(DIFF[d][:3],np.mean([a[d][2] for a in ACC]),np.mean([a[d][3] for a in ACC])) for d in range(4)))
    json.dump({'human':h,'weightspace':w},open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'fun_%s_%s.json'%(split,mode)),'w'),indent=1)
