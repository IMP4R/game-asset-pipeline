import os, resource, time, json
os.environ['OMP_NUM_THREADS']='2'
os.environ['OPENBLAS_NUM_THREADS']='2'
# macOS RLIMIT_AS is not usable here; parent watchdog caps RSS.
import torch
from ultralytics import YOLOE
from PIL import Image, ImageDraw
import numpy as np
from pathlib import Path
torch.set_num_threads(2)
p=Path(__file__).parent
src=Path('/Users/user0/godot-hybrid-casual/research/screens/sand_loop/play_shots/shot1.png')
t=time.monotonic()
model=YOLOE('yoloe-26s-seg.pt')
classes=['bucket','padlock','key','conveyor belt','picture frame','coin','heart','button']
model.set_classes(classes)
result=model.predict(str(src),device='cpu',imgsz=640,conf=0.15,retina_masks=True,verbose=True)[0]
original=Image.open(src).convert('RGB'); arr=np.array(original).astype(float); overlay=arr.copy(); records=[]
colors=[(255,50,90),(30,210,100),(30,130,255),(250,180,20),(180,60,230),(20,210,210)]
if result.masks is not None:
 for i,(mask,box) in enumerate(zip(result.masks.data.cpu().numpy(),result.boxes)):
  alpha=np.array(Image.fromarray((mask*255).astype('uint8')).resize(original.size,Image.Resampling.NEAREST))/255.0
  strength=alpha[:,:,None]*0.6
  overlay=overlay*(1-strength)+np.array(colors[i%len(colors)])*strength
  rgba=original.convert('RGBA');rgba.putalpha(Image.fromarray((alpha*255).astype('uint8')));bbox=rgba.getchannel('A').getbbox()
  if bbox: rgba.crop(bbox).save(p/f'yolo_object_{i:02d}.png')
  records.append({'id':i,'class':classes[int(box.cls.item())],'confidence':round(box.conf.item(),3),'bbox':box.xyxy.cpu().tolist()[0]})
colored=Image.fromarray(overlay.clip(0,255).astype('uint8'));draw=ImageDraw.Draw(colored)
for r in records:
 x,y,_,_=r['bbox'];draw.text((x,y),f"{r['id']} {r['class']}",fill='white',stroke_width=2,stroke_fill='black')
w,h=original.size; sheet=Image.new('RGB',(w*2+24,h+50),'white');sheet.paste(original,(0,50));sheet.paste(colored,(w+24,50));d=ImageDraw.Draw(sheet);d.text((10,15),'A ORIGINAL',fill='black');d.text((w+34,15),f'B YOLOE-26-S SEG: {len(records)} detections',fill='black');sheet.save(p/'yolo_scene_ab.png')
report={'detections':records,'elapsed_seconds':round(time.monotonic()-t,2),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'device':'cpu','threads':2,'imgsz':640}
(p/'yolo_scene_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
