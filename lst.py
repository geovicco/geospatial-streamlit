import streamlit as st
st.set_page_config(page_title='Land Surface Temperature', layout='wide')
import geemap.foliumap as geemap
import utilities as ut
        
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

ut.initialize_sessionState()

with row1_col1:
    # INITIALIZE MAP
    m = geemap.Map(plugin_Draw=False, add_google_map=False)
    m.add_basemap("HYBRID")

    with row1_col2:
        # GEOCODER - SEARCH LOCATION
        ut.add_geocoder(mapObject=m)

        # AOI SELECTION
        ut.add_aoi_selector(mapObject=m)

        if st.session_state.aoi is "":
            st.info("Select AOI to Proceed")
        else:
            # # SET PROCESSING PARAMETERS  
            sessionState = ut.set_params()      
            
            # If the user has submitted the processing form, then run the algorithm
            if sessionState['FormSubmitter:processing-params-Submit']:
                try:
                    # Run Algorithm
                    ut.showLST(mapObject=m, state=sessionState)
                except KeyError:
                    st.warning("LST could not be computed. Try again with different settings!")
            else:
                st.info("Set Processing Options to Proceed")
            
    m.to_streamlit(height=700, width=1000)
