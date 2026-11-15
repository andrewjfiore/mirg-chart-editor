import sys,mido,collections,glob,os
G=[(96,98,100),(102,104,106),(108,110,112),(114,116,118)]
for f in sorted(glob.glob(sys.argv[1]+'/**/*.mid',recursive=True)):
    m=mido.MidiFile(f,clip=True); s=os.path.basename(f)[:-4]
    if s.startswith('tut'): continue
    for t in m.tracks:
        if 'CATCH' not in t.name: continue
        tick=0; ev=collections.defaultdict(list)
        for msg in t:
            tick+=msg.time
            if msg.type=='note_on' and msg.velocity>0: ev[tick].append(msg.note)
        for k,ns in ev.items():
            for gi,g in enumerate(G):
                hit=[n for n in ns if n in g]
                if len(hit)>1: print(s,t.name,'bar %.2f'%(k/m.ticks_per_beat/4+1),'diff',gi,'notes',hit)
