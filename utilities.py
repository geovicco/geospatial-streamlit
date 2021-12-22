import streamlit as st
import ee
import geemap.foliumap as geemap
import geemap as gmap
import folium
import geopandas as gpd
from datetime import date, timedelta

def initialize_sessionState():
    if st.session_state.get("zoom_level") is None:
        st.session_state["zoom_level"] = 4
    if st.session_state.get("aoi") is None:
        st.session_state["aoi"] = 'Not Selected'
    if st.session_state.get("useNDVI") is None:
        st.session_state["useNDVI"] = False


def add_geocoder(mapObject):
    with st.expander("Search Location", False):
        # SEARCH LOCATION
        keyword = st.text_input("Search for a location:", '')
        if keyword:
            locations = geemap.geocode(keyword)
            if locations is not None and len(locations) > 0:
                str_locations = [str(g)[1:-1] for g in locations]
                location = st.selectbox("Select a location:", str_locations)
                loc_index = str_locations.index(location)
                selected_loc = locations[loc_index]
                lat, lng = selected_loc.lat, selected_loc.lng
                folium.Marker(location=[lat, lng], popup=location).add_to(mapObject)
                mapObject.set_center(lng, lat, 13)
                st.session_state["zoom_level"] = 13
        
        else:
            coords = st.text_input('Search using Lat/Lon (Decimal Degrees)', '')
            if coords:
                locations = geemap.geocode(coords, reverse=True)
                str_locations = [str(g)[1:-1] for g in locations]
                location = str_locations[0]
                loc_index = str_locations.index(location)
                selected_loc = locations[loc_index]
                lat, lng = selected_loc.lat, selected_loc.lng
                folium.Marker(location=[lat, lng], popup=None).add_to(mapObject)
                mapObject.set_center(lng, lat, 16)
                st.session_state["zoom_level"] = 16

def uploaded_file_to_gdf(data, crs):
    import tempfile
    import os
    import uuid
    import zipfile

    _, file_extension = os.path.splitext(data.name)
    file_id = str(uuid.uuid4())
    file_path = os.path.join(tempfile.gettempdir(), f"{file_id}{file_extension}")

    with open(file_path, "wb") as file:
        file.write(data.getbuffer())

    if file_path.lower().endswith(".kml"):
        gpd.io.file.fiona.drvsupport.supported_drivers["KML"] = "rw"
        gdf = gpd.read_file(file_path, driver="KML")
        return gdf
    # If the user uploads a zipped shapefile
    # Only works when te name of the shapefile (XXXX.shp) is same te the name of the uploaded zip file (XXXX.zip)
    elif file_path.lower().endswith(".zip"):
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            # Extract the contents of the zip file into the temp directory
            zip_ref.extractall(os.path.join(tempfile.gettempdir(), file_id))
        # Return the filepath where the file_id.shp along with other components (.shx, .dbf, ...) are placed. 
        return os.path.join(tempfile.gettempdir(), file_id)
    else:
        gdf = gpd.read_file(file_path, crs = crs)
        return gdf

