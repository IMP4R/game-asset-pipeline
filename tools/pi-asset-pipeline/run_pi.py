"""New isolated run: python3 run_pi.py --description game.md --screenshots frame.png ...
--prepare-only creates the workspace without any model/API request.
"""
from pathlib import Path
import argparse,json,os,shutil,subprocess,uuid,datetime
p=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--description',type=Path,required=True);ap.add_argument('--screenshots',type=Path,nargs='+',required=True);ap.add_argument('--request-limit',type=int,default=8);ap.add_argument('--prepare-only',action='store_true');args=ap.parse_args()
if args.request_limit<1:ap.error('request-limit must be positive')
for f in [args.description,*args.screenshots]:
 if not f.is_file():ap.error('Missing input '+str(f))
run=p/'runs'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]);(run/'input/screenshots').mkdir(parents=True)
shutil.copyfile(args.description,run/'input/description.md')
for i,f in enumerate(args.screenshots):shutil.copyfile(f,run/'input/screenshots'/f'{i:03d}_{f.name}')
# Only game-agnostic instructions/helpers, NEVER previous geometry/assets/scripts.
for name in ['TASK.md','image_edit.py','context_bundle.py','critic.py','CRITIC.md','review_gate.py']:shutil.copyfile(p/name,run/name)
shutil.copytree(p/'.pi/skills',run/'.pi/skills')
manifest={'description':'input/description.md','screenshots':[str(f.relative_to(run)) for f in sorted((run/'input/screenshots').iterdir())],'agent_model':'gpt-6.1-sol','image_model':'gpt-image-2','image_request_limit':args.request_limit,'parent_provided_geometry':False}
(run/'run_input.json').write_text(json.dumps(manifest,indent=2));print('Workspace:',run,flush=True)
if args.prepare_only:raise SystemExit(0)
env=os.environ.copy();env['CLIPROXY_API_KEY']=subprocess.run(['python3','/Users/user0/golden-land-new/scripts/read-credential-key.py','CLIPROXY_API_KEY'],capture_output=True,text=True,check=True).stdout.strip()
env.update(PI_CODING_AGENT_DIR=str(p/'pi-config'),PI_TELEMETRY='0',NODE_OPTIONS='--max-old-space-size=768',PIPELINE_RUN_DIR=str(run),PI_RUNTIME_DIR=str(p),CRITIC_MAX_REVIEWS='3',REQUIRE_CRITIC_GATES='1',IMAGE_REQUEST_LIMIT=str(args.request_limit))
cmd=[str(p/'node_modules/.bin/pi'),'--provider','cliproxy','--model','gpt-6.1-sol','--thinking','high','--no-context-files','--no-extensions','--no-skills','--mode','json','--print','--session-dir',str(run/'sessions'),'--skill',str(run/'.pi/skills/game-cell-registration'),'Read TASK.md in your working directory. The only game inputs are input/description.md and input/screenshots/. Inspect them and execute the complete pipeline yourself. No geometry, inventory or prior generated assets have been supplied.']
with (run/'pi_trace.jsonl').open('w') as log:result=subprocess.run(cmd,cwd=run,env=env,stdout=log,stderr=subprocess.PIPE,text=True)
print('Pi exit',result.returncode);print(result.stderr[-2000:])
from review_gate import accepted_review
quality={}
for stage in ['geometry','assets','scene']:
 try:accepted_review(run,stage);quality[stage]='pass'
 except (ValueError,OSError) as e:quality[stage]=str(e)
status={'process_exit':result.returncode,'gates':quality,'accepted':result.returncode==0 and all(v=='pass' for v in quality.values())}
(run/'quality_status.json').write_text(json.dumps(status,indent=2));print('Quality accepted:',status['accepted'])
raise SystemExit(result.returncode if result.returncode else (0 if status['accepted'] else 2))
