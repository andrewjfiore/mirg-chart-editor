import sys,mido,collections,glob,os
where=collections.defaultdict(set); odd=[]
std=set(range(96,119,2))
for f in sorted(glob.glob(sys.argv[1]+'/**/*.mid',recursive=True)):
    m=mido.MidiFile(f,clip=True); s=os.path.basename(f)[:-4]
    for t in m.tracks:
        tick=0
        for msg in t:
            tick+=msg.time
            if msg.is_meta and hasattr(msg,'text'): where[msg.text].add(s)
            elif msg.type=='note_on' and msg.velocity>0 and 'CATCH' in t.name and msg.note not in std: odd.append((s,t.name,msg.note,tick/m.ticks_per_beat))
for k,v in sorted(where.items(),key=lambda x:len(x[1])):
    if len(v)<=2: print(repr(k)[:120],sorted(v))
print('odd pitches in CATCH tracks:',len(odd))
[print(o) for o in odd if o[0]!='credits']
