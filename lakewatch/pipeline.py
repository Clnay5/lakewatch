"""STAC -> HTTP COG windows -> aligned reflectance -> water/change products."""
import argparse, base64, hashlib, io, json, math, platform, time
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import shapes
from rasterio.transform import from_origin
from rasterio.windows import from_bounds, Window
from rasterio.warp import reproject, transform_bounds, transform_geom
from shapely.geometry import shape, mapping
import requests
from PIL import Image
from .core import mndwi, otsu, compare
from .rangeio import opener

ROOT = Path(__file__).resolve().parents[1]

def grid(bbox, crs, resolution):
    left, bottom, right, top = transform_bounds('EPSG:4326', crs, *bbox, densify_pts=21)
    left = math.floor(left/resolution)*resolution
    top = math.ceil(top/resolution)*resolution
    width = math.ceil((right-left)/resolution); height = math.ceil((top-bottom)/resolution)
    return from_origin(left, top, resolution, resolution), (height, width)

def read_asset(asset, transform, dims, crs, categorical=False):
    """Read native-resolution COG blocks only around destination bounds, then warp.

    Continuous reflectance uses bilinear; categorical SCL always nearest.
    Reflectance scaling happens BEFORE interpolation, and nodata stays NaN.
    """
    bounds = rasterio.transform.array_bounds(*dims, transform)
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', GDAL_HTTP_MAX_RETRY=3,
                      GDAL_HTTP_RETRY_DELAY=1, GDAL_HTTP_TIMEOUT=60):
        with rasterio.open(asset['href'], opener=opener) as src:
            sb = transform_bounds(crs, src.crs, *bounds, densify_pts=21)
            w = from_bounds(*sb, src.transform)
            x0 = max(0, math.floor(w.col_off)-2); y0 = max(0, math.floor(w.row_off)-2)
            x1 = min(src.width, math.ceil(w.col_off+w.width)+2)
            y1 = min(src.height, math.ceil(w.row_off+w.height)+2)
            if x1 <= x0 or y1 <= y0: raise ValueError('Asset does not intersect destination')
            window = Window(x0, y0, x1-x0, y1-y0)
            raw = src.read(1, window=window, masked=True)
            data = raw.astype('float32').filled(np.nan)
            meta = asset.get('raster:bands', [{}])[0]
            if not categorical:
                if 'scale' not in meta: raise ValueError('Missing reflectance scaling metadata')
                data = data*meta['scale'] + meta.get('offset', 0)
            out = np.full(dims, np.nan, dtype='float32')
            reproject(data, out, src_transform=src.window_transform(window), src_crs=src.crs,
                      src_nodata=np.nan, dst_transform=transform, dst_crs=crs, dst_nodata=np.nan,
                      resampling=Resampling.nearest if categorical else Resampling.bilinear)
            return out, {'window': [x0,y0,x1-x0,y1-y0], 'source_crs': str(src.crs),
                         'source_resolution': list(src.res), 'scale': meta.get('scale'),
                         'offset': meta.get('offset'), 'href': asset['href']}

def search(config, bbox, interval):
    params = {'collections': config['collection'], 'bbox': ','.join(map(str,bbox)),
              'datetime': interval, 'limit':100}
    r=requests.get(config['catalog']+'/search',params=params,timeout=90);r.raise_for_status()
    result=r.json(); features=result['features']; seen={r.url}
    while True:
        nxt=next((l for l in result.get('links',[]) if l['rel']=='next'),None)
        if not nxt:break
        url=nxt['href']
        if url in seen or len(seen)>20:raise RuntimeError('Pagination cycle or more than 20 pages')
        seen.add(url)
        page=requests.get(url,timeout=90);page.raise_for_status();result=page.json()
        features.extend(result['features'])
    # Must cover the actual rectangle (including irregular footprint), not only scene bbox.
    from shapely.geometry import box
    items=list({i['id']:i for i in features if shape(i['geometry']).covers(box(*bbox))}.values())
    return sorted(items,key=lambda i:(i['properties'].get('eo:cloud_cover',100),i['id'])), r.url

