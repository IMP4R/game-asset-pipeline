from pathlib import Path
from PIL import Image,ImageDraw
p=Path(__file__).parent/'output'
out=Image.new('RGB',(856,755),'white');d=ImageDraw.Draw(out)
for i,name in enumerate(['original_grid_overlay.png','registered_grid_overlay.png']):
 im=Image.open(p/name).convert('RGB');out.paste(im,(438*i,35))
 d.text((438*i+10,10),'A ORIGINAL FLOOR GRID' if i==0 else 'B GENERATED REGISTERED FLOOR GRID',fill='black')
out.save(p/'grid_registration_ab.png')
