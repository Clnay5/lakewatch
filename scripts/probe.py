import json, urllib.request
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'data';p.mkdir(exist_ok=True)
url='https://earth-search.aws.element84.com/v1/search?collections=sentinel-2-l2a&bbox=114.31,30.36,114.44,30.61&datetime=2025-01-01T00:00:00Z/2025-02-28T23:59:59Z&limit=100'
with urllib.request.urlopen(url,timeout=90) as f: result=json.load(f)
(p/'probe.json').write_text(json.dumps(result),encoding='utf-8')
items=sorted(result['features'],key=lambda x:x['properties'].get('eo:cloud_cover',100))
for i in items[:5]:print(i['id'],i['properties'].get('eo:cloud_cover'),i['bbox'])
print(json.dumps(items[0]['assets']['green'],indent=2))
