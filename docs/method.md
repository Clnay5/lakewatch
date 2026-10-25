# Method and evidence limits

The published study is a historical 2021 two-date comparison of rectangular windows around Donghu and Tangxun lakes, Wuhan. It does not claim official lake boundaries, current conditions or seasonal mean area.

## Radiometry gate

During development, a 2025 scene (`S2B_50RKU_20250227_0_L2A`) advertised scale 0.0001 and offset -0.1 but applying these yielded substantial negative reflectance in the window. Earth Search has published user reports of legacy-collection offset inconsistencies: [issue 71](https://github.com/Element84/earth-search/issues/71), [issue 66](https://github.com/Element84/earth-search/issues/66). This observation alone cannot establish the correct correction. We do not infer or silently override an offset from appearance. The current pipeline accepts only processing baseline <04.00. Reprocessed historical scenes with newer baselines are excluded. Expanding support requires cross-checking source SAFE/JP2 pixels and metadata, or a separately audited provider.

## Spatial and temporal support

Each site's WGS84 bounding rectangle is transformed to an EPSG:32650 envelope, snapped to a 20 m grid. This grid envelope is the analysis window and may extend slightly beyond the original rectangle. Green and SWIR reflectance are bilinearly warped onto exactly the same grid. SCL uses nearest neighbour. Continuous nodata is NaN before resampling. SCL classes 4,5,6 are retained; 0,1,2,3,7,8,9,10,11 are excluded. In older scenes class 2 includes dark features, so this conservative policy can exclude legitimate water and urban surfaces. This is missing observation, not proof of dry land.

The minimum accepted single-scene valid fraction is 65% because a strict class mask can leave substantial unobserved area even in visually clear scenes. The displayed actual common coverage is the key interpretation limit. Values below 85% produce an explicit warning; the threshold is an engineering policy, not a scientific confidence threshold. All temporal gain/loss calculations use the intersection of valid masks. Individual-scene observed area is separately recorded and must not be subtracted as if supports matched. No spatial extrapolation fills missing areas.

MNDWI=(green−SWIR16)/(green+SWIR16), requiring nonnegative reflectance and denominator >1e-6. Default water criterion is >0. The same thresholds -0.1,0,0.1,0.2 are swept on both dates. Otsu is an additional per-scene diagnostic, never substituted into the default comparison. Sensitivity is not statistical uncertainty.

Pixel count × 400 m² gives projected area. Rasterio polygonization followed by Shapely planar area independently checks this accounting (before transforming polygons to WGS84). This validates geometry/accounting consistency, not water classification accuracy. The product does not measure volume or explain hydrological causes.

## Reproducibility

`data/manifest.json` records item IDs, native band URLs, read windows, source resolution, scale/offset, local valid coverage, candidates rejected for coverage, Python/NumPy/GDAL/Rasterio versions and aligned-array SHA-256. `--pinned` reuses these exact items when cache is absent. Source data can be revised upstream; compare hashes after replay. Full-image downloads are unnecessary: a bounded HTTPS Range reader feeds Rasterio's documented Python opener, validating 206/Content-Range and retaining certificate checks.

No independent human-labeled shorelines were available. There is no validated IoU/F1/area-error score. A future evaluation should annotate blinded held-out shoreline tiles across cloudy/turbid/urban cases, document agreement, and report stratified error. Such evaluation is not represented as completed here.

## Primary implementation references

- [Rasterio windows](https://rasterio.readthedocs.io/en/stable/topics/windowed-rw.html)
- [Rasterio reprojection](https://rasterio.readthedocs.io/en/stable/topics/reproject.html)
- [Rasterio Python openers](https://rasterio.readthedocs.io/en/latest/topics/vsi.html)
- [Earth Search v1](https://element84.com/geospatial/introducing-earth-search-v1-new-datasets-now-available/)
- Xu, H. (2006), Modification of normalised difference water index to enhance open water features. DOI: [10.1080/01431160600589179](https://doi.org/10.1080/01431160600589179). Algorithm attribution, not a claim of inventing MNDWI.