def obtain(config, site, period, transform, dims, cache, pinned):
    dest=cache/f"{site['id']}-{period}.npz"
    meta_path=dest.with_suffix('.json')
    signature=hashlib.sha256(json.dumps([config,site,period,'mndwi-v1'],sort_keys=True).encode()).hexdigest()
    if dest.exists() and meta_path.exists() and json.loads(meta_path.read_text()).get('cache_signature')==signature:
        with np.load(dest) as arrays:
            return arrays['index'].copy(),arrays['valid'].copy(),json.loads(meta_path.read_text())
    if pinned:
        manifest=json.loads((ROOT/'data'/'manifest.json').read_text())
        prev=next(x for x in manifest['observations'] if x['site']==site['id'] and x['period']==period)
        url=config['catalog']+'/collections/'+config['collection']+'/items/'+prev['item_id']
        r=requests.get(url,timeout=90);r.raise_for_status(); candidates=[r.json()]; query=url
    else: candidates,query=search(config,site['bbox'],config['periods'][period])
    rejected=[]
    candidates=[i for i in candidates if float(i['properties'].get('s2:processing_baseline','99'))<4]
    for item in candidates[:8]:
        print('READ',site['id'],period,item['id'],flush=True)
        # Fail closed for the known legacy-catalog post-baseline-4 offset ambiguity.
        # Do not guess a correction from visual appearance or negative pixel counts.
        if float(item['properties'].get('s2:processing_baseline','99'))>=4:
            raise ValueError('Legacy catalog baseline >=4 requires independent radiometric audit; see docs/method.md')
        arrays={}; provenance={}
        for band in ('green','swir16','scl'):
            arrays[band],provenance[band]=read_asset(item['assets'][band],transform,dims,config['crs'],band=='scl')
        index,valid=mndwi(arrays['green'],arrays['swir16'],arrays['scl'])
        if valid.mean()<config['minimum_valid_fraction']:
            rejected.append({'item_id':item['id'],'valid_fraction':float(valid.mean())});continue
        cache.mkdir(exist_ok=True,parents=True)
        np.savez_compressed(dest,index=index,valid=valid)
        digest=hashlib.sha256(index.tobytes()+valid.tobytes()).hexdigest()
        meta={'site':site['id'],'period':period,'item_id':item['id'],'cache_signature':signature,
              'datetime':item['properties']['datetime'],'scene_cloud_percent':item['properties'].get('eo:cloud_cover'),
              'valid_fraction':float(valid.mean()),'query':query,'assets':provenance,
              'aligned_array_sha256':digest,'rejected_candidates':rejected}
        meta_path.write_text(json.dumps(meta,indent=2),encoding='utf-8')
        return index,valid,meta
    raise RuntimeError(f'No accepted observation: {site["id"]}/{period}; {rejected}')

def svg_image(index, valid, mode='index'):
    rgba=np.zeros((*index.shape,4),dtype=np.uint8);rgba[:]=[35,42,54,255]
    if mode=='index':
        v=np.nan_to_num(index)
        rgba[valid & (v<=0)]=[191,172,136,255]
        rgba[valid & (v>0)]=[32,170,210,255]
    else:
        rgba[valid]=[86,99,104,255];rgba[index==1]=[30,210,170,255];rgba[index==2]=[250,119,89,255]
    img=Image.fromarray(rgba); img.thumbnail((800,800),Image.Resampling.NEAREST)
    stream=io.BytesIO();img.save(stream,format='PNG')
    return '<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s"><image width="100%%" height="100%%" href="data:image/png;base64,%s"/></svg>'%(*img.size,*img.size,base64.b64encode(stream.getvalue()).decode())

def vector(mask, transform, crs, properties):
    features=[]; area=0
    for geom,val in shapes(mask.astype('uint8'),mask=mask,transform=transform):
        if val!=1:continue
        poly=shape(geom);area+=poly.area
        # Keep pixel-exact polygon, no simplifying that would change audit area.
        features.append({'type':'Feature','properties':properties,
                         'geometry':transform_geom(crs,'EPSG:4326',mapping(poly),precision=7)})
    return features,area

