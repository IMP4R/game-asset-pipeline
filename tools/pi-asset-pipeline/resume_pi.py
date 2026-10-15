"""Resume own builder session with generic refinement and cumulative budgets."""
from pathlib import Path
import argparse,os,subprocess,shutil,json
from review_gate import accepted_review
p=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--request-limit',type=int,required=True);ap.add_argument('--review-limit',type=int,default=6);ap.add_argument('--protocol',default='REFINEMENT.md');a=ap.parse_args();r=a.run.resolve()
if not (r/'sessions').is_dir():ap.error('No existing builder session')
# Update generic review/refinement machinery only; do NOT alter game artifacts.
for f in ['critic.py','CRITIC.md','review_gate.py','image_edit.py',a.protocol]:shutil.copyfile(p/f,r/f)
env=os.environ.copy();env['CLIPROXY_API_KEY']=subprocess.run(['python3','/Users/user0/golden-land-new/scripts/read-credential-key.py','CLIPROXY_API_KEY'],capture_output=True,text=True,check=True).stdout.strip()
env.update(PI_CODING_AGENT_DIR=str(p/'pi-config'),PI_RUNTIME_DIR=str(p),PIPELINE_RUN_DIR=str(r),IMAGE_REQUEST_LIMIT=str(a.request_limit),CRITIC_MAX_REVIEWS=str(a.review_limit),CRITIC_TIMEOUT='1000',REQUIRE_CRITIC_GATES='1',PI_TELEMETRY='0',NODE_OPTIONS='--max-old-space-size=768')
cmd=[str(p/'node_modules/.bin/pi'),'--continue','--session-dir',str(r/'sessions'),'--provider','cliproxy','--model','gpt-6.1-sol','--thinking','high','--no-context-files','--no-extensions','--no-skills','--mode','json','--print','Read '+a.protocol+' and updated CRITIC.md. Continue your own reconstruction with independent critics. Cumulative image limit '+str(a.request_limit)+' and per-stage review limit '+str(a.review_limit)+'. Obey the selected protocol scope and budgets. Execute corrections, not only a plan; all original input remains in input/.']
with (r/'pi_trace.jsonl').open('a') as log:result=subprocess.run(cmd,cwd=r,env=env,stdout=log,stderr=subprocess.PIPE,text=True)
status={'process_exit':result.returncode,'gates':{}}
for stage in ['geometry','assets','scene']:
 try:accepted_review(r,stage);status['gates'][stage]='pass'
 except (ValueError,OSError) as e:status['gates'][stage]=str(e)
status['accepted']=result.returncode==0 and all(v=='pass' for v in status['gates'].values());(r/'quality_status.json').write_text(json.dumps(status,indent=2));print('Pi exit',result.returncode,'Accepted',status['accepted']);print(result.stderr[-1000:]);raise SystemExit(result.returncode if result.returncode else (0 if status['accepted'] else 2))
