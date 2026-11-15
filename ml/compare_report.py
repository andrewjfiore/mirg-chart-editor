"""docs/model_comparison.html: metrics for trained vs weight-space vs baseline, plus piano-roll snippets on held-out songs."""
import sys,os,json,html,numpy as np,torch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,os.path.join(ROOT,'ml'))
import train as T, evaluate as E
from model import Charter
DIFF=E.DIFF; COL=['#e8615a','#f2a33a','#59c97a']
def roll(y,s0,n,label):
    w=900; cw=w/n; rows=[]
    for lane in range(3):
        for s in range(n):
            if y[s0+s]==lane+1: rows.append('<rect x="%.1f" y="%d" width="%.1f" height="10" rx="2" fill="%s"/>'%(s*cw,4+lane*13,max(2,cw*0.8),COL[lane]))
    beats=''.join('<line x1="%.1f" y1="0" x2="%.1f" y2="44" stroke="%s" stroke-width="1"/>'%(b*12*cw,b*12*cw,'#555' if b%4==0 else '#2c2c2c') for b in range(n//12+1))
    return '<div class="r"><span>%s</span><svg width="%d" height="44">%s%s</svg></div>'%(label,w,beats,''.join(rows))
if __name__=='__main__':
    calib=json.load(open(os.path.join(ROOT,'ml','calib.json')))
    model=Charter().to(T.dev); model.load_state_dict(torch.load(os.path.join(ROOT,'ml','charter.pt'),map_location=T.dev))
    tht=np.array(calib['trained']); thw=np.array(calib['weightspace'])
    res={}
    for name,fn,th in (('Trained',lambda n,k:T.predict(model,n,k),tht),('Weight-space',lambda n,k:E.ws_probs(n,k,thw),thw),('Onset baseline',E.baseline_probs,None)):
        if th is None: th=E.calibrate(E.collect(None,T.VAL,E.baseline_probs))
        R=E.collect(None,T.TEST,fn); S=[E.score(E.decode(p,th),y) for p,y in R]
        res[name]=np.array([[np.mean([s[d][i] for s in S]) for i in range(5)] for d in range(4)])
    tab='<table><tr><th>Model</th>'+''.join('<th>%s F1</th><th>%s lane</th>'%(d,d) for d in DIFF)+'</tr>'
    for k,v in res.items(): tab+='<tr><td>%s</td>'%k+''.join('<td>%.2f</td><td>%.2f</td>'%(v[d,2],v[d,3]) for d in range(4))+'</tr>'
    tab+='</table>'
    # ladder (what uploads use) on the same held-out songs
    lad={}
    for name,fn in (('Trained',lambda n,k:T.predict(model,n,k)),('Weight-space',lambda n,k:E.ws_probs(n,k,thw))):
        S=[]
        for n in sorted(T.TEST):
            for k in range(T.D[n]['mels'].shape[0]): S.append(E.score(E.ladder_labels(fn(n,k),n,k),T.D[n]['y'][k]))
        lad[name]=np.array([[np.mean([x[d][i] for x in S]) for i in range(5)] for d in range(4)])
    tab+='<h2>Upload decoding (difficulty ladder)</h2><table><tr><th>Model</th>'+''.join('<th>%s F1</th><th>%s lane</th>'%(d,d) for d in DIFF)+'</tr>'
    for k,v in lad.items(): tab+='<tr><td>%s</td>'%k+''.join('<td>%.2f</td><td>%.2f</td>'%(v[d,2],v[d,3]) for d in range(4))+'</tr>'
    tab+='</table>'
    e2e=os.path.join(ROOT,'ml','e2e_magpie.txt')
    if os.path.exists(e2e): tab+='<h2>End to end on Magpie (mixed audio, Demucs stems, beat tracking, 50 ms tolerance)</h2><pre>%s</pre>'%html.escape(open(e2e).read())
    # agreement between the two models on the user's test songs
    sys.path[:0]=[os.path.join(ROOT,'tools')]; import chart as CH, features as FF
    def times(slot):
        c=CH.load(os.path.join(ROOT,'work','edits',slot,slot+'.mid')); f=FF.tick_to_sec_fn(c['tempos'],c['tpq']); out={}
        for t in c['tracks']:
            if t['kind']=='catch':
                for d in range(4): out[(t['label'],d)]=f(np.array([g[0] for g in t['gems'] if g[1]==d],float))
        return out
    agree='<h2>Your test songs: how often the two models put a gem at the same moment (F1 at 50 ms)</h2><table><tr><th>Song</th>'+''.join('<th>%s</th>'%d for d in DIFF)+'</tr>'
    for title,a,b in (('Incredible','phantoms','necrodancer'),('Signal Overload','concept','redgiant')):
        try: A,B=times(a),times(b)
        except Exception: continue
        row=[]
        for d in range(4):
            fs=[]
            for key in A:
                if key[1]!=d or key not in B or not len(A[key]) or not len(B[key]): continue
                x,y=A[key],B[key]; pa=np.mean([np.min(np.abs(y-v))<=0.05 for v in x]); pb=np.mean([np.min(np.abs(x-v))<=0.05 for v in y]); fs.append(2*pa*pb/(pa+pb+1e-9))
            row.append(np.mean(fs) if fs else 0)
        agree+='<tr><td>%s</td>'%title+''.join('<td>%.2f</td>'%v for v in row)+'</tr>'
    tab+=agree+'</table><p>Play them side by side in play.html: weight-space charts are in the Phantoms and Concept slots, trained charts in Necrodancer and Red Giant.</p>'
    snips=''
    for n in sorted(T.TEST)[:2]:
        d=T.D[n]
        for k in range(min(3,d['mels'].shape[0])):
            s0=len(d['step_frames'])//3; L=16*12
            yt=E.decode(T.predict(model,n,k),tht)[:,3]; yw=E.decode(E.ws_probs(n,k,thw),thw)[:,3]
            snips+='<h3>%s, %s, Expert, 16 beats</h3>'%(html.escape(n),html.escape(str(d['labels'][k])))+roll(d['y'][k,3],s0,L,'Human')+roll(yt,s0,L,'Trained')+roll(yw,s0,L,'Weight-space')
    page='''<!DOCTYPE html><html><head><meta charset="utf-8"><title>Charting models</title><style>
body{background:#16161a;color:#ddd;font:14px -apple-system,Segoe UI,sans-serif;margin:24px;max-width:1040px}
table{border-collapse:collapse;margin:12px 0}td,th{border:1px solid #333;padding:5px 9px;text-align:right}pre{background:#1e1e24;padding:10px;border-radius:4px;font-size:12px;overflow:auto}h2{font-size:15px;margin-top:22px}td:first-child,th:first-child{text-align:left}
.r{display:flex;align-items:center;gap:8px;margin:2px 0}.r span{width:100px;color:#999}svg{background:#1e1e24;border-radius:4px}
h3{font-size:13px;color:#aaa;margin:18px 0 4px}p{color:#aaa;max-width:780px}</style></head><body>
<h1>Trained vs weight-space charting</h1><h2>Clean stems, fixed thresholds</h2>
<p>Held-out songs: %s (never seen in training or calibration). F1 counts a gem as correct only on the exact grid step a human used. Lane is the share of correctly placed gems also in the human's lane (chance is 0.33). Both models get one threshold per difficulty, set on the validation songs.</p>
<p>Trained: %s learned weights from gradient descent on %d songs. Weight-space: %d hand-written numbers (onset kernels, beat-position priors, spacing, lane rules), no gradient descent.</p>
%s%s</body></html>'''%(', '.join(sorted(T.TEST)),'{:,}'.format(sum(p.numel() for p in model.parameters())),len(T.TRAIN),
        sum(v.size for v in np.load(os.path.join(ROOT,'ml','weightspace_weights.npz')).values()),tab,snips)
    os.makedirs(os.path.join(ROOT,'docs'),exist_ok=True); open(os.path.join(ROOT,'docs','model_comparison.html'),'w').write(page); print('wrote docs/model_comparison.html')
    print({k:np.round(v[:,2],3).tolist() for k,v in res.items()})
