import warnings

import streamlit as st
from streamlit_dimensions import st_dimensions

def get_plot_width(key):
    wobj = st_dimensions(key=key) or { 'width': 400 }# Can return none so handle that
    return int(0.85*wobj['width']) # Needs to be adjusted to leave margin

def get_width():
    w = max(get_plot_width('full'), 800)
    return w

warnings.simplefilter(action='ignore', category=FutureWarning)

profile = False
if profile:
    from streamlit_profiler import Profiler
    p = Profiler(); p.start()

st.set_page_config(
    layout="wide",
    page_title="btracer",
    initial_sidebar_state="expanded",
)

info = st.empty()

with st.spinner("Loading libraries.."):
    import os, re, sys

    import altair as alt
    import arviz as az
    import pandas as pd
    import xarray as xr
    import btracer

    # Disable altair schema validations by setting debug_mode = False
    # This speeds plots up considerably as altair performs an excessive amount of these validation for some reason
    dm = alt.utils.schemapi.debug_mode(False); dm.__enter__()

# Turn off annoying warnings
warnings.filterwarnings(action='ignore', category=UserWarning)
warnings.filterwarnings(action='ignore', category=pd.errors.PerformanceWarning)

########################################################################
#                                                                      #
#                           Plot types                                 #
#                                                                      #
########################################################################

def plot_diagnostics(idata):
    var_names = list(idata.posterior.data_vars)
    selected_var_names = st.sidebar.multiselect('Variables:', var_names, default=var_names[:10])

    width = get_width()
    plot_properties = {'height': width / 4, 'width': width / 2}

    return btracer.plot_diagnostics(idata, var_names=selected_var_names, properties=plot_properties)

def plot_summary(idata):
    var_names = list(idata.posterior.data_vars)
    plot_properties = {'width': get_width()}

    agg_func_name = st.sidebar.selectbox('Aggregation function:', btracer.SUMMARY_FUNCTIONS.keys())
    selected_var_name = st.sidebar.selectbox('Variable:', var_names, index=None)

    if not selected_var_name:
        st.markdown("""Please choose a variable from the sidebar""")
        st.stop()

    var_dims = list(idata.posterior[selected_var_name].dims)
    base_dims = st.sidebar.multiselect('Base dimensions:', var_dims, default=[dim for dim in var_dims if dim in ['chain', 'draw']])

    other_dims = [dim for dim in var_dims if not dim in base_dims]

    selected_dim1 = st.sidebar.selectbox('Dimension 1 (horizontal):', other_dims)
    selected_dim2 = st.sidebar.selectbox('Dimension 2 (vertical):', [dim for dim in other_dims if dim != selected_dim1])

    if not selected_dim1 or not selected_dim2:
        st.markdown("""Please choose dimensions from the sidebar or another variable if no dimensions are available""")
        st.stop()

    return btracer.plot_summary(
        idata.posterior[selected_var_name],
        selected_dim1,
        selected_dim2,
        agg_func_name=agg_func_name,
        base_dims=base_dims,
        properties=plot_properties
    )

plot_types = {
    'diagnostics': plot_diagnostics,
    'summary': plot_summary,
}

########################################################################
#                                                                      #
#                      Choose & Load inputs                            #
#                                                                      #
########################################################################

def parse_input_path(input_path):
    if os.path.isdir(input_path):
        paths = sorted([os.path.join(input_path, f) for f in os.listdir(input_path) if f[-3:] == '.nc'])
        return {os.path.basename(p): p for p in paths}
    elif os.path.isfile(input_path):
        return {os.path.basename(input_path): input_path}
    else:
        return {}

input_paths = ['.'] if len(sys.argv) < 2 else sys.argv[1:]

input_file_choices = {}
for input_path in input_paths:
    input_file_choices.update(parse_input_path(input_path))

if not input_file_choices:
    st.markdown("""No input files found. Please specify one or more paths with model trace files when executing `streamlit run btracer.py <path>`.""")
    st.stop()

input_file_name = st.sidebar.selectbox('Input file:', input_file_choices.keys(), index=None)

@st.cache_resource(show_spinner=False)
def load_idata_file(input_file):
    return az.from_netcdf(input_file)

def clean_var_names(data: xr.Dataset):
    return data.rename({name: re.sub(r'[()[\]{} \'"]', '', name) for name in list(data.data_vars)})

plot = None

if not input_file_name:
    st.markdown("""Please choose an input file from the sidebar""")
    st.stop()
else:
    idata = load_idata_file(input_file_choices[input_file_name])
    idata.posterior = clean_var_names(idata.posterior)

    f_info = st.sidebar.empty()
    st.sidebar.markdown("""___""")
    plot_type = st.sidebar.selectbox('Plot:', plot_types.keys())
    st.sidebar.markdown("""___""")
    plot = plot_types[plot_type](idata)

if plot is not None:
    st.altair_chart(plot)

info.empty()

dm.__exit__(None, None, None)

if profile:
    p.stop()
