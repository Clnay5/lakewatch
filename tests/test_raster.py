import numpy as np
import rasterio
from rasterio.transform import from_origin
from lakewatch.pipeline import read_asset

def test_reproject_scale_and_categorical_resampling(tmp_path, monkeypatch):
    # Exercise actual GDAL interpolation and masks, not a hand-copied formula.
    p=tmp_path/'native.tif'
    with rasterio.open(p,'w',driver='GTiff',width=4,height=4,count=1,dtype='uint16',
                       crs='EPSG:32650',transform=from_origin(250000,3400000,10,10),nodata=0) as d:
        a=np.full((4,4),2000,dtype='uint16');a[0,0]=0;d.write(a,1)
    import lakewatch.pipeline as pipeline
    from builtins import open as localopen
    monkeypatch.setattr(pipeline,'opener',lambda path,mode='rb':localopen(path,mode))
    dst=from_origin(250000,3400000,20,20)
    asset={'href':str(p),'raster:bands':[{'scale':.0001,'offset':-.1}]}
    arr,_=read_asset(asset,dst,(2,2),'EPSG:32650')
    assert np.allclose(arr,.1)
    cats,_=read_asset(asset,dst,(2,2),'EPSG:32650',True)
    assert set(np.unique(cats))=={2000}
