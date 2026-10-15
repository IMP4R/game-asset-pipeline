import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import torch,time,json,resource
import numpy as np
from PIL import Image,ImageDraw
from pathlib import Path
from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
torch.set_num_threads(2)
p=Path(__file__).parent;out=p/'edge_probe';out.mkdir(exist_ok=True)
image=Image.open('/Users/user0/godot-hybrid-casual/research/screens/sand_loop/play_shots/shot1.png').convert('RGB')
model=build_sam2('configs/edgetam.yaml',str(p/'EdgeTAM/checkpoints/edgetam.pt'),device='cpu',apply_postprocessing=False)
predictor=SAM2ImagePredictor(model)
# Original coordinates; explicit object components and excluded neighbours.
tasks=[
 ('open_bucket',[475,1203,584,1326],[[528,1263],[525,1304],[480,1250],[580,1250],[526,1198],[589,1280]],[1,1,1,1,0,0]),
 ('inverted_bucket',[170,1314,275,1422],[[221,1351],[222,1396],[182,1378],[262,1380],[198,1391],[212,1395],[233,1395],[247,1390],[220,1306],[276,1380]],[1,1,1,1,1,1,1,1,0,0]),
 ('lock',[270,1304,373,1428],[[312,1360],[334,1325],[347,1406],[280,1380],[260,1380],[375,1360]],[1,1,1,1,0,0]),
 ('long_key',[271,1418,789,1517],[[310,1447],[310,1480],[354,1465],[500,1467],[720,1467],[421,1460],[631,1460],[326,1514]],[1,1,1,1,1,0,0,0])]
rows=[];records=[]
with torch.inference_mode():
 t=time.monotonic();predictor.set_image(np.array(image));print('encoded',time.monotonic()-t,flush=True)
 for name,box,points,labels in tasks:
  masks,scores,_=predictor.predict(point_coords=np.array(points),point_labels=np.array(labels),box=np.array(box),multimask_output=False)
  m=masks[0].astype(bool)
  # Fill enclosed mask holes only, no RGB generation.
  from scipy.ndimage import binary_fill_holes
  m=binary_fill_holes(m)
  rgba=image.convert('RGBA');rgba.putalpha(Image.fromarray((m*255).astype('uint8')));rgba.save(out/(name+'.png'))
  x0,y0,x1,y1=box; viewbox=(max(0,x0-10),max(0,y0-10),min(image.width,x1+10),min(image.height,y1+10))
  original=image.crop(viewbox); local=m[viewbox[1]:viewbox[3],viewbox[0]:viewbox[2]];a=np.array(original);colored=a.copy();colored[local]=(a[local]*.35+np.array([255,35,135])*.65).astype('uint8')
  cut=rgba.crop(viewbox);check=Image.new('RGB',cut.size,'#eeeeee');check.paste(cut,(0,0),cut)
  # Display panels scaled only for readability; stored masks stay original size.
  panels=[original,Image.fromarray(colored),check];row=Image.new('RGB',(1800,320),'white');d=ImageDraw.Draw(row);d.text((10,8),name,fill='black')
  for j,panel in enumerate(panels):
   scale=min(580/panel.width,275/panel.height)
   panel=panel.resize((round(panel.width*scale),round(panel.height*scale)),Image.Resampling.NEAREST);row.paste(panel,(j*600+10,40));d.text((j*600+10,25),['ORIGINAL','MASK','EXTRACTED'][j],fill='black')
  rows.append(row);records.append({'name':name,'score':float(scores[0]),'pixels':int(m.sum())});print(name,records[-1],flush=True)
sheet=Image.new('RGB',(1800,320*len(rows)),'white')
for i,row in enumerate(rows):sheet.paste(row,(0,320*i))
sheet.save(out/'comparison.png');(out/'report.json').write_text(json.dumps({'objects':records,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},indent=2))
