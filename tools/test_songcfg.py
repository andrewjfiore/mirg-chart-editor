"""New-song config helper checks. usage: python3 tools/test_songcfg.py ROOT   (ROOT holds ps3/config and ps3/ui, e.g. work/ark)"""
import sys,os; sys.path.insert(0,os.path.dirname(__file__)); import dtb,songcfg as S
root=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'..','work','ark')
files={p:open(os.path.join(root,p),'rb').read() for p in S.PATHS}
rt=sum(dtb.write(dtb.read(b))==b for b in files.values()); print('binary round trip of the 8 configs: %d/8'%rt); assert rt==8
def kids(b): return [(t,v) for t,v in dtb.read(b)['kids']]
# 1. add one song: all 8 files change, read back says what was written, output round-trips
a=S.add_song(files,'testsong','Test Song','Some Artist','Custom song by Some Artist.')
assert all(a[p]!=files[p] for p in S.PATHS) and all(dtb.write(dtb.read(b))==b for b in a.values())
r=S.read_song(a,'testsong'); print('read back:',r)
assert (r['symbol'],r['region'],r['type'],r['include'],r['token'],r['unlock_row'])==('TESTSONG','World3','kSongExtra','../Songs/testsong/testsong.moggsong','song_testsong',True)
for loc in S.LOCALES: assert r['locale'][loc]=={'song_testsong':'Test Song - Some Artist','song_desc_testsong':'Custom song by Some Artist.'},loc
none=S.read_song(files,'testsong'); assert none['region'] is None and none['token'] is None and not none['unlock_row'] and not any(none['locale'].values())
# 2. nothing shipped moved: the old content is a prefix of the new, except the one unlock row inserted after DONOTRETREAT's
for p in [S.LOCALE%l for l in S.LOCALES]: assert kids(a[p])[:-2]==kids(files[p]),p
old=dtb.read(files[S.SONGS]); new=dtb.read(a[S.SONGS]); assert new['kids'][:2]==old['kids'][:2]
w_old=[v for t,v in old['kids'] if v['kids'][0][1]==b'World3'][0]; w_new=[v for t,v in new['kids'] if v['kids'][0][1]==b'World3'][0]
assert w_new['kids'][:-1]==w_old['kids'] and len(w_new['kids'])==len(w_old['kids'])+1
dn=S._db(dtb.read(a[S.CFG])); do=S._db(dtb.read(files[S.CFG]))
tn,to=S._named(dn,b'unlock_tokens'),S._named(do,b'unlock_tokens'); assert tn['kids'][:-1]==to['kids'] and len(tn['kids'])==len(to['kids'])+1
cn,co=S._named(dn,b'campaign'),S._named(do,b'campaign'); gone=[k for k in cn['kids'] if k not in co['kids']]; assert len(gone)==1 and len(cn['kids'])==len(co['kids'])+1
assert [k for k in cn['kids'] if k!=gone[0]]==co['kids'] and [k for k in dn['kids'] if k[1] not in (tn,cn)]==[k for k in do['kids'] if k[1] not in (to,co)]
# 3. second song on top of the first, both read back; a name the configs use is refused
b=S.add_song(a,'other2','Other: "Two"','','Second.'); assert S.read_song(b,'other2')['locale']['fre']['song_other2']=='Other: "Two"' and S.read_song(b,'testsong')['unlock_row']
for bad,why in (('donotretreat','symbol of DONOT'),('donot','folder'),('world1','region'),('testsong','added above'),('multiplier','unlock token'),('Bad','format'),('9a','format')):
    try: S.add_song(b,bad,'x'); raise SystemExit('accepted %s'%bad)
    except ValueError as e: print('refused %-13s (%s): %s'%(bad,why,e))
assert S.taken(files,'brandnew') is None
# 4. text with accents is stored as UTF-8 like the shipped locale strings
c=S.add_song(files,'cafe','Café','Bärtsch'); assert S.read_song(c,'cafe')['locale']['eng']['song_cafe']=='Café - Bärtsch'
print('ok')
