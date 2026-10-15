"""Fail-closed review gate. Critic reports must cover the current artifact bytes."""
from pathlib import Path
import hashlib,json

def digest(path):
 return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def accepted_review(root,stage):
 root=Path(root).resolve()
 reports=sorted((root/'output/critics').glob(f'{stage}-*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
 for path in reports:
  report=json.loads(path.read_text())
  if report.get('stage')!=stage:continue
  # Never fall back to an older pass after a newer rejection or technical failure.
  if report.get('verdict')!='pass':raise ValueError(f'{stage} critic has not passed: {path.name}')
  hashes=report.get('file_hashes',{})
  if not hashes:raise ValueError('Critic report lacks artifact hashes')
  for name,expected in hashes.items():
   f=(root/name).resolve()
   if not f.is_relative_to(root) or not f.is_file() or digest(f)!=expected:raise ValueError('Review stale or missing artifact: '+name)
  return report
 raise ValueError(f'Missing independent {stage} review. Run critic.py first.')
