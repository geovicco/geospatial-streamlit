import streamlit as st
st.set_page_config(page_title='Land Surface Temperature', layout='wide')
import ee
import geemap.foliumap as geemap
import geemap as gmap
import folium
import geopandas as gpd
from datetime import date, timedelta

def initialize_sessionState():
    if st.session_state.get("zoom_level") is None:
        st.session_state["zoom_level"] = 3
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
        fromDate = form.date_input('Start Date', date.today() - timedelta(days=3))
        toDate = form.date_input('End Date', date.today()-timedelta(days=1))
        useNDVI = form.checkbox("Use NDVI", False)
        satellite = form.radio("", [
                "Landsat 4",
                "Landsat 5",
                "Landsat 7",
                "Landsat 8"
            ], index=3)     
                   
        # Date Validation Check
        if toDate - fromDate < timedelta(days=1):
            st.error('Incorrect End Date! Try Again')
            st.stop()
        else:
            submit = form.form_submit_button('Submit')

        if submit:
            st.session_state['fromDate'] = fromDate
            st.session_state["toDate"] = toDate
            st.session_state["useNDVI"] = useNDVI
            st.session_state['satellite'] = satellite
            
        return st.session_state
    
####### MAIN APPLICATION #######

c1, c2, c3 = st.columns([1,8,1]); c2.title('  Land Surface Temperature Explorer')
c1, c2, c3 = st.columns([1,8,1]); 
c2.markdown(
        """
        An interactive web app that estimates Land Surface Temperature (LST) using [Landsat](https://developers.google.com/earth-engine/datasets/catalog/landsat) satellite data. LST is derived using the Single Mono Window (SMW) Algorithm ([Ermida et al., 2020](https://doi.org/10.3390/rs12091471)).

        The app was built using [streamlit](https://streamlit.io), [geemap](https://geemap.org), and [Google Earth Engine](https://earthengine.google.com). 
    """
    )

row1_col1, row1_col2 = st.columns([2, 1])

initialize_sessionState()


with row1_col1:
    # INITIALIZE MAP
    # m = leafmap.Map(height="400px", width="800px)
    m = geemap.Map(plugin_Draw=True, draw_export=True)
    m.setCenter(76,22, 5)
    # m.add_basemap("SATELLITE")

    with row1_col2:
        # GEOCODER - SEARCH LOCATION
        add_geocoder(mapObject=m)

        # AOI SELECTION
        add_aoi_selector(mapObject=m)

        if st.session_state.aoi == "Not Selected":
            st.info("Select AOI to Proceed")
        else:
            # # SET PROCESSING PARAMETERS  
            sessionState = set_params()      
            
            # If the user has submitted the processing form, then run the algorithm
            if sessionState['FormSubmitter:processing-params-Submit']:
                # Run Algorithm
                # showLST(mapObject=m, state=sessionState)
                st.write("Running LST SMW Algorithm")
            else:
                st.info("Define Processing Paramaters to Proceed")        
    print(st.session_state)
    m.to_streamlit(height=600, width=1000)
    # 1440p monitor # (height=900, width=1350)