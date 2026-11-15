"""MiRG Chart Editor (Multi Instrument Rhythm Game Chart Editor): local server. Run: python3 server.py [port]  then open http://localhost:PORT/"""
import json,os,sys,re,glob,collections,struct
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(ROOT,'tools'))
import chart,midps3,dtb,mogg,ark,songcfg,unicodedata
WORK=os.path.join(ROOT,'work'); SONGS=os.path.join(WORK,'ark','ps3','songs'); USRDIR=os.path.join(WORK,'pkg','USRDIR')
EDITS=os.path.join(WORK,'edits'); BUILD=os.path.join(WORK,'build','USRDIR'); EDITOR=os.path.join(ROOT,'editor')
SKIP={'tut0','tut1','tutc'}
DEFAULT_DONOR='donot'   # shipped extra whose world and click tracks, arena and score goals a new song borrows
NEW_FILES=('.mid','.mid_ps3','.mogg','.moggsong','.moggsong_dta_ps3','.png_ps3','.png.dta_dta_ps3')
def shipped(): return set(os.listdir(SONGS)) if os.path.isdir(SONGS) else set()
def is_new(sid):
    """A song that exists only in work/edits (added, not a replaced slot) and finished building."""
    f=os.path.join(EDITS,sid,sid+'.moggsong')
    return sid not in shipped() and os.path.exists(os.path.join(EDITS,sid,'upload.json')) and os.path.exists(f) and os.path.getsize(f)>0
_CFG={}
def cfg_files():
    """The eight shipped configs a new song touches, read from the archive in work/pkg (read once)."""
    if not _CFG:
        _,d=ark.load(USRDIR); _CFG.update({n:ark.read_file(USRDIR,d,d['files'][ark.find(d,n)]) for n in songcfg.PATHS})
    return dict(_CFG)
def slug(title):
    t=unicodedata.normalize('NFKD',title).encode('ascii','ignore').decode().lower(); t=re.sub(r'[^a-z0-9]','',t)[:20]
    return t if re.match(r'[a-z]',t) else 'song'+t
def check_new_id(sid):
    """Error text if `sid` cannot be a new song id, else None."""
    if not re.fullmatch(r'[a-z][a-z0-9]{1,23}',sid): return 'The song id must be 2 to 24 lowercase letters or digits, starting with a letter.'
    if sid in shipped() or os.path.exists(os.path.join(EDITS,sid)): return 'The id %s is already used by a song.'%sid
    why=songcfg.taken(cfg_files(),sid)
    return 'The id %s cannot be used: %s.'%(sid,why) if why else None
def kids_to_dict(tree):
    out={}
    for t,v in tree['kids']:
        if t==0x10 and v['kids'] and v['kids'][0][0]==5:
            key=v['kids'][0][1].decode('latin-1'); vals=[]
            for tt,vv in v['kids'][1:]:
                if tt==0: vals.append(struct.unpack('<i',vv)[0])
                elif tt==1: vals.append(round(struct.unpack('<f',vv)[0],4))
                elif tt in(5,0x12): vals.append(vv.decode('latin-1'))
                elif tt==0x10: vals.append(kids_to_dict(vv) or [ (struct.unpack('<i',x)[0] if y==0 else round(struct.unpack('<f',x)[0],4) if y==1 else x.decode('latin-1') if y in(5,0x12) else None) for y,x in vv['kids']])
            out[key]=vals[0] if len(vals)==1 else vals
    return out
def song_file(sid,ext):
    e=os.path.join(EDITS,sid,sid+ext); return e if os.path.exists(e) else os.path.join(SONGS,sid,sid+ext)
def song_meta(sid):
    src=open(song_file(sid,'.moggsong'),encoding='latin-1').read()
    return kids_to_dict(dtb.parse_text(src))
def mid_path(sid):
    e=os.path.join(EDITS,sid,sid+'.mid'); return e if os.path.exists(e) else os.path.join(SONGS,sid,sid+'.mid')
def song_list():
    out=[]; newer=[d for d in (os.listdir(EDITS) if os.path.isdir(EDITS) else []) if is_new(d)]
    for d in sorted(shipped()|set(newer)):
        if d in SKIP or (d not in newer and not os.path.exists(os.path.join(SONGS,d,d+'.moggsong'))): continue
        m=song_meta(d); upf=os.path.join(EDITS,d,'upload.json'); up=os.path.exists(upf)
        model=json.load(open(upf)).get('model') if up else None
        out.append({'id':d,'title':m.get('title',d),'artist':m.get('artist',''),'bpm':m.get('bpm'),'edited':os.path.exists(os.path.join(EDITS,d,d+'.mid')),'uploaded':up,'model':model,'new':d in newer})
    return out
