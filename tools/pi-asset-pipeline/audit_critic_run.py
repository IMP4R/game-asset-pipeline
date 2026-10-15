"""Read-only run audit. Does not infer fidelity from API success or alter builder work."""
from pathlib import Path
import argparse,json
from review_gate import accepted_review

def audit(root):
 root=Path(root).resolve();ledger=root/'image_requests.jsonl';events=[json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
 submitted={e['id']:e for e in events if e['state']=='submitted'};terminal={e['id']:e for e in events if e['state'] in ['success','failed']}
 gates={}
 for stage in ['geometry','assets','scene']:
  try:accepted_review(root,stage);gates[stage]={'accepted_current_bytes':True}
  except (ValueError,OSError,json.JSONDecodeError) as e:gates[stage]={'accepted_current_bytes':False,'reason':str(e)}
 trace=root/'pi_trace.jsonl';tools=0;legacy=[]
 if trace.exists():
  with trace.open() as f:
   for line in f:
    try:e=json.loads(line)
    except ValueError:continue
    if e.get('type')!='tool_execution_start':continue
    tools+=1;text=json.dumps(e.get('args',{}))
    # Audit leakage markers only, NOT geometry authority supplied to agent.
    for marker in ['/scene_rebuild_v','/pi-asset-pipeline/output/']:
     if marker in text:legacy.append({'tool':e.get('toolName'),'marker':marker})
 return {'run':str(root),'submitted':len(submitted),'success':sum(e['state']=='success' for e in terminal.values()),'failed':sum(e['state']=='failed' for e in terminal.values()),'unconfirmed':sorted(set(submitted)-set(terminal)),'gates':gates,'tool_calls':tools,'historical_access_markers':legacy,'scope':'Read-only metadata audit; absence of markers is not OS isolation proof; acceptance is critic judgement, not pixel-perfect guarantee.'}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);args=ap.parse_args();print(json.dumps(audit(args.run),indent=2))
