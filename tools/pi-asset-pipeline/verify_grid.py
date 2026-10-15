"""Regression acceptance for user-approved sample only, not universal grid detection."""
from pathlib import Path
import json,math
p=Path(__file__).parent;grid=json.loads((p/'output/grid.json').read_text())
origin=grid['origin'];cv=grid['column_vector'];rv=grid['row_vector'];errs=[]
for row in range(7):
 for col in range(8):
  actual=[origin[i]+col*cv[i]+row*rv[i] for i in range(2)]
  expected=[42+48*col,431+44*row]
  errs.append(math.dist(actual,expected))
report={'regression_only':True,'accepted_source':'User-approved original grid: x42+48c,y431+44r','intersections':len(errs),'max_user_grid_delta_px':max(errs),'mean_user_grid_delta_px':sum(errs)/len(errs),'within_2px':max(errs)<=2,'does_not_prove':'Independent universal visual fitting or generated-background registration'}
(p/'grid_regression_evidence.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));raise SystemExit(0 if report['within_2px'] else 1)