def add_aoi_selector(mapObject):
    with st.expander("Select Area of Interest (AOI)", False):
        optionsList = ["Search EE Assets", "Enter URL", "Upload Shapefile/GeoJSON"]
        option = st.radio("Select Option", optionsList)
        if option == optionsList[1]:
            url_data = st.text_input("Enter GeoJSON URL","")
            if url_data == '':
                st.info("Enter URL")
                pass
            else:
                gdf = gpd.read_file(url_data)
                st.session_state["aoi"] = geemap.geopandas_to_ee(gdf, geodesic=True)
                ee_obj = st.session_state['aoi'] 
                gdf['center'] = gdf.centroid
                gdf['lon'] = gdf.center.apply(lambda p: p.x)
                gdf['lat'] = gdf.center.apply(lambda p: p.y)
                lon = gdf.lon.mean()
                lat = gdf.lat.mean()
                zoomLevel = 10
                mapObject.addLayer(ee_obj, {}, 'AOI')
                mapObject.set_center(lon, lat, zoomLevel)
                st.session_state["aoi"] = ee_obj # Saving AOI to Session State
        elif option == optionsList[0]:
            ee_asset_search = st.text_input("Search EarthEngine FeatureCollection Asset", "")
            ee_assets_from_search = geemap.search_ee_data(ee_asset_search)
            asset_options = [asset['title'] for asset in ee_assets_from_search]
            if ee_asset_search == '':
                st.info("Search EE using keyword")
            elif len(asset_options) > 0:
                selected_ee_asset = st.selectbox("Select EE Asset", asset_options)
                selected_asset_index = asset_options.index(selected_ee_asset)
                asset = ee_assets_from_search[selected_asset_index]
                featureID = asset['id']
                ee_obj = ee.FeatureCollection(featureID)
                st.session_state['aoi'] = ee_obj
                mapObject.addLayer(ee_obj, {}, selected_ee_asset)
            else:
                st.info('Asset Not Found! Use a diffent keyword.')
        elif option == optionsList[2]:
            uploaded_file = st.file_uploader(
                    "Upload a GeoJSON or a Zipped Shapefile to use as an AOI.",
                    type=["geojson", "zip"]
                    )
            crs = {"init": "epsg:4326"}
            
            if uploaded_file != None:
                file_ext = uploaded_file.name.split('.')[-1]
                if file_ext == 'zip':
                    # Get Path to the temp directory where all contents of the shapefile are located
                    tempDirPath = uploaded_file_to_gdf(uploaded_file, crs)
                    # Get the name of the shapefile
                    shpName = uploaded_file.name.split('.zip')[0]
                    import os
                    # Read using geopandas
                    gdf = gpd.read_file(os.path.join(tempDirPath, (shpName + '.shp')))
                    
                    st.session_state["aoi"] = geemap.geopandas_to_ee(gdf, geodesic=False)
                    ee_obj = st.session_state['aoi']

                    from shapely.geometry import Polygon, Point

                    minx, miny, maxx, maxy = gdf.geometry.total_bounds
                    gdf_bounds = gpd.GeoSeries({
                        'geometry': Polygon([Point(minx, maxy), Point(maxx, maxy), Point(maxx, miny), Point(minx, miny)])
                    }, crs="EPSG:4326")
                    area = gdf_bounds.area.values[0]
                    center = gdf_bounds.centroid
                    center_lon = float(center.x); center_lat = float(center.y)

                    if area > 5:
                        zoomLevel = 8
                    elif area > 3:
                        zoomLevel = 10
                    elif area > 0.1 and area < 0.5:
                        zoomLevel = 11
                    else:
                        zoomLevel = 13
                    print(area, zoomLevel)
                    mapObject.addLayer(ee_obj, {}, 'aoi')
                    mapObject.set_center(center_lon, center_lat, zoomLevel)
                    st.session_state["aoi"] = ee_obj
                elif uploaded_file is None:
                    pass
                else:
                    gdf = uploaded_file_to_gdf(uploaded_file, crs)
                    st.session_state["aoi"] = geemap.geopandas_to_ee(gdf, geodesic=False)
                    ee_obj = st.session_state['aoi']
                    from shapely.geometry import Polygon, Point

                    minx, miny, maxx, maxy = gdf.geometry.total_bounds
                    gdf_bounds = gpd.GeoSeries({
                        'geometry': Polygon([Point(minx, maxy), Point(maxx, maxy), Point(maxx, miny), Point(minx, miny)])
                    }, crs="EPSG:4326")

                    area = gdf_bounds.area.values[0]
                    center = gdf_bounds.centroid
                    center_lon = float(center.x); center_lat = float(center.y)

                    if area > 5:
                        zoomLevel = 8
                    elif area > 3:
                        zoomLevel = 10
                    elif area > 0.1 and area < 0.5:
                        zoomLevel = 11
                    elif area < 2 and area > 1:
                        zoomLevel = 9
                    else:
                        zoomLevel = 13
                    print(area, zoomLevel)
                    mapObject.addLayer(ee_obj, {}, 'aoi')
                    mapObject.set_center(center_lon, center_lat, zoomLevel)
                    st.session_state["aoi"] = ee_obj
    
