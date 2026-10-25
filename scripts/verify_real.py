"""Local integration audit of computed real products; does not claim classification truth."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
r=json.loads((ROOT/'docs/results/results.json').read_text(encoding='utf-8'))
checks=[]
for o in r['manifest']['observations']:
    with np.load(ROOT/f"data/cache/{o['site']}-{o['period']}.npz") as a:
        digest=hashlib.sha256(a['index'].tobytes()+a['valid'].tobytes()).hexdigest()
        assert digest==o['aligned_array_sha256']
        assert float(a['valid'].mean())==o['valid_fraction']
        assert o['assets']['green']['scale']==.0001
        checks.append({'item':o['item_id'],'site':o['site'],'sha256_matches':True,'valid_fraction':o['valid_fraction']})
for s in r['sites']:
    c=s['change_on_common_support']
    assert abs(c['after_km2']-c['before_km2']-c['net_km2'])<1e-9
    assert abs(c['gain_km2']-c['loss_km2']-c['net_km2'])<1e-9
    assert all(x['difference_m2']==0 for x in s['polygon_area_checks'])
out={'status':'passed','observations':checks,'sites':len(r['sites']),
     'checks':['aligned-array SHA-256','local valid coverage','net=gain-loss','net=after-before','pixel/polygon metric area'],
     'scope':'Data and accounting integrity only; no independent water classification truth'}
(ROOT/'evidence').mkdir(exist_ok=True)
(ROOT/'evidence/real-audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