def song_json(sid):
    c=chart.load(mid_path(sid)); m=song_meta(sid)
    return {'id':sid,'meta':{k:m.get(k) for k in('title','artist','bpm','section_start_bars','song_info','enable_order','preview_start_ms','preview_length_ms')},
            'tpq':c['tpq'],'tempos':c['tempos'],'timesig':c['timesig'],'world':c['world'],
            'length_ticks':max(t['eot'] for t in c['tracks']),'edited':mid_path(sid).startswith(EDITS),'new':is_new(sid),
            'tracks':[{'index':t['index'],'name':t['name'],'kind':t['kind'],'label':t['label'],'gems':t['gems']} for t in c['tracks']]}
def save_song(sid,body):
    c=chart.load(mid_path(sid)); by_index={t['index']:t for t in c['tracks']}
    for nt in body.get('tracks',[]):
        t=by_index[nt['index']]
        if t['kind']!='catch': continue
        old={}
        for g,m in zip(t['gems'],t['gem_meta']): old.setdefault((g[0],g[1],g[2]),[]).append((g,m))
        chans=collections.Counter(m[0] for m in t['gem_meta']); ch=chans.most_common(1)[0][0] if chans else 0
        vels=collections.Counter(g[4] for g in t['gems']); vel=vels.most_common(1)[0][0] if vels else 96
        durs=collections.Counter(g[3] for g in t['gems']); dur=durs.most_common(1)[0][0] if durs else 120
        gems=[];meta=[]
        for g in sorted(nt['gems']):
            tick,d,l=int(g[0]),int(g[1]),int(g[2])
            if not(0<=d<=3 and 0<=l<=2 and tick>=0): raise ValueError('bad gem %r'%g)
            k=(tick,d,l)
            if old.get(k):
                want=int(g[3]) if len(g)>3 and g[3] else None; pool=old[k]
                pick=next((i for i,(og,_) in enumerate(pool) if want is None or og[3]==want),0)
                og,om=pool.pop(pick); gems.append([tick,d,l,og[3],og[4]]); meta.append(om)
            else: gems.append([tick,d,l,int(g[3]) if len(g)>3 and g[3] else dur,int(g[4]) if len(g)>4 and g[4] else vel]); meta.append([ch,0x80|ch,0x40,None,None])
        t['gems']=gems; t['gem_meta']=meta
        t['eot']=max(t['eot'],max([g[0]+g[3] for g in gems],default=0))
    os.makedirs(os.path.join(EDITS,sid),exist_ok=True)
    mp=os.path.join(EDITS,sid,sid+'.mid'); open(mp,'wb').write(chart.save(c))
    comp=midps3.compile_mid(mp); open(mp+'_ps3','wb').write(comp)
    return {'ok':True,'files':[mp,mp+'_ps3'],'gems':sum(len(t['gems']) for t in c['tracks']),'compiled_bytes':len(comp)}
def revert(sid,confirmed=False):
    """Drop the saved edit of a song. A new song has no original to fall back to, so this removes the song and
    only runs when the caller says the user confirmed (the editor asks first)."""
    if is_new(sid) and not confirmed: raise ValueError('confirm is required to delete a new song')
    if any(j['slot']==sid and not j['done'] for j in JOBS.values()): raise ValueError('this song is still being made')
    d=os.path.join(EDITS,sid)
    for f in glob.glob(os.path.join(d,'*')): os.remove(f)
    if os.path.isdir(d): os.rmdir(d)
    return {'ok':True}