def set_params():
    with st.expander("Define Processing Parameters"):
        form = st.form(key='processing-params')
        fromDate = form.date_input('Start Date', date.today() - timedelta(days=61))
        toDate = form.date_input('End Date', date.today()-timedelta(days=1))
        useNDVI = form.checkbox("Use NDVI", False)
        satellite = form.radio("", [
                "Landsat 4",
                "Landsat 5",
                "Landsat 7",
                "Landsat 8"
            ], index=3)     
                   
        # Date Validation Check
        if toDate - fromDate < timedelta(days=30):
            st.error('Difference between the two selected data is too small. Try again!')
            st.stop()
        else:
            submit = form.form_submit_button('Submit')

        if submit:
            st.session_state['fromDate'] = fromDate
            st.session_state["toDate"] = toDate
            st.session_state["useNDVI"] = useNDVI
            st.session_state['satellite'] = satellite
            
        return st.session_state
    
################################################################################
############## LST Single Mono Window Algorithm ################################
############# CITATION FOR THIS ALGORITHM ###############
"""Ermida, S.L., Soares, P., Mantas, V., Göttsche, F.-M., Trigo, I.F., 2020. 
    Google Earth Engine open-source code for Land Surface Temperature estimation from the Landsat series.
    Remote Sensing, 12 (9), 1471; https://doi.org/10.3390/rs12091471
"""
# 1. Mask Clouds from TOA and SR Landsat Collection
def maskL8srClouds(image):
    # Bits 3 and 5 are cloud shadow and cloud, respectively.
    cloudShadowBitMask = (1 << 3); cloudsBitMask = (1 << 5)
    # Get the pixel QA band.
    qa = image.select('pixel_qa')
    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0).And(qa.bitwiseAnd(cloudsBitMask).eq(0))
    return image.updateMask(mask)

def maskL8toaClouds(image):
    # Bits 3 and 5 are cloud shadow and cloud, respectively.
    cloudShadowBitMask = (1 << 4)
    # Get the pixel QA band.
    qa = image.select('BQA')
    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0)
    return image.updateMask(mask)

# 2. Add NDVI Band to Landsat Collection
def addNDVI(landsat):
  def wrap(image):

    # choose bands
    nir = ee.String(ee.Algorithms.If(landsat=='Landsat 8','B5','B4'))
    red = ee.String(ee.Algorithms.If(landsat=='Landsat 8','B4','B3'))

    # compute NDVI
    return image.addBands(image.expression('(nir-red)/(nir+red)',{
      'nir':image.select(nir).multiply(0.0001),
      'red':image.select(red).multiply(0.0001)
    }).rename('NDVI'))
  return wrap

