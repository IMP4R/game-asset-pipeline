from PIL import Image,ImageDraw
from pathlib import Path
p=Path(__file__).parent/'edge_probe';names=['open_bucket','inverted_bucket','lock','long_key'];out=Image.new('RGB',(1200,1200),'#eeeeee');d=ImageDraw.Draw(out)
for i,n in enumerate(names):
 for j,suffix in enumerate(['input','repaired']):
  im=Image.open(p/f'{n}_{suffix}.png').convert('RGBA')
  if suffix=='repaired':
   import numpy as np
   a=np.array(im);nonwhite=(a[:,:,:3].min(2)<235);ys,xs=np.where(nonwhite)
   if len(xs):im=im.crop((max(0,int(xs.min())-8),max(0,int(ys.min())-8),min(im.width,int(xs.max())+9),min(im.height,int(ys.max())+9)))
  scale=min(550/im.width,250/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST if suffix=='input' else Image.Resampling.LANCZOS)
  x=j*600+20;y=i*300+40;out.paste(im,(x,y),im);d.text((x,y-25),f'{n} | '+('A EXTRACTED' if j==0 else 'B GPT IMAGE REPAIRED'),fill='black')
out.save(p/'repair_comparison.png');print(p/'repair_comparison.png')
