"""Live read-only critic smoke on an existing run, no image generation."""
from pathlib import Path
import os,sys,subprocess,json
p=Path(__file__).parent.resolve();run=Path(sys.argv[1]).resolve()
manifest={'items':[{'id':'complete_scene','files':['input/screenshots/000_original.png','output/reconstruction.png','output/registration.json','output/asset_map.json']}]}
f=run/'scene_critic_smoke.json';f.write_text(json.dumps(manifest,indent=2))
env=os.environ.copy();env['CLIPROXY_API_KEY']=subprocess.run(['python3','/Users/user0/golden-land-new/scripts/read-credential-key.py','CLIPROXY_API_KEY'],capture_output=True,text=True,check=True).stdout.strip()
env.update(PI_RUNTIME_DIR=str(p),PIPELINE_RUN_DIR=str(run),PI_CODING_AGENT_DIR=str(p/'pi-config'))
r=subprocess.run([sys.executable,str(p/'critic.py'),'--stage','scene','--manifest',str(f)],cwd=run,env=env);raise SystemExit(r.returncode)
