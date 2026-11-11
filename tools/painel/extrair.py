import re, json, base64, subprocess, io, sys
from PIL import Image
R='/home/user/darkchannel'
def blocks(md, header_re):
    out=[]
    parts=re.split(r'^## ', md, flags=re.M)
    for p in parts[1:]:
        h=p.split('\n',1)[0]
        m=re.match(header_re,h)
        if not m: continue
        cb=re.findall(r'\*\*(Título|Descrição)\*\*\s*```\n(.*?)```', p, re.S)
        d={k:v.strip() for k,v in cb}
        out.append((m, d))
    return out
def thumb(path, w):
    im=Image.open(path).convert('RGB'); im.thumbnail((w,w*2))
    b=io.BytesIO(); im.save(b,'JPEG',quality=68,optimize=True)
    return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
def frame(mp4, t=2.0):
    raw=subprocess.run(['ffmpeg','-loglevel','error','-ss',str(t),'-i',mp4,'-frames:v','1','-vf','scale=144:-2','-f','image2','-c:v','mjpeg','-q:v','6','-'],capture_output=True).stdout
    return 'data:image/jpeg;base64,'+base64.b64encode(raw).decode()
items=[]
DIAS={'Seg':'seg','Ter':'ter','Qua':'qua','Qui':'qui','Sex':'sex','Sáb':'sáb','Dom':'dom'}
def dt(s):  # "19/10" -> "2026-10-19"
    d,m=s.split('/'); return f"2026-{m}-{d}"
up=open(f'{R}/UPLOAD.md').read()
for m,d in blocks(up, r'\d+\. (\w+) (\d\d/\d\d)[^—]*— (\S+)'):
    slug=m.group(3)
    items.append(dict(id=slug, kind='longo', lote=1, ep=slug[:2], slug=slug, date=dt(m.group(2)), time='17h',
        title=d.get('Título',''), desc=d.get('Descrição',''), file=f'videos/{slug}.mp4', img=thumb(f'{R}/thumbnails/{slug}.jpg',320)))
sh=open(f'{R}/SHORTS.md').read()
table=dict(re.findall(r'`shorts/(\S+?)\.mp4` \|[^|]*\|[^|]*\| \*\*\w+ (\d\d/\d\d)', sh))
for m,d in blocks(sh, r'\d+\. `(\S+?)\.mp4`'):
    sid=m.group(1)
    items.append(dict(id=sid, kind='short', lote=1, ep=sid[:2], slug=sid.rsplit('-short',1)[0], date=dt(table[sid]), time='21h' if sid.startswith('09') else '12h',
        title=d.get('Título',''), desc=d.get('Descrição',''), file=f'shorts/{sid}.mp4', img=frame(f'{R}/shorts/{sid}.mp4')))
l2=open(f'{R}/LOTE2.md').read()
for m,d in blocks(l2, r'\d+\. \w+ (\d\d/\d\d) — (\S+)'):
    slug=m.group(2)
    items.append(dict(id=slug, kind='longo', lote=2, ep=slug[:2], slug=slug, date=dt(m.group(1)), time='17h',
        title=d.get('Título',''), desc=d.get('Descrição',''), file=f'videos/{slug}.mp4', img=thumb(f'{R}/thumbnails/{slug}.jpg',320)))
for m,d in blocks(l2, r'\w+ (\d\d/\d\d), 12h — `shorts/(\S+?)\.mp4`'):
    sid=m.group(2)
    items.append(dict(id=sid, kind='short', lote=2, ep=sid[:2], slug=sid.rsplit('-short',1)[0], date=dt(m.group(1)), time='12h',
        title=d.get('Título',''), desc=d.get('Descrição',''), file=f'shorts/{sid}.mp4', img=frame(f'{R}/shorts/{sid}.mp4')))
print(len(items), sum(i['kind']=='longo' for i in items), file=sys.stderr)
for i in items:
    if not i['title'] or not i['desc']: print('FALTA', i['id'], file=sys.stderr)
json.dump(items, open(sys.argv[1],'w'), ensure_ascii=False)
