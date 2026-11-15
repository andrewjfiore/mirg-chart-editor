"""Upload -> playable song, either in an existing slot (replace) or as a new song id (add).
Steps: load audio, beat grid, Demucs stems, model charts per stem, side tracks from the slot or donor, 15-ch MOGG, config.
Files are built in work/uploads/<id>/out and moved into work/edits/<id> at the end, so a failed run leaves no partial song."""
import os,sys,io,json,re,math,struct,shutil,numpy as np,soundfile as sf,librosa,torch
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path[:0]=[os.path.join(ROOT,'tools'),os.path.join(ROOT,'ml'),ROOT]
import features as F,beats,separate,chart,midps3,dtb,mogg,weightspace as WS,decode as DEC,weightspace_fun as WF
from model import Charter
SONGS=os.path.join(ROOT,'work','ark','ps3','songs'); EDITS=os.path.join(ROOT,'work','edits'); UPLOADS=os.path.join(ROOT,'work','uploads')
SR=48000; TPB=1920
# Demucs stem -> (track label, MIDI letter, config name)
LAYOUT=[('drums','Drums','D','drums'),('bass','Bass','B','bass'),('guitar','Guitar','G','guitar'),
        ('piano','Keys','S','keys'),('other','Synth','S','synth'),('vocals','Vox','V','vox')]
_model=None
def model():
    global _model
    if _model is None:
        dev='cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
        m=Charter().to(dev); m.load_state_dict(torch.load(os.path.join(ROOT,'ml','charter.pt'),map_location=dev)); m.eval(); _model=(m,dev)
    return _model
def thresholds(kind='trained'):
    p=os.path.join(ROOT,'ml','calib.json')
    if not os.path.exists(p): return np.full(4,0.5)
    c=json.load(open(p)); return np.array(c.get(kind) or c.get('thresholds') or [0.5]*4)
def load_audio(path):
    x,sr=sf.read(path,dtype='float32',always_2d=True)
    if x.shape[1]==1: x=np.repeat(x,2,1)
    x=x[:,:2]
    if sr!=SR: x=librosa.resample(x.T,orig_sr=sr,target_sr=SR).T
    return np.ascontiguousarray(x,dtype=np.float32)
def band(x,lo=None,hi=None):
    from scipy.signal import butter,sosfiltfilt
    if lo and hi: sos=butter(4,[lo,hi],'bandpass',fs=SR,output='sos')
    elif lo: sos=butter(4,lo,'highpass',fs=SR,output='sos')
    else: sos=butter(4,hi,'lowpass',fs=SR,output='sos')
    return sosfiltfilt(sos,x,axis=0).astype(np.float32)
def predict_track(stem,mix_mel,n_steps,tempos,fam,th,kind='trained'):
    mel=F.logmel(stem.mean(1),SR).astype(np.float32); T=min(len(mel),len(mix_mel)); mel=mel[:T]; mx=mix_mel[:T]
    sfr=F.step_frames(n_steps,tempos,F.TPQ).astype(np.float32); n_steps=int((sfr<T-1).sum()); sfr=sfr[:n_steps]
    act=DEC.active_steps(mel,sfr)
    if kind=='weightspace':
        y=WF.chart(WS.forward(mel,sfr,fam,th=th),mel,sfr,F.FAMILIES[fam],act,scale=DEC.DENS.get('_scale',[1]*4))
        return [(int(s_),d,int(y[s_,d])-1) for d in range(4) for s_ in np.where(y[:,d]>0)[0]]
    m,dev=model()
    out=np.zeros((n_steps,4,4),np.float32); CH=384
    with torch.no_grad():
        for s0 in range(0,n_steps,CH-64):
            s1=min(n_steps,s0+CH); f0=max(0,int(sfr[s0])-24); f1=min(T,int(sfr[s1-1])+25)
            t=lambda a:torch.from_numpy(np.ascontiguousarray(a))[None].to(dev)
            p=m(t(mel[f0:f1]),t(mx[f0:f1]),t(sfr[s0:s1]-f0),t(np.arange(s0,s1)),torch.tensor([fam],device=dev)).softmax(-1)[0].cpu().numpy()
            a=0 if s0==0 else 32; out[s0+a:s1]=p[a:]
    # same lane grammar + repeat copying as the weight-space charts (placement stays the model's own ladder pick)
    y=WF.chart(out,mel,sfr,F.FAMILIES[fam],act,scale=DEC.DENS.get('_scale',[1]*4),quota=False,viterbi=True,motif=True)
    return [(int(s_),d,int(y[s_,d])-1) for d in range(4) for s_ in np.where(y[:,d]>0)[0]]