# 3. Calculate Total Precipitable Water
def addTPWBands(image):
    date = ee.Date(image.get('system:time_start'))
    year = ee.Number.parse(date.format('yyyy'))
    month = ee.Number.parse(date.format('MM'))
    day = ee.Number.parse(date.format('dd'))
    date1 = ee.Date.fromYMD(year,month,day)
    date2 = date1.advance(1,'days')

    def dateDist(image):
        return image.set('DateDist',ee.Number(image.get('system:time_start')).subtract(date.millis()).abs())

    #   # load atmospheric data collection
    TPWcollection = ee.ImageCollection('NCEP_RE/surface_wv').filter(ee.Filter.date(date1.format('yyyy-MM-dd'), date2.format('yyyy-MM-dd'))).map(dateDist)

    # select the two closest model times
    closest = (TPWcollection.sort('DateDist')).toList(2)

    # check if there is atmospheric data in the wanted day
    # if not creates a TPW image with non-realistic values
    # these are then masked in the SMWalgorithm function (prevents errors)
    tpw1 = ee.Image(ee.Algorithms.If(closest.size().eq(0), ee.Image.constant(-999.0),ee.Image(closest.get(0)).select('pr_wtr')))
    tpw2 = ee.Image(ee.Algorithms.If(closest.size().eq(0), ee.Image.constant(-999.0),ee.Algorithms.If(closest.size().eq(1), tpw1,ee.Image(closest.get(1)).select('pr_wtr'))))

    time1 = ee.Number(ee.Algorithms.If(closest.size().eq(0), 1.0, ee.Number(tpw1.get('DateDist')).divide(ee.Number(21600000))))
    time2 = ee.Number(ee.Algorithms.If(closest.size().lt(2), 0.0,ee.Number(tpw2.get('DateDist')).divide(ee.Number(21600000))))

    tpw = tpw1.expression('tpw1*time2+tpw2*time1', {'tpw1':tpw1,'time1':time1, 'tpw2':tpw2, 'time2':time2}).clip(image.geometry())

    # SMW coefficients are binned by TPW values
    # find the bin of each TPW value
    pos = tpw.expression(
        "value = (TPW>0 && TPW<=6) ? 0" + \
        ": (TPW>6 && TPW<=12) ? 1" + \
        ": (TPW>12 && TPW<=18) ? 2" + \
        ": (TPW>18 && TPW<=24) ? 3" + \
        ": (TPW>24 && TPW<=30) ? 4" + \
        ": (TPW>30 && TPW<=36) ? 5" + \
        ": (TPW>36 && TPW<=42) ? 6" + \
        ": (TPW>42 && TPW<=48) ? 7" + \
        ": (TPW>48 && TPW<=54) ? 8" + \
        ": (TPW>54) ? 9" + \
        ": 0",{'TPW': tpw}) \
        .clip(image.geometry()
        )

    # add tpw to image as a band
    withTPW = (image.addBands(tpw.rename('TPW'),['TPW'])).addBands(pos.rename('TPWpos'),['TPWpos'])
    return withTPW

# 4. Fraction of Vegetation Cover (FVC)
def addFVC(landsat):
  def wrap(image):  
    ndvi = image.select('NDVI')
    # Compute FVC
    fvc = image.expression('((ndvi-ndvi_bg)/(ndvi_vg - ndvi_bg))**2',
                           {'ndvi':ndvi,'ndvi_bg':0.2,'ndvi_vg':0.86}
                           )
    fvc = fvc.where(fvc.lt(0.0),0.0);
    fvc = fvc.where(fvc.gt(1.0),1.0);
    
    return image.addBands(fvc.rename('FVC'))
  return wrap

# 5. Surface Emissivity Calculation
# bare ground emissivity functions for each band
def add_emiss_bare_band10(image):
    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    aster_ndvi = aster.select('ndvi').multiply(0.01)
    aster_fvc = aster_ndvi.expression('((ndvi-ndvi_bg)/(ndvi_vg - ndvi_bg))**2', {'ndvi':aster_ndvi,'ndvi_bg':0.2,'ndvi_vg':0.86})
    aster_fvc = aster_fvc.where(aster_fvc.lt(0.0),0.0)
    aster_fvc = aster_fvc.where(aster_fvc.gt(1.0),1.0)
    
    return image.expression('(EM - 0.99*fvc)/(1.0-fvc)',{
    'EM':aster.select('emissivity_band10').multiply(0.001),
    'fvc':aster_fvc}).clip(image.geometry())

def add_emiss_bare_band11(image):
    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    aster_ndvi = aster.select('ndvi').multiply(0.01)
    aster_fvc = aster_ndvi.expression('((ndvi-ndvi_bg)/(ndvi_vg - ndvi_bg))**2', {'ndvi':aster_ndvi,'ndvi_bg':0.2,'ndvi_vg':0.86})
    aster_fvc = aster_fvc.where(aster_fvc.lt(0.0),0.0)
    aster_fvc = aster_fvc.where(aster_fvc.gt(1.0),1.0)  
    return image.expression('(EM - 0.99*fvc)/(1.0-fvc)',{
    'EM':aster.select('emissivity_band11').multiply(0.001),
    'fvc':aster_fvc}).clip(image.geometry())

