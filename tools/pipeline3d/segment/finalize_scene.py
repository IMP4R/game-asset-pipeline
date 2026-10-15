from pathlib import Path
import json,colorsys
import cv2
import numpy as np
from PIL import Image,ImageDraw
cv2.setNumThreads(1)
p=Path(__file__).parent; report=json.loads((p/'scene_guided_report.json').read_text()); regions=json.loads((p/'scene_regions.json').read_text());src=Image.open(report['source']).convert('RGB');a=np.array(src);h,w=a.shape[:2]; masks={}
for r in report['objects']:
 m=np.array(Image.open(r['mask_path']).getchannel('A'))>127
 masks[r['id']]=masks.get(r['id'],np.zeros((h,w),bool))|m
# Complete planar surfaces by explicit visible boundaries, not invented neural masks.
board=np.zeros((h,w),np.uint8);cv2.rectangle(board,(142,92),(900,837),255,-1);# Separate board from conveyor foreground.
board[790:]=0
masks[4]=board>0
banner=np.zeros((h,w),np.uint8);cv2.fillPoly(banner,[np.array([(310,1590),(1051,1506),(1051,1869),(310,1869)])],255);masks[31]=banner>0
# Missing small lock: image-based GrabCut within VLM-provided window.
x,y,bw,bh=275,1308,96,116
patch=a[y:y+bh,x:x+bw].copy();m=np.full((bh,bw),cv2.GC_PR_BGD,np.uint8)
m[8:bh-7,8:bw-7]=cv2.GC_PR_FGD;m[20:bh-15,25:bw-20]=cv2.GC_FGD
m[:2]=0;m[-2:]=0;m[:,:2]=0;m[:,-2:]=0
cv2.grabCut(patch,m,None,np.zeros((1,65)),np.zeros((1,65)),4,cv2.GC_INIT_WITH_MASK)
lock=np.zeros((h,w),bool);lock[y:y+bh,x:x+bw]=(m==1)|(m==3);masks[15]=lock
head=np.array(Image.open(p/'scene_instances/22_gold_key_head_1.png').getchannel('A'))>127
# Keep neural head only in its requested region (exclude lock occluder).
masks[22]|=head
# Gold shaft's visible pixels, excluding blue locks that occlude it.
hsv=cv2.cvtColor(a,cv2.COLOR_RGB2HSV)
shaft=np.zeros((h,w),bool);shaft[1450:1481,370:789]=(hsv[1450:1481,370:789,0]<40)&(hsv[1450:1481,370:789,1]>120)
masks[22]|=shaft
labels=np.full((h,w),-1,np.int16)
for r in sorted(regions,key=lambda r:r['box'][2]*r['box'][3],reverse=True):
 if r.get('id',regions.index(r)) in masks:labels[masks[regions.index(r)]]=regions.index(r)
over=a.astype(float);out=p/'scene_instances'
legend=[]
for i,r in enumerate(regions):
 mask=labels==i
 if not mask.any():continue
 color=np.array(colorsys.hsv_to_rgb((i*.61803398875)%1,.8,1))*255;over[mask]=a[mask]*.35+color*.65
 rgba=src.convert('RGBA');rgba.putalpha(Image.fromarray((mask*255).astype('uint8')));box=rgba.getchannel('A').getbbox();rgba.crop(box).save(out/f'{i:02d}_{r["name"]}_final.png')
 legend.append({'id':i,'name':r['name'],'bbox':box,'method':'VLM boundary' if i in (4,31) else 'GrabCut' if i==15 else 'Apple Vision guided mask'})
colored=Image.fromarray(over.astype('uint8'));d=ImageDraw.Draw(colored)
for r in legend:d.text(r['bbox'][:2],str(r['id']),fill='white',stroke_width=2,stroke_fill='black')
sheet=Image.new('RGB',(2*w+24,h+55),'white');sheet.paste(src,(0,55));sheet.paste(colored,(w+24,55));d=ImageDraw.Draw(sheet);d.text((12,16),'A ORIGINAL',fill='black');d.text((w+36,16),f'B GUIDED INSTANCE SEGMENTATION: {len(legend)} objects',fill='black');sheet.save(p/'scene_final_ab.png')
(p/'scene_final_manifest.json').write_text(json.dumps(legend,indent=2));print('Saved',len(legend),'objects',p/'scene_final_ab.png')
