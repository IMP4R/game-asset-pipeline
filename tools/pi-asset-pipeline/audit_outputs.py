"""Mechanical artifact audit, NOT a visual acceptance verdict. No network calls."""
from pathlib import Path
import json,collections
from PIL import Image
ROOT=Path(__file__).parent

def audit_outputs():
 ledger=ROOT/'image_requests.jsonl';events=[json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
 states=collections.defaultdict(list)
 for e in events:states[e['id']].append(e['state'])
 counts={s:sum(e['state']==s for e in events) for s in ['submitted','success','failed']}
 incomplete=[rid for rid,s in states.items() if 'submitted' in s and not any(t in s for t in ['success','failed'])]
 required=['game_description.md','grid.json','asset_map.json','reconstructed.png','final_ab.png','report.md']
 artifacts={}
 for n in required:
  p=ROOT/'output'/n;entry={'exists':p.exists()}
  if p.exists():
   entry['bytes']=p.stat().st_size
   if p.suffix=='.json':
    try:json.loads(p.read_text());entry['valid_json']=True
    except Exception:entry['valid_json']=False
   if p.suffix=='.png':
    try:
     with Image.open(p) as im:entry['size']=im.size;im.verify();entry['valid_image']=True
    except Exception:entry['valid_image']=False
  artifacts[n]=entry
 result={'counts':counts,'pending_or_interrupted_requests':incomplete,'models':sorted(set(e['model'] for e in events)), 'request_budget_ok':counts['submitted']<=8,'artifacts':artifacts,'visual_acceptance':'NOT assessed by this audit'}
 (ROOT/'artifact_audit.json').write_text(json.dumps(result,indent=2));return result
if __name__=='__main__':print(json.dumps(audit_outputs(),indent=2))