def add_emiss_bare_band12(image):
    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    aster_ndvi = aster.select('ndvi').multiply(0.01)
    aster_fvc = aster_ndvi.expression('((ndvi-ndvi_bg)/(ndvi_vg - ndvi_bg))**2', {'ndvi':aster_ndvi,'ndvi_bg':0.2,'ndvi_vg':0.86})
    aster_fvc = aster_fvc.where(aster_fvc.lt(0.0),0.0)
    aster_fvc = aster_fvc.where(aster_fvc.gt(1.0),1.0)
    return image.expression('(EM - 0.99*fvc)/(1.0-fvc)',{
    'EM':aster.select('emissivity_band12').multiply(0.001),
    'fvc':aster_fvc}).clip(image.geometry())

def add_emiss_bare_band13(image):
    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    aster_ndvi = aster.select('ndvi').multiply(0.01)
    aster_fvc = aster_ndvi.expression('((ndvi-ndvi_bg)/(ndvi_vg - ndvi_bg))**2', {'ndvi':aster_ndvi,'ndvi_bg':0.2,'ndvi_vg':0.86})
    aster_fvc = aster_fvc.where(aster_fvc.lt(0.0),0.0)
    aster_fvc = aster_fvc.where(aster_fvc.gt(1.0),1.0)
    return image.expression('(EM - 0.99*fvc)/(1.0-fvc)',{
    'EM':aster.select('emissivity_band13').multiply(0.001),
    'fvc':aster_fvc}).clip(image.geometry())

def add_emiss_bare_band14(image):
    aster = ee.Image("NASA/ASTER_GED/AG100_003")
    aster_ndvi = aster.select('ndvi').multiply(0.01)
    aster_fvc = aster_ndvi.expression('((ndvi-ndvi_bg)/(ndvi_vg - ndvi_bg))**2', {'ndvi':aster_ndvi,'ndvi_bg':0.2,'ndvi_vg':0.86})
    aster_fvc = aster_fvc.where(aster_fvc.lt(0.0),0.0)
    aster_fvc = aster_fvc.where(aster_fvc.gt(1.0),1.0)
    return image.expression('(EM - 0.99*fvc)/(1.0-fvc)',{
    'EM':aster.select('emissivity_band14').multiply(0.001),
    'fvc':aster_fvc}).clip(image.geometry())


# this function computes the emissivity of the
# Landsat TIR band using ASTER and FVC
def addEM(landsat, use_ndvi):
  def wrap(image):
    c13 = ee.Number(ee.Algorithms.If(landsat=='L4',0.3222,
                            ee.Algorithms.If(landsat=='L5',-0.0723,
                            ee.Algorithms.If(landsat=='L7',0.2147,
                            0.6820))))
    c14 = ee.Number(ee.Algorithms.If(landsat=='L4',0.6498,
                            ee.Algorithms.If(landsat=='L5',1.0521,
                            ee.Algorithms.If(landsat=='L7',0.7789,
                            0.2578))))
    c = ee.Number(ee.Algorithms.If(landsat=='L4',0.0272,
                            ee.Algorithms.If(landsat=='L5',0.0195,
                            ee.Algorithms.If(landsat=='L7',0.0059,
                            0.0584))))
    # get ASTER emissivity
    # convolve to Landsat band
    emiss_bare = image.expression('c13*EM13 + c14*EM14 + c',{
      'EM13':add_emiss_bare_band13(image),
      'EM14':add_emiss_bare_band14(image),
      'c13':ee.Image(c13),
      'c14':ee.Image(c14),
      'c':ee.Image(c)
      })

    # compute the dynamic emissivity for Landsat
    EMd = image.expression('fvc*0.99+(1-fvc)*em_bare',
      {'fvc':image.select('FVC'),'em_bare':emiss_bare})

    # compute emissivity directly from ASTER
    # without vegetation correction
    # get ASTER emissivity
    aster = ee.Image("NASA/ASTER_GED/AG100_003") \
      .clip(image.geometry())
    EM0 = image.expression('c13*EM13 + c14*EM14 + c',{
      'EM13':aster.select('emissivity_band13').multiply(0.001),
      'EM14':aster.select('emissivity_band14').multiply(0.001),
      'c13':ee.Image(c13),
      'c14':ee.Image(c14),
      'c':ee.Image(c)
      })

    # select which emissivity to output based on user selection
    EM = ee.Image(ee.Algorithms.If(use_ndvi,EMd,EM0))

    return image.addBands(EM.rename('EM'))
  return wrap

