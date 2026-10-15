import base64,json,subprocess,urllib.request,uuid,time
from pathlib import Path
p=Path(__file__).parent/'edge_probe'
key=subprocess.run(['python3','/Users/user0/golden-land-new/scripts/read-credential-key.py','CHEAPVIBECODE_API_KEY'],capture_output=True,text=True,check=True).stdout.strip()
tasks={
'open_bucket':'Repair this extracted orange bucket. Preserve its exact viewpoint, silhouette proportions, orange material, rim and interior cavity. Smooth jagged extraction edges and remove stray background. Do not invent new parts.',
'inverted_bucket':'Repair this extracted upside-down orange bucket. Preserve its exact upside-down pose and proportions. Preserve the black carrying handle and its two side attachment points. Smooth jagged extraction edges, restore tiny clipped edge pixels and remove stray background. Do not turn it into a helmet or change its construction.',
'lock':'Repair this extracted stylized blue padlock marked 2. Preserve viewpoint, shape and the digit 2. Remove the pale background fragments around it, especially right and bottom. Smooth jagged edges and restore small clipped boundaries without redesigning it.',
'long_key':'Repair this extracted golden key. These separated pieces are visible fragments of ONE horizontal key whose straight shaft was occluded by two objects. Reconnect the fragments into one continuous straight golden shaft of the same thickness and total length. Preserve the ornate double-loop head and exact horizontal view. Remove tiny stray pixels and smooth jagged edges.'}
tasks={'inverted_bucket_context':'Repair the extracted upside-down orange bucket shown in image 1. Image 2 is the ORIGINAL gameplay screenshot and explains the occlusion. Locate the orange upside-down bucket at the left of the second bucket row. Its lower edge is overlapped by a beige bucket in the next row. The concave notch in image 1 is missing material caused by that occlusion, NOT a designed notch, feet, scallop or indentation. Restore the hidden lower orange rim as a continuous smooth convex rounded ellipse, consistent with the rest of the bucket. Preserve the upside-down viewpoint, orange body, and black carrying handle with two attachment points. Remove background fragments; do not add a black silhouette outline. Use image 2 only as context, do not include neighbouring objects or gameplay UI in the result.'}
for name,instruction in tasks.items():
 prompt=instruction+' Output only the repaired object on a plain white background, with comfortable margins. No labels, no other objects. This is restoration, not a new design.'
 (p/(name+'_repair_prompt.txt')).write_text(prompt)
 for attempt in range(2):
  boundary=uuid.uuid4().hex;body=b''
  for k,v in {'model':'gpt-image-2','prompt':prompt,'size':'1024x1024','quality':'low'}.items():body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
  for file in [p/'inverted_bucket_input.png',Path('/Users/user0/godot-hybrid-casual/research/screens/sand_loop/play_shots/shot1.png')]:
   body+=f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{file.name}"\r\nContent-Type: image/png\r\n\r\n'.encode()+file.read_bytes()+b'\r\n'
  body+=f'--{boundary}--\r\n'.encode()
  req=urllib.request.Request('https://ru.cheapvibecode.ru/v1/images/edits',data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'multipart/form-data; boundary='+boundary})
  try:
   t=time.monotonic()
   with urllib.request.urlopen(req,timeout=280) as response:r=json.load(response)
   (p/(name+'_repaired.png')).write_bytes(base64.b64decode(r['data'][0]['b64_json']));print(name,'saved',round(time.monotonic()-t,1),'sec',flush=True);break
  except Exception as e:
   print(name,'attempt failed',type(e).__name__,flush=True)
   if attempt==1:raise