def build():
    reps={}; skipped=[]; newsongs=[]
    for sid in sorted(os.listdir(EDITS)) if os.path.isdir(EDITS) else []:
        found={ext:os.path.join(EDITS,sid,sid+ext) for ext in NEW_FILES if os.path.exists(os.path.join(EDITS,sid,sid+ext))}
        if any(os.path.getsize(p)==0 for p in found.values()): skipped.append(sid); continue   # an interrupted upload left an empty file
        if sid not in shipped():
            if not is_new(sid) or any(e not in found for e in NEW_FILES): skipped.append(sid); continue
            newsongs.append(sid)
        for ext,p in found.items(): reps['ps3/songs/%s/%s%s'%(sid,sid,ext)]=open(p,'rb').read()
    if not reps: return {'ok':False,'error':'no edited songs to build'+(' (incomplete: %s)'%', '.join(skipped) if skipped else '')}
    if newsongs:   # song list, unlock rows and text for each new song, from the shipped configs
        cfg=cfg_files()
        for sid in sorted(newsongs):
            up=json.load(open(os.path.join(EDITS,sid,'upload.json'))); cfg=songcfg.add_song(cfg,sid,up.get('title') or sid,up.get('artist',''),up.get('desc') or 'Custom song.')
        reps.update(cfg)
    part,size=ark.patch(USRDIR,BUILD,reps)
    # verify through the new hdr: every entry resolves through the bucket table, and each written file reads back from the parts
    key,d=ark.decrypt_hdr(open(os.path.join(BUILD,'main_ps3.hdr'),'rb').read()); d=ark.parse(d)
    names=collections.Counter(f['name'] for f in d['files'])
    bad=['table: %s'%f['name'] for i,f in enumerate(d['files']) if names[f['name']]==1 and ark.find(d,f['name'])!=i]
    def rf(f):
        starts=[];acc=0
        for s in d['part_sizes']: starts.append(acc); acc+=s
        for i,st in enumerate(starts):
            if st<=f['offset']<st+max(d['part_sizes'][i],1):
                base=BUILD if d['part_names'][i]==part else USRDIR
                with open(os.path.join(base,d['part_names'][i]),'rb') as fh: fh.seek(f['offset']-st); return fh.read(f['size'])
    _,orig=ark.load(USRDIR); oldnames={f['name'] for f in orig['files']}; added=sorted(n for n in reps if n not in oldnames)
    for n,b in reps.items():
        i=ark.find(d,n)
        if i<0 or rf(d['files'][i])!=b: bad.append(n)
    untouched=[f for f in orig['files'] if f['name'] not in reps and f['size']>0][:50]
    for f in untouched:
        i=ark.find(d,f['name'])
        if i<0 or rf(d['files'][i])!=ark.read_file(USRDIR,orig,f): bad.append(f['name'])
    return {'ok':not bad,'out_dir':BUILD,'part':part,'part_bytes':size,'files':sorted(n for n in reps if n in oldnames),'added':added,'new_songs':sorted(newsongs),'skipped':skipped,
            'entries':len(d['files']),'verify_failures':bad,
            'install':'Copy main_ps3.hdr and %s into the installed game USRDIR (RPCS3: dev_hdd0/game/NPEB02398/USRDIR). Keep a backup of the original main_ps3.hdr.'%part}
_audio={}
def audio(sid):
    p=song_file(sid,'.mogg'); key=(p,os.path.getmtime(p))
    if key not in _audio:
        b=open(p,'rb').read(); _audio.clear(); _audio[key]=b[mogg.parse(b)['ogg_offset']:]
    return _audio[key]
def audio_info(sid):
    src=open(song_file(sid,'.moggsong'),encoding='latin-1').read(); tree=dtb.parse_text(src); m=kids_to_dict(tree); tr=[]
    for t,v in tree['kids']:
        if t==0x10 and v['kids'] and v['kids'][0]==(5,b'tracks'):
            for t2,inner in v['kids'][1:]:
                if t2!=0x10: continue
                for t3,ent in inner['kids']:
                    if t3==0x10 and len(ent['kids'])>=2 and ent['kids'][0][0]==5:
                        name=ent['kids'][0][1].decode('latin-1'); chans=ent['kids'][1]
                        if chans[0]==0x10: ch=[struct.unpack('<i',x)[0] for y,x in chans[1]['kids'] if y==0]
                        elif chans[0]==0: ch=[struct.unpack('<i',chans[1])[0]]
                        else: ch=[]
                        tr.append({'name':name,'channels':ch})
    return {'tracks':tr,'pans':m.get('pans'),'vols':m.get('vols')}