# 6. SWM Algorithm for Calculating LST
# coefficients for the Statistical Mono-Window Algorithm
def coeff_SMW_L4():
    return ee.FeatureCollection([
    ee.Feature(None, {'TPWpos': 0, 'A': 0.9755, 'B': -205.2767, 'C': 212.0051}),
    ee.Feature(None, {'TPWpos': 1, 'A': 1.0155, 'B': -233.8902, 'C': 230.4049}),
    ee.Feature(None, {'TPWpos': 2, 'A': 1.0672, 'B': -257.1884, 'C': 239.3072}),
    ee.Feature(None, {'TPWpos': 3, 'A': 1.1499, 'B': -286.2166, 'C': 244.8497}),
    ee.Feature(None, {'TPWpos': 4, 'A': 1.2277, 'B': -316.7643, 'C': 253.0033}),
    ee.Feature(None, {'TPWpos': 5, 'A': 1.3649, 'B': -361.8276, 'C': 258.5471}),
    ee.Feature(None, {'TPWpos': 6, 'A': 1.5085, 'B': -410.1157, 'C': 265.1131}),
    ee.Feature(None, {'TPWpos': 7, 'A': 1.7045, 'B': -472.4909, 'C': 270.7000}),
    ee.Feature(None, {'TPWpos': 8, 'A': 1.5886, 'B': -442.9489, 'C': 277.1511}),
    ee.Feature(None, {'TPWpos': 9, 'A': 2.0215, 'B': -571.8563, 'C': 279.9854})
    ])

def coeff_SMW_L5():
    return ee.FeatureCollection([
    ee.Feature(None, {'TPWpos': 0, 'A': 0.9765, 'B': -204.6584, 'C': 211.1321}),
    ee.Feature(None, {'TPWpos': 1, 'A': 1.0229, 'B': -235.5384, 'C': 230.0619}),
    ee.Feature(None, {'TPWpos': 2, 'A': 1.0817, 'B': -261.3886, 'C': 239.5256}),
    ee.Feature(None, {'TPWpos': 3, 'A': 1.1738, 'B': -293.6128, 'C': 245.6042}),
    ee.Feature(None, {'TPWpos': 4, 'A': 1.2605, 'B': -327.1417, 'C': 254.2301}),
    ee.Feature(None, {'TPWpos': 5, 'A': 1.4166, 'B': -377.7741, 'C': 259.9711}),
    ee.Feature(None, {'TPWpos': 6, 'A': 1.5727, 'B': -430.0388, 'C': 266.9520}),
    ee.Feature(None, {'TPWpos': 7, 'A': 1.7879, 'B': -498.1947, 'C': 272.8413}),
    ee.Feature(None, {'TPWpos': 8, 'A': 1.6347, 'B': -457.8183, 'C': 279.6160}),
    ee.Feature(None, {'TPWpos': 9, 'A': 2.1168, 'B': -600.7079, 'C': 282.4583})
    ])

def coeff_SMW_L7():
    return ee.FeatureCollection([
    ee.Feature(None, {'TPWpos': 0, 'A': 0.9764, 'B': -205.3511, 'C': 211.8507}),
    ee.Feature(None, {'TPWpos': 1, 'A': 1.0201, 'B': -235.2416, 'C': 230.5468}),
    ee.Feature(None, {'TPWpos': 2, 'A': 1.0750, 'B': -259.6560, 'C': 239.6619}),
    ee.Feature(None, {'TPWpos': 3, 'A': 1.1612, 'B': -289.8190, 'C': 245.3286}),
    ee.Feature(None, {'TPWpos': 4, 'A': 1.2425, 'B': -321.4658, 'C': 253.6144}),
    ee.Feature(None, {'TPWpos': 5, 'A': 1.3864, 'B': -368.4078, 'C': 259.1390}),
    ee.Feature(None, {'TPWpos': 6, 'A': 1.5336, 'B': -417.7796, 'C': 265.7486}),
    ee.Feature(None, {'TPWpos': 7, 'A': 1.7345, 'B': -481.5714, 'C': 271.3659}),
    ee.Feature(None, {'TPWpos': 8, 'A': 1.6066, 'B': -448.5071, 'C': 277.9058}),
    ee.Feature(None, {'TPWpos': 9, 'A': 2.0533, 'B': -581.2619, 'C': 280.6800})
    ])

