import numpy as np
import pytest
from lakewatch.core import mndwi, otsu, compare
from lakewatch.pipeline import grid, vector

def test_scl_nodata_negative_and_zero_are_excluded():
    g=np.array([.2,.2,0,-.1,np.nan,.2]);s=np.array([.1,.1,0,.1,.1,.1])
    v=np.array([6,9,6,6,6,3]);idx,valid=mndwi(g,s,v)
    assert valid.tolist()==[True,False,False,False,False,False]
    assert idx[0]==pytest.approx(1/3)

def test_change_only_uses_common_observations():
    a=np.array([[.5,.5],[-.5,.5]]);b=np.array([[-.5,-.5],[.5,.5]])
    va=np.ones((2,2),bool);vb=np.array([[True,False],[True,True]])
    r,_,_,_=compare(a,va,b,vb,400)
    assert r['gain_km2']==.0004 and r['loss_km2']==.0004
    assert r['net_km2']==0 and r['common_valid_fraction']==.75

def test_all_cloud_does_not_create_water():
    r,*_=compare(np.ones((2,2)),np.zeros((2,2),bool),np.ones((2,2)),np.ones((2,2),bool),400)
    assert r['after_km2']==0 and r['common_valid_fraction']==0

def test_otsu_bimodal_and_failures():
    t=otsu(np.r_[np.full(200,-.5),np.full(200,.5)])
    assert -.5<t<.5
    for x in [np.ones(200),np.arange(2),np.array([np.nan]*200)]:
        with pytest.raises(ValueError):otsu(x)

def test_grid_is_repeatable_and_metric():
    t,dim=grid([114.34,30.5,114.44,30.61],'EPSG:32650',20)
    assert t.a==20 and t.e==-20 and min(dim)>400
    assert (t,dim)==grid([114.34,30.5,114.44,30.61],'EPSG:32650',20)

def test_vector_area_holes_and_disjoint_components():
    from rasterio.transform import from_origin
    mask=np.array([[1,1,1,0],[1,0,1,0],[1,1,1,1]],dtype=bool)
    features,area=vector(mask,from_origin(250000,3400000,20,20),'EPSG:32650',{})
    assert area==9*400 and len(features)==1
    assert len(features[0]['geometry']['coordinates'])==2

@pytest.mark.parametrize('pa',[0,-1,float('nan')])
def test_invalid_area_rejected(pa):
    with pytest.raises(ValueError):compare(np.ones((2,2)),np.ones((2,2),bool),np.ones((2,2)),np.ones((2,2),bool),pa)
