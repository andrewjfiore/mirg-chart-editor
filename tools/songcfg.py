"""Add a new song to the shipped configs: amp_songs_config (song list), amp_config (unlock token and an unlock
row that opens it from the start) and the six locale_keep files (song_<id> and song_desc_<id>).
Works on the binary DTA files through dtb.read/write; every new node is a copy of a shipped neighbour."""
import copy,re,dtb
LOCALES=('eng','deu','esl','fre','ita','ptb')
CFG='ps3/config/amp_config.dta_dta_ps3'; SONGS='ps3/config/amp_songs_config.dta_dta_ps3'
LOCALE='ps3/ui/locale/%s/locale_keep.dta_dta_ps3'
PATHS=[CFG,SONGS]+[LOCALE%l for l in LOCALES]
SYM,STR,ARR,INC=5,0x12,0x10,0x21
def symbol(sid): return sid.upper()
def _head(n): return n['kids'][0][1] if n['kids'] and n['kids'][0][0]==SYM else None
def _arrays(n): return [v for t,v in n['kids'] if t==ARR]
def _named(n,key):
    r=[v for v in _arrays(n) if _head(v)==key]
    if len(r)!=1: raise KeyError('%r: %d matches'%(key,len(r)))
    return r[0]
def _db(cfg): return _named(cfg,b'db')
def _campaign_row(r,sym): return len(r['kids'])==4 and [k[1] for k in r['kids'][:3:2]]==[b'beat_num',b'kUnlockArena'] and r['kids'][3][1]==sym
def _tree(files,path): return dtb.read(files[path])
def taken(files,sid):
    """Why `sid` cannot be a new song id (a name the shipped configs already use), or None."""
    sym=symbol(sid).encode(); names=set()
    songs=_tree(files,SONGS)
    for w in _arrays(songs):
        names.add(_head(w))
        for s in _arrays(w): names.add(_head(s))
    for r in _arrays(_named(_db(_tree(files,CFG)),b'unlock_tokens')): names.add(_head(r))
    if sym in {x.upper() for x in names if x}: return 'the name %s is already used by a shipped song or region'%sym.decode()
    dirs={re.search(rb'/songs/([^/]+)/',v,re.I).group(1).lower() for w in _arrays(songs) for s in _arrays(w) for t,v in s['kids'] if t==INC}
    if sid.encode() in dirs: return 'a shipped song already uses the folder %s'%sid
    keys={_head(r) for r in _arrays(_tree(files,LOCALE%'eng'))}
    for k in (b'song_'+sid.encode(),b'song_desc_'+sid.encode()):
        if k in keys: return 'the text token %s is already used'%k.decode()
def add_song(files,sid,title,artist='',desc='',world='World3',ctype='kSongExtra'):
    """files: {archive path: bytes} holding PATHS. Returns a new dict with the song added to all eight files.
    Rejects an id the configs already use (see taken())."""
    if not re.fullmatch(r'[a-z][a-z0-9]*',sid): raise ValueError('song id must be lowercase letters and digits, starting with a letter')
    why=taken(files,sid)
    if why: raise ValueError(why)
    out=dict(files); sym=symbol(sid).encode()
    # song list: a copy of the last song of the region, with the new name, include path and type
    t=_tree(files,SONGS); w=_named(t,world.encode()); sib=[v for v in _arrays(w)][-1]; n=copy.deepcopy(sib)
    n['kids'][0]=(SYM,sym); n['kids'][1]=(INC,('../Songs/%s/%s.moggsong'%(sid,sid)).encode())
    ty=[v for v in _arrays(n) if _head(v)==b'type'][0]; ty['kids'][1]=(SYM,ctype.encode())
    w['kids'].append((ARR,n)); out[SONGS]=dtb.write(t)
    # unlock token and unlock row, copied from DONOTRETREAT (an extra that is open from the start)
    c=_tree(files,CFG); db=_db(c); toks=_named(db,b'unlock_tokens'); camp=_named(db,b'campaign')
    tok=copy.deepcopy([r for r in _arrays(toks) if _head(r)==b'DONOTRETREAT'][0])
    tok['kids'][0]=(SYM,sym); tok['kids'][1]=(SYM,b'song_'+sid.encode()); toks['kids'].append((ARR,tok))
    i=[j for j,(tt,r) in enumerate(camp['kids']) if tt==ARR and _campaign_row(r,b'DONOTRETREAT')][0]
    row=copy.deepcopy(camp['kids'][i][1]); row['kids'][3]=(SYM,sym); camp['kids'].insert(i+1,(ARR,row)); out[CFG]=dtb.write(c)
    # locale: song_<id> is "title - artist", song_desc_<id> the description; same text in every language
    name=(title+' - '+artist if artist else title).encode('utf-8'); dsc=desc.encode('utf-8')
    for loc in LOCALES:
        p=LOCALE%loc; lt=_tree(files,p)
        for key,val in ((b'song_'+sid.encode(),name),(b'song_desc_'+sid.encode(),dsc)):
            e=copy.deepcopy(lt['kids'][-1][1]); e['id']=lt['kids'][-1][1]['id']+1; e['kids']=[(SYM,key),(STR,val)]; lt['kids'].append((ARR,e))
        out[p]=dtb.write(lt)
    return out
def read_song(files,sid):
    """What the eight files say about `sid`, for checking: region, type, include path, token, unlock row, locale text."""
    sym=symbol(sid).encode(); r={'symbol':sym.decode(),'region':None,'type':None,'include':None,'token':None,'unlock_row':False,'locale':{}}
    for w in _arrays(_tree(files,SONGS)):
        for s in _arrays(w):
            if _head(s)==sym:
                r['region']=_head(w).decode(); r['include']=[v for t,v in s['kids'] if t==INC][0].decode()
                r['type']=[v['kids'][1][1] for v in _arrays(s) if _head(v)==b'type'][0].decode()
    db=_db(_tree(files,CFG))
    for x in _arrays(_named(db,b'unlock_tokens')):
        if _head(x)==sym: r['token']=x['kids'][1][1].decode()
    r['unlock_row']=any(_campaign_row(x,sym) for x in _arrays(_named(db,b'campaign')))
    for loc in LOCALES:
        kv={_head(e):e['kids'][1][1] for e in _arrays(_tree(files,LOCALE%loc))}
        r['locale'][loc]={k:kv[k.encode()].decode('utf-8') for k in ('song_'+sid,'song_desc_'+sid) if k.encode() in kv}
    return r