def coeff_SMW_L8():
    return ee.FeatureCollection([
    ee.Feature(None, {'TPWpos': 0, 'A': 0.9751, 'B': -205.8929, 'C': 212.7173}),
    ee.Feature(None, {'TPWpos': 1, 'A': 1.0090, 'B': -232.2750, 'C': 230.5698}),
    ee.Feature(None, {'TPWpos': 2, 'A': 1.0541, 'B': -253.1943, 'C': 238.9548}),
    ee.Feature(None, {'TPWpos': 3, 'A': 1.1282, 'B': -279.4212, 'C': 244.0772}),
    ee.Feature(None, {'TPWpos': 4, 'A': 1.1987, 'B': -307.4497, 'C': 251.8341}),
    ee.Feature(None, {'TPWpos': 5, 'A': 1.3205, 'B': -348.0228, 'C': 257.2740}),
    ee.Feature(None, {'TPWpos': 6, 'A': 1.4540, 'B': -393.1718, 'C': 263.5599}),
    ee.Feature(None, {'TPWpos': 7, 'A': 1.6350, 'B': -451.0790, 'C': 268.9405}),
    ee.Feature(None, {'TPWpos': 8, 'A': 1.5468, 'B': -429.5095, 'C': 275.0895}),
    ee.Feature(None, {'TPWpos': 9, 'A': 1.9403, 'B': -547.2681, 'C': 277.9953})
    ])

# Function to create a lookup between two columns in a
# feature collection
def get_lookup_table(fc, prop_1, prop_2):
  reducer = ee.Reducer.toList().repeat(2)
  lookup = fc.reduceColumns(reducer, [prop_1, prop_2])
  return ee.List(lookup.get('list'))

def addLST(landsat):
  def wrap(image):
    # Select algorithm coefficients
    coeff_SMW = ee.FeatureCollection(ee.Algorithms.If(landsat=='Landsat 4',coeff_SMW_L4(),
                                        ee.Algorithms.If(landsat=='Landsat 5',coeff_SMW_L5(),
                                        ee.Algorithms.If(landsat=='Landsat 7',coeff_SMW_L7(),
                                        coeff_SMW_L8()))))

    # Create lookups for the algorithm coefficients
    A_lookup = get_lookup_table(coeff_SMW, 'TPWpos', 'A')
    B_lookup = get_lookup_table(coeff_SMW, 'TPWpos', 'B')
    C_lookup = get_lookup_table(coeff_SMW, 'TPWpos', 'C')

    # Map coefficients to the image using the TPW bin position
    A_img = image.remap(A_lookup.get(0), A_lookup.get(1),0.0,'TPWpos').resample('bilinear')
    B_img = image.remap(B_lookup.get(0), B_lookup.get(1),0.0,'TPWpos').resample('bilinear')
    C_img = image.remap(C_lookup.get(0), C_lookup.get(1),0.0,'TPWpos').resample('bilinear')

    # select TIR band
    tir = ee.String(ee.Algorithms.If(landsat=='Landsat 8','B10',
                        ee.Algorithms.If(landsat=='Landsat 7','B6_VCID_1',
                        'B6')))
    # compute the LST
    lst = image.expression(
      'A*Tb1/em1 + B/em1 + C',
         {'A': A_img,
          'B': B_img,
          'C': C_img,
          'em1': image.select('EM'),
          'Tb1': image.select(tir)
         }).updateMask(image.select('TPW').lt(0).Not())
    return image.addBands(lst.rename('LST'))
  return wrap

