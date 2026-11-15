import sys,mido,collections,glob,os
for f in sorted(glob.glob(sys.argv[1]+'/**/*.mid',recursive=True)):
    try: m=mido.MidiFile(f,clip=True)
    except Exception as e: print(f,'ERR',e); continue
    print('==',os.path.basename(f),'tracks',len(m.tracks))
    for t in m.tracks:
        name=t.name; texts=[];notes=collections.Counter()
        for msg in t:
            if msg.is_meta and msg.type in('text','marker','lyrics','cue_marker','copyright','instrument_name') : texts.append(msg.text)
            elif msg.type=='note_on' and msg.velocity>0: notes[msg.note]+=1
        tx=collections.Counter(texts)
        print('  [%s] notes=%d pitches=%s'%(name,sum(notes.values()),sorted(notes)[:3]+['..']+sorted(notes)[-3:] if notes else []))
        if tx: print('    text:',', '.join('%s x%d'%(k,v) if v>1 else k for k,v in list(tx.items())[:40]))