import threading,uuid,time,traceback
JOBS={}
def start_upload(slot,title,artist,filename,data,kind='trained',mode='replace',new_id='',donor=''):
    """mode replace: `slot` is the song to overwrite. mode add: a new song under `new_id` (made from the title when
    empty), borrowing template parts from `donor` (default DEFAULT_DONOR); `slot` is ignored."""
    if kind not in('trained','weightspace'): raise ValueError('model must be trained or weightspace')
    if mode not in('replace','add'): raise ValueError('mode must be replace or add')
    if not title.strip(): raise ValueError('title is required')
    ext=os.path.splitext(filename)[1].lower()
    if ext not in('.wav','.flac','.mp3','.ogg','.aiff','.aif'): raise ValueError('use WAV, FLAC, MP3, OGG or AIFF')
    if mode=='add':
        donor=donor or DEFAULT_DONOR
        if donor not in shipped() or donor in SKIP or not os.path.exists(os.path.join(SONGS,donor,donor+'.moggsong')): raise ValueError('donor %r is not a shipped song'%donor)
        if new_id:
            err=check_new_id(new_id)
            if err: raise ValueError(err)
        else:
            base=slug(title); new_id=base; n=1
            while check_new_id(new_id):
                n+=1; new_id=base+str(n)
                if n>99: raise ValueError('could not find a free song id for this title')
        slot=new_id
    if any(j['slot']==slot and not j['done'] for j in JOBS.values()): raise ValueError('this song is already being made')
    jid=uuid.uuid4().hex[:8]; up=os.path.join(WORK,'uploads',slot); os.makedirs(up,exist_ok=True)
    for f in glob.glob(os.path.join(up,'stems','*'))+glob.glob(os.path.join(up,'source.*')): os.remove(f)
    src=os.path.join(up,'source'+ext); open(src,'wb').write(data)
    JOBS[jid]={'id':jid,'slot':slot,'mode':mode,'title':title.strip(),'stage':'Queued','progress':0.0,'done':False,'error':None,'started':time.time()}
    def work():
        try:
            import importlib; sys.path.insert(0,os.path.join(ROOT,'ml')); import autochart
            def prog(stage,frac=None):
                JOBS[jid]['stage']=stage
                if frac is not None: JOBS[jid]['progress']=round(float(frac),3)
            JOBS[jid]['result']=autochart.run(src,slot,title.strip(),artist.strip(),progress=prog,kind=kind,donor=donor if mode=='add' else None)
        except Exception as e:
            JOBS[jid]['error']=repr(e); JOBS[jid]['trace']=traceback.format_exc()[-2000:]
        JOBS[jid]['done']=True
    threading.Thread(target=work,daemon=True).start(); return JOBS[jid]
import threading as _th
_PLAY_LOCK=_th.Lock()
def play_mix(sid):
    with _PLAY_LOCK: return _play_mix(sid)
def _play_mix(sid):
    """Light play-test audio: one mono channel per chart track (in chart order) + one background channel,
    mixer volumes applied, 16-bit WAV at 32 kHz. About a third of the browser memory of the full MOGG."""
    import io as _io,numpy as np,soundfile as sf,librosa
    src=song_file(sid,'.mogg'); cache=os.path.join(WORK,'cache'); os.makedirs(cache,exist_ok=True)
    out=os.path.join(cache,'%s_play_%d.wav'%(sid,int(os.path.getmtime(src)))); meta=out+'.json'
    if not (os.path.exists(out) and os.path.exists(meta)):
        for old in glob.glob(os.path.join(cache,sid+'_play_*')): os.remove(old)
        info=audio_info(sid); b=open(src,'rb').read(); x,sr=sf.read(_io.BytesIO(b[mogg.parse(b)['ogg_offset']:]),dtype='float32')
        vols=info.get('vols') or [0]*x.shape[1]; lin=np.array([10**(float(v)/20) for v in vols][:x.shape[1]]+[1.0]*max(0,x.shape[1]-len(vols)),np.float32)
        playable=[t for t in info['tracks'] if not t['name'].lower().startswith(('freestyle','bg_click'))]
        used=set(); cols=[]; names=[]
        for t in playable[:6]:
            ch=[c for c in t['channels'] if c<x.shape[1]]; used|=set(ch)
            cols.append((x[:,ch]*lin[ch]).sum(1)*(0.5 if len(ch)>1 else 1.0) if ch else np.zeros(len(x),np.float32)); names.append(t['name'])
        rest=[c for c in range(x.shape[1]) if c not in used]
        cols.append((x[:,rest]*lin[rest]).sum(1)*0.5 if rest else np.zeros(len(x),np.float32)); names.append('background')
        y=np.stack(cols,1); peak=float(np.abs(y.sum(1)).max()) or 1.0; y*=min(1.0,0.95/peak)
        y=librosa.resample(y.T,orig_sr=sr,target_sr=32000).T
        sf.write(out+'.part',y,32000,format='WAV',subtype='PCM_16'); os.replace(out+'.part',out)
        json.dump({'tracks':[{'name':n,'channels':[i]} for i,n in enumerate(names)],'pans':[0.0]*len(names),'vols':[0.0]*len(names),'sample_rate':32000},open(meta,'w'))
    return out,meta