def tile_track(src_rest,length_ticks,period):
    """Repeat a slot track's events every `period` ticks up to length_ticks (keeps the name once)."""
    out=[]; body=[r for r in src_rest if not (r[1]=='meta' and r[2] in(3,0x2F))]; name=[r for r in src_rest if r[1]=='meta' and r[2]==3][:1]
    out+= [[0,'meta',3,name[0][3]]] if name else []
    rep=0
    while rep*period<length_ticks:
        for r in body:
            t=r[0]+rep*period
            if r[0]<period and t<length_ticks: out.append([t]+r[1:4])
        rep+=1
    return out
def chart_tracks(upload_path,job,progress,kind):
    """Beat grid, Demucs stems and one model chart per stem, written under `job`. Shared by run() and web_chart()."""
    progress('Loading audio',0.02); mix=load_audio(upload_path)
    progress('Finding the beat',0.06); bt=beats.track(mix,SR); lead=int(round(bt['lead_sec']*SR))
    mix=np.concatenate([np.zeros((lead,2),np.float32),mix]); per=bt['period']; tempos=[[0,int(round(per*1e6))]]
    padded=os.path.join(job,'padded.wav'); sf.write(padded,mix,SR,subtype='FLOAT')
    progress('Splitting instruments',0.12)
    stems={k:load_audio(p) for k,p in separate.separate(padded,os.path.join(job,'stems'),progress=lambda f:progress('Splitting instruments',0.12+0.5*f)).items()}
    n=min(len(mix),*[len(v) for v in stems.values()]); mix=mix[:n]; stems={k:v[:n] for k,v in stems.items()}
    # tracks with almost no sound borrow a frequency band from a busier stem
    rms={k:float(np.sqrt(np.mean(v**2))) for k,v in stems.items()}; loud=max(rms.values())
    fills=[('other',None,700),('other',700,None),('drums',None,200),('drums',5000,None)]; used=set()
    for key,_,_,_ in LAYOUT:
        if rms[key]<0.03*loud:
            for src,lo,hi in fills:
                if (src,lo,hi) in used or rms[src]<0.03*loud: continue
                stems[key]=band(stems[src],lo,hi); used.add((src,lo,hi)); break
    progress('Charting',0.65)
    mix_mel=F.logmel(mix.mean(1),SR).astype(np.float32)
    total_ticks=int(n/SR/per*F.TPQ); n_steps=total_ticks//F.STEP_TICKS; first_step=int(math.ceil(bt['lead_sec']/per*F.TPQ/F.STEP_TICKS))
    th=thresholds(kind); tracks=[]
    for i,(key,label,letter,cfg) in enumerate(LAYOUT):
        progress('Charting %s'%label,0.65+0.2*i/6)
        gems=predict_track(stems[key],mix_mel,n_steps,tempos,F.family(label),th,kind)
        gems=[[s*F.STEP_TICKS,d,l,F.STEP_TICKS*3 if F.STEP_TICKS*3<=120 else 120,96] for s,d,l in gems if s>=first_step+F.STEPS_PER_BEAT*4]
        tracks.append({'index':i+1,'name':'T%d CATCH:%s:%s'%(i+1,letter,label),'kind':'catch','label':label,'gems':sorted(gems),
                       'gem_meta':[[0,0x80,0x40,None,None]]*len(gems),'rest':[[0,'meta',3,('T%d CATCH:%s:%s'%(i+1,letter,label)).encode().hex()]],'eot':total_ticks})
    return mix,stems,n,per,tempos,bt,rms,loud,total_ticks,tracks
def web_chart(upload_path,job,title,artist,progress=lambda stage,frac=None:None,kind='trained'):
    """Audio file -> chart for the web editor, no game files needed. The beat-aligned audio goes to job/audio.flac."""
    os.makedirs(job,exist_ok=True)
    mix,stems,n,per,tempos,bt,rms,loud,total_ticks,tracks=chart_tracks(upload_path,job,progress,kind)
    progress('Writing audio',0.9); sf.write(os.path.join(job,'audio.flac'),np.clip(mix,-1,1),SR,format='FLAC',subtype='PCM_16')
    return {'meta':{'title':title,'artist':artist,'bpm':round(60/per,1),'section_start_bars':[],'song_info':[],'enable_order':[1,2,3,4,5,6]},
            'tpq':F.TPQ,'tempos':tempos,'timesig':[[0,4,4]],'world':[],'length_ticks':total_ticks,
            'tracks':[{k:t[k] for k in ('index','name','kind','label','gems')} for t in tracks]}