def getLSTCollection(landsat, date_start, date_end, geometry, use_ndvi):
    
    COLLECTION = ee.Dictionary({
        'Landsat 4': {
        'TOA': ee.ImageCollection('LANDSAT/LT04/C01/T1_TOA'),
        'SR': ee.ImageCollection('LANDSAT/LT04/C01/T1_SR'),
        'TIR': ['B6',]
        },
        'Landsat 5': {
            'TOA': ee.ImageCollection('LANDSAT/LT05/C01/T1_TOA'),
            'SR': ee.ImageCollection('LANDSAT/LT05/C01/T1_SR'),
            'TIR': ['B6',]
        },
        'Landsat 7': {
            'TOA': ee.ImageCollection('LANDSAT/LE07/C01/T1_TOA'),
            'SR': ee.ImageCollection('LANDSAT/LE07/C01/T1_SR'),
            'TIR': ['B6_VCID_1','B6_VCID_2'],
        },
        'Landsat 8': {
            'TOA': ee.ImageCollection('LANDSAT/LC08/C01/T1_TOA'),
            'SR': ee.ImageCollection('LANDSAT/LC08/C01/T1_SR'),
            'TIR': ['B10','B11']
        }
    })

    # load TOA Radiance/Reflectance
    collection_dict = ee.Dictionary(COLLECTION.get(landsat))

    landsatTOA = ee.ImageCollection(collection_dict.get('TOA')) \
                    .filter(ee.Filter.date(date_start, date_end)) \
                    .filterBounds(geometry) \
                    .map(maskL8toaClouds)

    # load Surface Reflectance collection for NDVI
    landsatSR = ee.ImageCollection(collection_dict.get('SR')) \
                    .filter(ee.Filter.date(date_start, date_end)) \
                    .filterBounds(geometry) \
                    .map(maskL8srClouds) \
                    .map(addNDVI(landsat)) \
                    .map(addFVC(landsat)) \
                    .map(addTPWBands) \
                    .map(addEM(landsat,use_ndvi))

    # combine collections
    # all channels from surface reflectance collection
    # except tir channels: from TOA collection
    # select TIR bands
    tir = ee.List(collection_dict.get('TIR'))
    landsatALL = (landsatSR.combine(landsatTOA.select(tir),True))

    # compute the LST
    landsatLST = landsatALL.map(addLST(landsat))
    return landsatLST
################################################################################
############## END of SMW LST ALGORITHM ########################################

def showLST(mapObject, state): 
    # Get Parameters from State
    satellite = state.satellite
    start = str(state.fromDate)
    end = str(state.toDate)
    aoi = state.aoi
    useNDVI = state.useNDVI
    
    LandsatColl = getLSTCollection(satellite, start, end, aoi, useNDVI)
    # Covert Landsat LST Image Collection to Image 
    exImage = LandsatColl.qualityMosaic('LST')
    # Define Colormap for Visualization
    cmap1 = ['blue', 'cyan', 'green', 'yellow', 'red']
    
    lst_img = exImage.select('LST').clip(aoi)
    
    lst_min = gmap.image_stats(exImage, aoi, scale=1000).getInfo()['min']['LST']
    lst_max = gmap.image_stats(exImage, aoi, scale=1000).getInfo()['max']['LST']
    lst_std = gmap.image_stats(exImage, aoi, scale=1000).getInfo()['std']['LST']
    mapObject.addLayer(exImage.multiply(0.0001).clip(aoi),{'bands': ['B4',  'B3',  'B2'], 'min':0, 'max':0.3}, 'Natural Color RGB')
    mapObject.addLayer(lst_img,{'min':lst_min- 2.5*lst_std, 'max':lst_max, 'palette':cmap1}, 'LST')
    
    vmin = (lst_min- 2.5*lst_std) - 273.15
    vmax = lst_max - 273.15
    caption = 'Land Surface Temperature (Celsius)'
    
    mapObject.add_colorbar(colors=cmap1, vmin=vmin, vmax=round(vmax, 2), caption=caption)