def audio_wav(sid):
    with _PLAY_LOCK: return _audio_wav(sid)
def _audio_wav(sid):
    """Same channels as the MOGG, as 16-bit WAV at 32 kHz: decodes in every browser and needs a third less memory."""
    import io as _io,numpy as np,soundfile as sf,librosa
    src=song_file(sid,'.mogg'); cache=os.path.join(WORK,'cache'); os.makedirs(cache,exist_ok=True)
    out=os.path.join(cache,'%s_%d.wav'%(sid,int(os.path.getmtime(src))))
    if not os.path.exists(out):
        for old in glob.glob(os.path.join(cache,sid+'_*.wav')): os.remove(old)
        b=open(src,'rb').read(); x,sr=sf.read(_io.BytesIO(b[mogg.parse(b)['ogg_offset']:]),dtype='float32')
        y=librosa.resample(x.T,orig_sr=sr,target_sr=32000).T
        sf.write(out+'.part',y,32000,format='WAV',subtype='PCM_16'); os.replace(out+'.part',out)
    return open(out,'rb').read()
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _send(self,code,body,ctype='application/json'):
        if not isinstance(body,(bytes,bytearray)): body=json.dumps(body).encode()
        self.send_response(code); self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def _sid(self,p):
        sid=p.split('/')[-1]
        if not re.fullmatch(r'[a-z0-9_]+',sid) or not (os.path.isdir(os.path.join(SONGS,sid)) or is_new(sid)): raise KeyError(sid)
        return sid
    def do_GET(self):
        p=self.path.split('?')[0]
        try:
            if p=='/api/songs': return self._send(200,song_list())
            if p.startswith('/api/song/'): return self._send(200,song_json(self._sid(p)))
            if p.startswith('/api/audio_info/'): return self._send(200,audio_info(self._sid(p)))
            if p.startswith('/api/audio/'): return self._send(200,audio(self._sid(p)),'audio/ogg')
            if p.startswith('/api/audio_wav/'): return self._send(200,audio_wav(self._sid(p)),'audio/wav')
            if p.startswith('/api/play_audio/'): return self._send(200,open(play_mix(self._sid(p))[0],'rb').read(),'audio/wav')
            if p.startswith('/api/play_info/'): return self._send(200,json.load(open(play_mix(self._sid(p))[1])))
            if p.startswith('/api/job/'):
                j=JOBS.get(p.split('/')[-1]); return self._send(200 if j else 404,j or {'error':'unknown job'})
            f=os.path.normpath(os.path.join(EDITOR,(p.lstrip('/') or 'index.html')))
            if f.startswith(EDITOR) and os.path.isfile(f):
                ct={'html':'text/html','js':'text/javascript','css':'text/css'}.get(f.rsplit('.',1)[-1],'application/octet-stream')
                return self._send(200,open(f,'rb').read(),ct+'; charset=utf-8' if ct.startswith('text') else ct)
            self._send(404,{'error':'not found'})
        except KeyError as e: self._send(404,{'error':'unknown song %s'%e})
        except Exception as e: self._send(500,{'error':repr(e)})
    def do_HEAD(self):
        self.send_response(200 if self.path in('/','/index.html') or self.path.startswith('/api/') else 404); self.end_headers()
    def do_POST(self):
        p=self.path.split('?')[0]
        try:
            n=int(self.headers.get('Content-Length') or 0)
            if p=='/api/upload':
                from urllib.parse import urlparse,parse_qs
                q={k:v[0] for k,v in parse_qs(urlparse(self.path).query).items()}; mode=q.get('mode','replace')
                slot=self._sid('/x/'+q.get('slot','')) if mode=='replace' else ''
                return self._send(200,start_upload(slot,q.get('title',''),q.get('artist',''),q.get('name','upload.wav'),self.rfile.read(n),q.get('model','trained'),mode,q.get('id',''),q.get('donor','')))
            body=json.loads(self.rfile.read(n) or b'{}')
            if p.startswith('/api/song/'): return self._send(200,save_song(self._sid(p),body))
            if p.startswith('/api/revert/'): return self._send(200,revert(self._sid(p),body.get('confirm') is True))
            if p=='/api/build': return self._send(200,build())
            self._send(404,{'error':'not found'})
        except Exception as e: self._send(500,{'error':repr(e)})
if __name__=='__main__':
    port=int(sys.argv[1]) if len(sys.argv)>1 else 8651
    print('MiRG Chart Editor on http://localhost:%d/'%port); ThreadingHTTPServer(('127.0.0.1',port),H).serve_forever()
