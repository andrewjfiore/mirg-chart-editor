import sys,glob,os,tempfile,json; sys.path.insert(0,os.path.dirname(__file__)); import chart,midps3
songs=sys.argv[1]; ok=0; n=0; bad=[]; tmp=tempfile.mkdtemp()
for f in sorted(glob.glob(songs+'/*/*.mid')):
    n+=1; c=chart.load(f); c=json.loads(json.dumps(c))  # must survive JSON
    mine=chart.compile_chart(c,os.path.join(tmp,'x.mid')); ref=midps3.compile_mid(f)
    if mine==ref: ok+=1
    else: bad.append(os.path.basename(f))
print('chart JSON round trip (compiled output identical): %d/%d'%(ok,n),bad[:8])
