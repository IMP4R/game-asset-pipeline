"""Rebuild previously generated outputs WITHOUT network/image charges."""
from pathlib import Path
import subprocess,sys
p=Path(__file__).parent
steps=['output/measure_grid.py','output/build_inventory.py','output/prepare_fidelity.py','output/extract_sprites.py','output/register_environment.py','output/assemble.py','output/finalize_report.py','verify_grid.py','grid_registration_ab.py','audit_outputs.py']
for step in steps:
 script=p/step
 if not script.exists():raise SystemExit('Missing pipeline step '+step)
 print('LOCAL STEP',step,flush=True)
 subprocess.run([sys.executable,str(script)],cwd=p,check=True)
print('Local replay complete. No network clients invoked; visual review still required.')
