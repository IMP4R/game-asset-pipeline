"""Usage: python3 image_edit.py task.json. Credentials only from inherited env."""
from pathlib import Path
import os,sys,json,uuid,time,urllib.request,base64
root=Path(os.environ.get('PIPELINE_RUN_DIR',Path(__file__).parent)).resolve();task=json.loads(Path(sys.argv[1]).read_text());url=os.environ.get('IMAGE_BASE_URL','http://205.196.80.135:8317/v1')+'/images/edits';rid=uuid.uuid4().hex
from context_bundle import build_context_bundle, RESTORATION_RULE
if os.environ.get('REQUIRE_CRITIC_GATES')=='1':
 from review_gate import accepted_review
 accepted_review(root,'geometry')
task['inputs']=build_context_bundle(root,task)
task['prompt']=RESTORATION_RULE+'\n\n'+task['prompt']
output=Path(task['output']);output.parent.mkdir(parents=True,exist_ok=True)
ledger=root/'image_requests.jsonl'
# Budget reservation below is serialized across parallel image subprocesses.
if task.get('model','gpt-image-2')!='gpt-image-2':raise SystemExit('This run authorizes only gpt-image-2.')
def log(state,**kwargs):
 with ledger.open('a') as f:f.write(json.dumps({'id':rid,'state':state,'model':task.get('model','gpt-image-2'),'endpoint':url,'time':time.time(),**kwargs})+'\n')
boundary=uuid.uuid4().hex;body=b''
fields={'model':task.get('model','gpt-image-2'),'quality':'low','size':task.get('size','1536x1024'),'prompt':task['prompt']}
if 'background' in task:fields['background']=task['background']
for k,v in fields.items():body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
for name in task['inputs']:
 f=Path(name);body+=f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{f.name}"\r\nContent-Type: image/png\r\n\r\n'.encode()+f.read_bytes()+b'\r\n'
body+=f'--{boundary}--\r\n'.encode()
import fcntl
with (root/'image_requests.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 submitted=sum(json.loads(line).get('state')=='submitted' for line in ledger.read_text().splitlines() if line.strip()) if ledger.exists() else 0
 if submitted>=int(os.environ.get('IMAGE_REQUEST_LIMIT','8')):raise SystemExit('Configured image request budget exhausted.')
 log('submitted',output=str(output),inputs=task['inputs'])
 fcntl.flock(lock,fcntl.LOCK_UN)
try:
 req=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+os.environ['CLIPROXY_API_KEY'],'Content-Type':'multipart/form-data; boundary='+boundary})
 with urllib.request.urlopen(req,timeout=300) as r:data=json.load(r)
 item=data['data'][0]
 if 'b64_json' in item:output.write_bytes(base64.b64decode(item['b64_json']))
 else:
  with urllib.request.urlopen(item['url'],timeout=120) as r:output.write_bytes(r.read())
 log('success');print('Saved',output)
except Exception as e:
 log('failed',error=type(e).__name__,status=getattr(e,'code',None));print('Image edit failed:',type(e).__name__,getattr(e,'code',None),file=sys.stderr);sys.exit(1)
