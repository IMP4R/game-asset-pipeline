import json, subprocess, time, os, shutil
from pathlib import Path
import psutil
from PIL import Image,ImageDraw
import numpy as np
p=Path(__file__).parent
source=Path('/Users/user0/godot-hybrid-casual/research/screens/sand_loop/play_shots/shot1.png')
regions=json.loads((p/'scene_regions.json').read_text())
out=p/'scene_instances';out.mkdir(exist_ok=True)
parent=psutil.Process();peak=0;records=[]
for i,r in enumerate(regions):
 prefix=out/f'{i:02d}_{r["name"]}'
 cmd=[str(p/'extract_original'),str(source),str(prefix),*[str(v) for v in r['box']]]
 proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 start=time.monotonic()
 while proc.poll() is None:
  total=parent.memory_info().rss
  for child in parent.children(recursive=True):
   try: total+=child.memory_info().rss
   except psutil.NoSuchProcess: pass
  peak=max(peak,total)
  if total>2*1024**3 or time.monotonic()-start>45:
   proc.kill();raise RuntimeError(f'Budget exceeded on {r["name"]}: RSS {total}')
  time.sleep(.15)
 stdout,stderr=proc.communicate()
 if proc.returncode: print('FAILED',r['name'],stderr,flush=True);continue
 files=list(out.glob(prefix.name+'_*.png'))
 for f in files:
  im=Image.open(f).convert('RGBA');alpha=im.getchannel('A');bbox=alpha.getbbox()
  if bbox:
   crop=im.crop(bbox);crop.save(out/(prefix.name+'_cutout.png'))
   records.append({**r,'id':i,'mask_path':str(f),'bbox':bbox})
 print(f'{i+1}/{len(regions)} {r["name"]}',flush=True)
base=Image.open(source).convert('RGB');w,h=base.size
labels=np.full((h,w),-1,dtype=np.int16)
# Small objects take precedence over large surfaces, removing overlapping occluders.
for r in sorted(records,key=lambda r:r['box'][2]*r['box'][3],reverse=True):
 a=np.array(Image.open(r['mask_path']).getchannel('A'))
 labels[a>127]=r['id']
colors=[]
import colorsys
for i in range(len(regions)):
 colors.append(tuple(round(c*255) for c in colorsys.hsv_to_rgb((i*.61803398875)%1,.8,1)))
a=np.array(base,dtype=np.float32); overlay=a.copy()
for r in records:
 m=labels==r['id'];overlay[m]=a[m]*.35+np.array(colors[r['id']])*.65
 # Save resolved per-object mask and original-pixel cutout.
 rgba=base.convert('RGBA');rgba.putalpha(Image.fromarray((m*255).astype('uint8')))
 bbox=rgba.getchannel('A').getbbox()
 if bbox:rgba.crop(bbox).save(out/f'{r["id"]:02d}_{r["name"]}_resolved.png')
colored=Image.fromarray(overlay.astype('uint8'));d=ImageDraw.Draw(colored)
for r in records:
 x,y,_,_=r['bbox'];d.text((x,y),str(r['id']),fill='white',stroke_width=2,stroke_fill='black')
sheet=Image.new('RGB',(2*w+24,h+55),'white');sheet.paste(base,(0,55));sheet.paste(colored,(w+24,55));d=ImageDraw.Draw(sheet)
d.text((12,16),'A ORIGINAL',fill='black');d.text((w+36,16),f'B VLM REGIONS + APPLE VISION: {len(records)} masks',fill='black');sheet.save(p/'scene_guided_ab.png')
(p/'scene_guided_report.json').write_text(json.dumps({'source':str(source),'method':'human-model visual regions + Apple Vision instance masks','peak_combined_process_rss_bytes':peak,'objects':records},indent=2))
print('DONE peak combined RSS MiB',round(peak/1024**2),flush=True)