def run(upload_path,slot,title,artist,progress=lambda stage,frac=None:None,kind='trained',donor=None):
    """slot: song id the files go to. A slot that is not a shipped song is a new song: `donor` (a shipped song id,
    or the one saved with the slot's earlier run) supplies the world and click tracks, arena and score goals."""
    new=not os.path.isdir(os.path.join(SONGS,slot))
    if new:
        upj=os.path.join(EDITS,slot,'upload.json')
        donor=donor or (json.load(open(upj)).get('donor') if os.path.exists(upj) else None)
        if not donor or not os.path.isdir(os.path.join(SONGS,donor)): raise ValueError('a new song needs a shipped donor song')
    else: donor=slot
    os.makedirs(EDITS,exist_ok=True); job=os.path.join(UPLOADS,slot); os.makedirs(job,exist_ok=True)
    mix,stems,n,per,tempos,bt,rms,loud,total_ticks,tracks=chart_tracks(upload_path,job,progress,kind)
    progress('Writing song files',0.88)
    slot_chart=chart.load(os.path.join(SONGS,donor,donor+'.mid')); side={t['kind']:t for t in slot_chart['tracks'] if t['kind'] in('click','world')}
    slot_len=max(t['eot'] for t in slot_chart['tracks']); period=max(TPB,(slot_len//TPB)*TPB)
    us=tempos[0][1]
    head={'index':0,'name':'?','kind':'other','label':'?','gems':[],'gem_meta':[],'eot':0,
          'rest':[[0,'meta',3,'3f'],[0,'meta',0x51,us.to_bytes(3,'big').hex()],[0,'meta',0x58,'04021808']]}
    fs_={'index':7,'name':'T7 FREESTYLE','kind':'freestyle','label':'T7 FREESTYLE','gems':[],'gem_meta':[],'eot':0,'rest':[[0,'meta',3,b'T7 FREESTYLE'.hex()]]}
    click={'index':8,'name':'BG_CLICK','kind':'click','label':'BG_CLICK','gems':[],'gem_meta':[],'eot':total_ticks,'rest':tile_track(side['click']['rest'],total_ticks,period)}
    world={'index':9,'name':'WORLD','kind':'world','label':'WORLD','gems':[],'gem_meta':[],'eot':total_ticks,'rest':tile_track(side['world']['rest'],total_ticks,period)}
    c={'tpq':F.TPQ,'tracks':[head]+tracks+[fs_,click,world],'tempos':tempos,'timesig':[[0,4,4]],'world':[]}
    out=os.path.join(job,'out'); os.makedirs(out,exist_ok=True)
    mp=os.path.join(out,slot+'.mid'); open(mp,'wb').write(chart.save(c)); open(mp+'_ps3','wb').write(midps3.compile_mid(mp))
    # audio: 6 stereo stems, mono freestyle (silent), stereo background (whatever the stems missed)
    resid=mix-sum(stems[k] for k,_,_,_ in LAYOUT)
    chans=[stems[k][:,j] for k,_,_,_ in LAYOUT for j in (0,1)]+[np.zeros(n,np.float32)]+[resid[:,0],resid[:,1]]
    A=np.stack(chans,1); A/=max(1.0,float(np.abs(A).max())/0.99)
    buf=io.BytesIO()
    with sf.SoundFile(buf,'w',SR,A.shape[1],format='OGG',subtype='VORBIS') as fo:   # one-shot write of long audio crashes libsndfile
        for i in range(0,len(A),SR*5): fo.write(A[i:i+SR*5])
    open(os.path.join(out,slot+'.mogg'),'wb').write(mogg.build(buf.getvalue()))
    # config from the slot's (or donor's) file: keep arena, unlock, description; replace audio, length, sections, text
    src=open(os.path.join(SONGS,donor,donor+'.moggsong'),encoding='latin-1').read()
    keep=lambda key,default: (re.search(r'\(%s\b[^()]*(?:\([^()]*\)[^()]*)*\)'%key,src) or [default])[0]
    bars=total_ticks//TPB; secs=[max(5,int(bars*f)) for f in (0.25,0.5,0.75)]
    prefix='' if new else (re.search(r'title_short "(\d+\.)',src) or [None,''])[1]
    old_gems=[t for t in slot_chart['tracks'] if t['kind']=='catch']; new_counts=[sum(1 for t in tracks for g in t['gems'] if g[1]==d) for d in range(4)]
    old_counts=[max(1,sum(1 for t in old_gems for g in t['gems'] if g[1]==d)) for d in range(4)]
    sg=re.search(r'\(score_goal\s*((?:\(\s*[\d\s]+\)\s*)+)\)',src); rows=[list(map(int,r.split())) for r in re.findall(r'\(([\d\s]+)\)',sg.group(1))] if sg else [[500,800,2000]]*4
    rows=[[max(1,int(v*new_counts[d]/old_counts[d])) for v in row] for d,row in enumerate(rows)]
    esc=lambda s:' '.join(s.split()).encode('utf-8').decode('latin-1').replace('\\','\\\\').replace('"','\\q')   # file text carries UTF-8 bytes as latin-1
    txt='''(mogg_path %s.mogg)
(midi_path %s.mid)
(song_info (length %d:0:0) (countin 4))
(tracks ((drums (0 1) event:/SONG_BUS) (bass (2 3) event:/SONG_BUS) (guitar (4 5) event:/SONG_BUS) (keys (6 7) event:/SONG_BUS) (synth (8 9) event:/SONG_BUS) (vox (10 11) event:/SONG_BUS) (freestyle (12) event:/FREESTYLE_FX_1) (bg_click (13 14) event:/SONG_BUS)))
(pans (-1.0 1.0 -1.0 1.0 -1.0 1.0 -1.0 1.0 -1.0 1.0 -1.0 1.0 0.0 -1.0 1.0))
(vols (-1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 -1.0 0.0 -1.0 -1.0))
(active_track_db 0.0 0.0 0.0 0.0 0.0 0.0 0.0)
%s
(score_goal %s)
%s
(enable_order (1 2 3 4 5 6))
(section_start_bars %d %d %d)
(title "%s")
(title_short "%s")
(artist "%s")
(artist_short "%s")
%s
%s
(bpm %d)
(preview_start_ms %d)
(preview_length_ms 15000)
'''%(slot,slot,max(8,bars-4),keep('arena_path','(arena_path ConstructoP2)'),' '.join('(%d %d %d)'%tuple(r) for r in rows),
      keep('tunnel_scale','(tunnel_scale 1.0)'),secs[0]-4,secs[1]-4,secs[2]-4,esc(title),esc(((prefix+' ') if prefix else '')+title),esc(artist),esc(artist),
      ('(desc song_desc_%s)'%slot if new else keep('desc','(desc song_desc_%s)'%slot)),keep('unlock_requirement','(unlock_requirement unlock_requirement_playcount)'),round(60/per),int(n/SR*1000*0.4))
    open(os.path.join(out,slot+'.moggsong'),'w',encoding='latin-1').write(txt)
    open(os.path.join(out,slot+'.moggsong_dta_ps3'),'wb').write(dtb.compile_text(txt))
    made=[slot+e for e in ('.mid','.mid_ps3','.mogg','.moggsong_dta_ps3','.moggsong')]
    if new:   # placeholder art: the donor's cover and its texture settings
        for e in ('.png_ps3','.png.dta_dta_ps3'): shutil.copyfile(os.path.join(SONGS,donor,donor+e),os.path.join(out,slot+e)); made.append(slot+e)
    meta={'id':slot,'new':new,'model':kind,'source':os.path.basename(upload_path),'title':title,'artist':artist,'bpm':60/per,'lead_sec':bt['lead_sec'],'beat_fit_rms_ms':bt['fit_rms_ms'],
          'gems_per_difficulty':new_counts,'filled_from_bands':[k for k,_,_,_ in LAYOUT if rms[k]<0.03*loud]}
    if new: meta.update(donor=donor,desc='Custom song'+(' by '+' '.join(artist.split()) if artist.strip() else '')+'.')
    json.dump(meta,open(os.path.join(out,'upload.json'),'w'),indent=1)
    dst=os.path.join(EDITS,slot); os.makedirs(dst,exist_ok=True)
    for f in made+['upload.json']: os.replace(os.path.join(out,f),os.path.join(dst,f))
    progress('Done',1.0); return meta
if __name__=='__main__':
    print(json.dumps(run(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],progress=lambda s,f=None:print(s,f,flush=True),kind=sys.argv[5] if len(sys.argv)>5 else 'trained',donor=sys.argv[6] if len(sys.argv)>6 else None),indent=1))
