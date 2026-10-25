"""Pure numerical operations. No network or global state."""
import numpy as np

VALID_SCL = (4, 5, 6)  # vegetation, bare soil, water; exclude clouds, shadow, snow, unclassified

def mndwi(green, swir, scl):
    green, swir = np.asarray(green), np.asarray(swir)
    valid = np.isin(scl, VALID_SCL) & np.isfinite(green) & np.isfinite(swir)
    valid &= (green >= 0) & (swir >= 0) & ((green + swir) > 1e-6)
    result = np.full(green.shape, np.nan, dtype='float32')
    np.divide(green - swir, green + swir, out=result, where=valid)
    return result, valid

def otsu(values, bins=256):
    values = np.asarray(values); values = values[np.isfinite(values)]
    if values.size < 100 or np.ptp(values) < 1e-6:
        raise ValueError('Otsu requires at least 100 finite, nonconstant observations')
    counts, edges = np.histogram(values, bins=bins, range=(-1, 1))
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(counts); w1 = values.size - w0
    s0 = np.cumsum(counts * centers); total = s0[-1]
    score = np.full(bins, -np.inf)
    good = (w0 > 0) & (w1 > 0)
    score[good] = w0[good] * w1[good] * (s0[good]/w0[good] - (total-s0[good])/w1[good])**2
    return float(edges[int(np.argmax(score)) + 1])

def compare(a, va, b, vb, pixel_area, threshold=0.0):
    if a.shape != b.shape or va.shape != a.shape or vb.shape != a.shape:
        raise ValueError('Inputs must share a grid and shape')
    if pixel_area <= 0 or not np.isfinite(pixel_area):
        raise ValueError('Pixel area must be finite and positive')
    common = va & vb & np.isfinite(a) & np.isfinite(b)
    before = (a > threshold) & common; after = (b > threshold) & common
    gained = after & ~before; lost = before & ~after
    return {
        'common_valid_fraction': float(common.mean()),
        'before_km2': float(before.sum()*pixel_area/1e6),
        'after_km2': float(after.sum()*pixel_area/1e6),
        'gain_km2': float(gained.sum()*pixel_area/1e6),
        'loss_km2': float(lost.sum()*pixel_area/1e6),
        'net_km2': float((int(after.sum())-int(before.sum()))*pixel_area/1e6),
    }, common, gained, lost
