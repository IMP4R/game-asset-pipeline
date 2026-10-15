"""Independent read-only Pi review: --stage geometry|assets|scene --manifest file.json."""
from pathlib import Path
import argparse,os,json,uuid,subprocess,hashlib,fcntl

def validate_manifest(root,data):
 root=Path(root).resolve()
 items=data.get('items',[]);ids=[i['id'] for i in items]
 if not ids or len(ids)!=len(set(ids)):raise ValueError('Manifest needs unique exhaustive item ids')
 files=set()
 for i in items:
  if not i.get('files'):raise ValueError('Every item needs original and candidate files')
  for name in i['files']:
   p=(root/name).resolve()
   if not p.is_relative_to(root) or not p.is_file():raise ValueError('Invalid review file '+name)
   files.add(str(p.relative_to(root)))
 return files

def parse_review(trace):
 reads=set();pending={};final=None
 for line in Path(trace).read_text().splitlines():
  try:e=json.loads(line)
  except ValueError:continue
  if e.get('type')=='tool_execution_start' and e.get('toolName')=='read':pending[e.get('toolCallId')]=e.get('args',{}).get('path','')
  if e.get('type')=='tool_execution_end' and e.get('toolName')=='read' and e.get('isError') is False:
   if e.get('toolCallId') in pending:reads.add(pending[e['toolCallId']])
  if e.get('type')=='message_end' and e.get('message',{}).get('role')=='assistant':
   parts=e['message'].get('content',[]);text=''.join(p.get('text','') for p in parts if p.get('type')=='text')
   if text:final=text
 if not final:raise ValueError('No final critic response')
 text=final.strip()
 if text.startswith('```'):text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
 return json.loads(text),reads

def validate_review(root,stage,manifest,report,reads):
 root=Path(root).resolve()
 wanted=validate_manifest(root,manifest);readfiles=set()
 for name in reads:
  p=(root/name).resolve()
  if p.is_relative_to(root):readfiles.add(str(p.relative_to(root)))
 if not wanted<=readfiles:raise ValueError('Critic did not read required files: '+str(sorted(wanted-readfiles)))
 if report.get('stage')!=stage or report.get('verdict') not in ['pass','revise','uncertain']:raise ValueError('Invalid critic verdict')
 entries=report.get('items',[])
 if sorted(i['id'] for i in entries)!=sorted(i['id'] for i in manifest['items']):raise ValueError('Incomplete item coverage')
 for i in entries:
  if i.get('verdict') not in ['pass','revise','uncertain'] or not i.get('evidence'):raise ValueError('Missing item verdict/evidence')
 if report['verdict']=='pass' and any(i['verdict']!='pass' for i in entries):raise ValueError('Overall pass contradicts item verdict')
 if not wanted<=set(report.get('reviewed_files',[])):raise ValueError('Incomplete reviewed_files')
 if not isinstance(report.get('issues'),list):raise ValueError('Missing issues')
 if report['verdict']=='pass' and any(i.get('severity') in ['critical','major'] for i in report['issues']):raise ValueError('Pass contradicts major issue')
 return report

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=['geometry','assets','scene'],required=True);ap.add_argument('--manifest',type=Path,required=True);args=ap.parse_args()
 root=Path(os.environ.get('PIPELINE_RUN_DIR',Path.cwd())).resolve();manifest=json.loads(args.manifest.read_text());files=validate_manifest(root,manifest)
 out=root/'output/critics';out.mkdir(parents=True,exist_ok=True);rid=args.stage+'-'+uuid.uuid4().hex;trace=out/(rid+'.jsonl');target=out/(rid+'.json')
 with (out/'reservations.jsonl').open('a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);lock.seek(0);records=[json.loads(l) for l in lock if l.strip()]
  if sum(x['stage']==args.stage for x in records)>=int(os.environ.get('CRITIC_MAX_REVIEWS','3')):raise SystemExit('Critic review budget exhausted for stage')
  lock.write(json.dumps({'stage':args.stage,'id':rid})+'\n');lock.flush()
 hashes={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files}
 runtime=Path(os.environ.get('PI_RUNTIME_DIR',Path(__file__).parent));env=os.environ.copy();env['IMAGE_REQUEST_LIMIT']='0';env['PI_TELEMETRY']='0';env['NODE_OPTIONS']='--max-old-space-size=768'
 prompt=(Path(__file__).with_name('CRITIC.md')).read_text()+'\nStage: '+args.stage+'\nManifest: '+json.dumps(manifest)+'\nRead all listed files with read tool, then return the required JSON verdict.'
 cmd=[str(runtime/'node_modules/.bin/pi'),'--provider','cliproxy','--model','gpt-6.1-sol','--thinking','high','--tools','read,grep,find,ls','--no-context-files','--no-skills','--no-extensions','--no-prompt-templates','--no-session','--mode','json','--print',prompt]
 try:
  with trace.open('w') as log:result=subprocess.run(cmd,cwd=root,env=env,stdout=log,stderr=subprocess.PIPE,text=True,timeout=int(os.environ.get('CRITIC_TIMEOUT','600')))
  if result.returncode:raise ValueError('Critic process failed; exit '+str(result.returncode))
  report,reads=parse_review(trace);report=validate_review(root,args.stage,manifest,report,reads)
  if hashes!={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files}:raise ValueError('Artifacts changed during review')
  report.update(file_hashes=hashes,manifest=manifest,trace=str(trace.relative_to(root)))
 except Exception as e:report={'stage':args.stage,'verdict':'uncertain','technical_error':str(e),'file_hashes':hashes,'manifest':manifest,'trace':str(trace.relative_to(root))}
 target.write_text(json.dumps(report,indent=2));print('Critic report:',target);print('Verdict:',report['verdict']);return 0 if report['verdict']=='pass' else 2
if __name__=='__main__':raise SystemExit(main())
