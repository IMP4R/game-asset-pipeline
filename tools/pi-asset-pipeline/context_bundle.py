"""Separate agent analysis context from the two-reference image-edit contract."""
from pathlib import Path

RESTORATION_RULE = '''INPUT CONTRACT: Each object has TWO references: a contextual crop and the same object's masked crop. The contextual crop explains neighbors, camera and occluding walls; the masked crop identifies the visible object, NOT necessarily its full geometry. Restore the complete standalone object preserving camera, colors and proportions. A flat cut at a tray lip is OCCLUSION, not the real base: complete hidden rounded geometry consistently. Do not include foreground walls inside the sprite. Leave transparent margins. Occlusion is applied later as a separate layer.'''

def build_context_bundle(root, task):
 root=Path(root).resolve()
 # Agent selects references using its image-reading tools in the working directory.
 # No automatic context discovery or selection at the API boundary.
 pairs=task.get('reference_pairs')
 if pairs is None:
  inputs=task.get('inputs',[])
  if len(inputs)!=2:raise ValueError('Image task requires reference_pairs or exactly two inputs: contextual crop, masked crop. Full context belongs to Pi analysis, not the image API.')
  pairs=[{'context_crop':inputs[0],'masked_crop':inputs[1]}]
 if not pairs:raise ValueError('At least one object reference pair is required')
 paths=[]
 for pair in pairs:
  for key in ['context_crop','masked_crop']:
   if not pair.get(key):raise ValueError('Missing '+key+' in object reference pair')
   f=Path(pair[key]);f=(f if f.is_absolute() else root/f).resolve()
   if not f.is_file():raise ValueError('Missing image reference: '+str(f))
   paths.append(str(f))
 # Group sheets may carry several objects: two references PER object, not unrelated inputs.
 return list(dict.fromkeys(paths))

def analysis_context(root):
 """Full context inventory for Pi/VLM analysis ONLY; never auto-attached to image edits."""
 root=Path(root).resolve()
 return [str(p) for folder in ['input','output/context','output/templates'] for p in sorted((root/folder).rglob('*')) if p.is_file() and p.suffix.lower() in ['.png','.jpg','.jpeg','.webp']]