def run(config_path, out, pinned=False):
    config=json.loads(config_path.read_text(encoding='utf-8'));out.mkdir(exist_ok=True,parents=True)
    cache=ROOT/'data'/'cache';observations=[];results=[];periods=list(config['periods'])
    for site in config['sites']:
        transform,dims=grid(site['bbox'],config['crs'],config['resolution_m'])
        a,va,ma=obtain(config,site,periods[0],transform,dims,cache,pinned)
        b,vb,mb=obtain(config,site,periods[1],transform,dims,cache,pinned)
        observations.extend([ma,mb]);pa=abs(transform.a*transform.e-transform.b*transform.d)
        fixed,common,gain,loss=compare(a,va,b,vb,pa)
        thresholds={p:otsu(arr[v]) for p,arr,v in zip(periods,(a,b),(va,vb))}
        sensitivity=[{'threshold':t,**compare(a,va,b,vb,pa,t)[0]} for t in (-.1,0,.1,.2)]
        features=[];checks=[]
        for label,mask in [('gain',gain),('loss',loss)]:
            f,area=vector(mask,transform,config['crs'],{'site':site['id'],'change':label})
            features.extend(f); expected=float(mask.sum()*pa)
            checks.append({'class':label,'raster_area_m2':expected,'polygon_area_m2':area,'difference_m2':area-expected})
            if abs(area-expected)>1e-4:raise RuntimeError('Raster/vector area mismatch')
        (out/f"{site['id']}-change.geojson").write_text(json.dumps({'type':'FeatureCollection','features':features}),encoding='utf-8')
        for period,arr,v in zip(periods,(a,b),(va,vb)):
            (out/f"{site['id']}-{period}.svg").write_text(svg_image(arr,v),encoding='utf-8')
        change=np.zeros(dims,dtype='uint8');change[gain]=1;change[loss]=2
        (out/f"{site['id']}-change.svg").write_text(svg_image(change,common,'change'),encoding='utf-8')
        # Reusable aligned, georeferenced artifact for downstream engineering.
        with rasterio.open(cache/f"{site['id']}-mndwi.tif",'w',driver='GTiff',height=dims[0],width=dims[1],
                           count=2,dtype='float32',crs=config['crs'],transform=transform,nodata=-9999,
                           compress='deflate',tiled=True) as dst:
            dst.write(np.where(va,a,-9999).astype('float32'),1);dst.write(np.where(vb,b,-9999).astype('float32'),2)
        results.append({**site,'shape':list(dims),'transform':list(transform)[:6],
                        'fixed_threshold':0,'change_on_common_support':fixed,'sensitivity':sensitivity,
                        'otsu_thresholds':thresholds,'polygon_area_checks':checks,
                        'individual_observed_water_km2':{p:float(((arr>0)&v).sum()*pa/1e6) for p,arr,v in zip(periods,(a,b),(va,vb))}})
    manifest={'generated_at':datetime.now(timezone.utc).isoformat(),'config':config,'observations':observations,
              'environment':{'python':platform.python_version(),'numpy':np.__version__,'rasterio':rasterio.__version__,'gdal':rasterio.__gdal_version__},
              'method':'MNDWI > 0, SCL in {4,5,6}; intersection-of-valid temporal support; Otsu diagnostic only',
              'limitations':['Study rectangles include other water bodies; not cadastral lake boundaries.',
                             'No independent human labels: no accuracy, IoU or causal hydrology claim.',
                             'Threshold sweep is sensitivity, not a confidence interval.',
                             'Scene cloud metadata ranks candidates; actual local SCL validity gates acceptance.',
                             '20 m UTM grid area is projected area; shoreline mixed pixels and SCL errors remain.']}
    (ROOT/'data'/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (out/'results.json').write_text(json.dumps({'manifest':manifest,'sites':results},indent=2),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=True,indent=2))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,default=ROOT/'config.json')
    parser.add_argument('--out',type=Path,default=ROOT/'docs'/'results');parser.add_argument('--pinned',action='store_true')
    args=parser.parse_args();run(args.config,args.out,args.pinned)

if __name__=='__main__':main()
