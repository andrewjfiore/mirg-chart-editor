"""Archive index checks. usage: python3 tools/test_ark.py [USRDIR]   (default work/pkg/USRDIR, reads main_ps3.hdr only)"""
import sys,os,tempfile,collections; sys.path.insert(0,os.path.dirname(__file__)); import ark
usr=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'..','work','pkg','USRDIR')
enc=open(os.path.join(usr,'main_ps3.hdr'),'rb').read(); key,d=ark.load(usr)
n=len(d['files']); dup=[k for k,v in collections.Counter(f['name'] for f in d['files']).items() if v>1]
# 1. rebuilding the bucket table and links from the names alone gives back the shipped hdr byte for byte
links=[f['link'] for f in d['files']]; heads=ark.rebuild_table(d['files'])
same=heads==d['buckets'] and [f['link'] for f in d['files']]==links and ark.encrypt_hdr(ark.build(dict(d,buckets=heads)),key)==enc
print('rebuild of the shipped table, %d entries: identical hdr = %s'%(n,same)); assert same
# 2. every shipped path resolves through the table (repeated names, the __split_ark__ markers, resolve to a same-named entry)
bad=[f['name'] for i,f in enumerate(d['files']) if (ark.find(d,f['name'])!=i if f['name'] not in dup else d['files'][ark.find(d,f['name'])]['name']!=f['name'])]
print('shipped paths resolved through the table: %d/%d'%(n-len(bad),n)); assert not bad
# 3. patch with new files plus one replaced file: every old and new path resolves, old entries keep their data
new={'ps3/songs/zzt/zzt.%s'%e:(b'x'*(i+3)) for i,e in enumerate(('mid','mid_ps3','mogg','moggsong','moggsong_dta_ps3','png.dta_dta_ps3','png_ps3'))}
rep=dict(new); rep['ps3/config/amp_songs_config.dta_dta_ps3']=b'cfg'
with tempfile.TemporaryDirectory() as out:
    part,size=ark.patch(usr,out,rep); key2,d2=ark.decrypt_hdr(open(os.path.join(out,'main_ps3.hdr'),'rb').read()); d2=ark.parse(d2)
    assert key2==key and len(d2['buckets'])==len(d2['files'])==n+len(new) and d2['part_names'][-1]==part
    blob=open(os.path.join(out,part),'rb').read(); base=sum(d['part_sizes'])
    unresolved=[f['name'] for f in d2['files'] if f['name'] not in dup and d2['files'][ark.find(d2,f['name'])] is not f]
    print('patched archive, %d entries (+%d new): unresolved paths %s'%(len(d2['files']),len(new),unresolved)); assert not unresolved
    for name,data in rep.items():
        f=d2['files'][ark.find(d2,name)]; assert f['name']==name and f['size']==len(data) and blob[f['offset']-base:f['offset']-base+f['size']]==data and f['stamp']==ark.NEW_STAMP,name
    old={f['name']:f for f in d['files']}
    moved=[f['name'] for f in d2['files'] if f['name'] in old and f['name'] not in rep and (f['offset'],f['size'],f['stamp'])!=(old[f['name']]['offset'],old[f['name']]['size'],old[f['name']]['stamp'])]
    print('old entries whose data pointer changed (expect none): %s'%moved); assert not moved
    # 4. replacement only: the table is left exactly as shipped
    ark.patch(usr,out,{'ps3/config/amp_songs_config.dta_dta_ps3':b'cfg'}); k3,d3=ark.decrypt_hdr(open(os.path.join(out,'main_ps3.hdr'),'rb').read()); d3=ark.parse(d3)
    print('replacement only: buckets and links unchanged = %s'%(d3['buckets']==d['buckets'] and [f['link'] for f in d3['files']]==links)); assert d3['buckets']==d['buckets']
    # 5. bad new names are refused
    try: ark.patch(usr,out,{'ps3/songs/Bad/Bad.mid':b'x'}); raise SystemExit('uppercase path was accepted')
    except ValueError: print('uppercase new path refused')
print('ok')
