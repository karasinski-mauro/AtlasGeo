import os
import fiona
import geobr
import pandas as pd
import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import matplotlib.pyplot as plt
from matplotlib_scalebar.scalebar import ScaleBar
from matplotlib.ticker import ScalarFormatter
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from io import BytesIO
import base64
import contextily as ctx
import mplleaflet

fiona.drvsupport.supported_drivers['kml'] = 'rw' # enable KML support which is disabled by default
fiona.drvsupport.supported_drivers['KML'] = 'rw' # enable KML support which is disabled by default


def load_municipality_data():
    return geobr.read_municipality(code_muni='all', year=2020)

def load_state_data():
    return geobr.read_state(code_state='all', year=2020)

def read_kml(file):
    gdf = kml_to_gdf(file)
    return gdf

def kml_to_gdf(kml_file):
    with fiona.Env():
        with fiona.open(kml_file, 'r', driver='kml') as src:

            gdf = gpd.GeoDataFrame.from_features(src)
    return gdf 

def show_folium_map(gdf):
    m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=12)

    for index, row in gdf.iterrows():
        folium.GeoJson(row['geometry'].__geo_interface__, name=row['Name']).add_to(m)
    

    return m

def generate_plot_folium(gdf):
    m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=12)

    # Adicionar camada do OpenStreetMap
    folium.TileLayer('openstreetmap').add_to(m)

    # Adicionar GeoJson após a camada do OpenStreetMap
    for index, row in gdf.iterrows():
        folium.GeoJson(row['geometry'].__geo_interface__, name=row['Name']).add_to(m)

    return m


def generate_plot(data_gdf, brasil, estado, municipio, margin=0.2):
    # Criar a figura Matplotlib
    fig, ax = plt.subplots(figsize=(12, 8))

    fig.subplots_adjust(right=1.11)
        
    # Adicionar o GeoDataFrame ao gráfico Matplotlib
    data_gdf.plot(ax=ax, alpha=0.6, cmap='YlGn', edgecolor='black',legend=True)

    ax.xaxis.set_tick_params(rotation=0)
    ax.yaxis.set_tick_params(rotation=90)
    ax.set_xticks(ax.get_xticks())
    ax.y_formatter = ScalarFormatter()
    ax.y_formatter.set_scientific(False)
    ax.yaxis.set_major_formatter(ax.y_formatter)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position('right')
    ax.grid(color='gray', linestyle='--', linewidth=0.5)
    
    
        # Adicionar o mapa OpenStreetMap como um fundo usando mplleaflet
    try:
        ctx.add_basemap(ax, crs='EPSG:4326', source=ctx.providers.OpenStreetMap.Mapnik)
    except TypeError:
        # Se o CRS não estiver definido no GeoDataFrame, use CRS 4326 (WGS84)
        ctx.add_basemap(ax, crs='EPSG:4326', source=ctx.providers.OpenStreetMap.Mapnik)
    


    # mapa 2 ----------------------------------
    ax_brasil = fig.add_axes([0.01, 0.52, 0.35, 0.35])
    brasil.plot(ax=ax_brasil)

    # Destacar o estado de interesse no mapa do Brasil
    intersected_estado = gpd.overlay(estado, brasil, how='intersection')
    intersected_estado.plot(ax=ax_brasil, color='yellow', edgecolor='gray', linewidth=2)

    ax_brasil.set_xticks([])
    ax_brasil.set_yticks([])
    ax_brasil.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False)
    
    # Mostrar os municípios dentro do estado de interesse
    municipios_interior_estado = gpd.overlay(estado, municipio, how='intersection')
    municipios_interior_estado.plot(ax=ax_brasil, color='red', alpha=0.7, edgecolor='black', linewidth=0.2)
    
    # Calcular a caixa delimitadora com margem
    bbox = municipios_interior_estado.total_bounds
    bbox_margin = [
        bbox[0] - margin * (bbox[2] - bbox[0]),
        bbox[1] - margin * (bbox[3] - bbox[1]),
        bbox[2] + margin * (bbox[2] - bbox[0]),
        bbox[3] + margin * (bbox[3] - bbox[1])
    ]

    # Adicionar um retângulo envolvente sobre o município de interesse
    rect = plt.Rectangle((bbox_margin[0], bbox_margin[1]), bbox_margin[2] - bbox_margin[0], bbox_margin[3] - bbox_margin[1],
                         linewidth=2, edgecolor='lightpink', facecolor='none')
    ax_brasil.add_patch(rect)

    
    # mapa 3 -----------------------------------------------------------------
    ax_estado = fig.add_axes([0.01, 0.15, 0.3, 0.3])
    estado.plot(ax=ax_estado, color='lightgray', edgecolor='black', linewidth=0.5)

    ax_estado.set_xticks([])
    ax_estado.set_yticks([])
    ax_estado.tick_params(axis='both', which='both', bottom=False, top=False, left=False, right=False)
    
    # Recortar todos os municípios do Brasil pelo estado de interesse
    municipios_estado = gpd.clip(municipio, estado)

    # Mostrar os limites de todos os municípios dentro do estado
    municipios_estado.plot(ax=ax_estado, color='lightgray', alpha=0.7, edgecolor='black', linewidth=0.5)

       # Calcular a caixa delimitadora com margem
    bbox = municipios_interior_estado.total_bounds
    bbox_margin = [
        bbox[0] - margin * (bbox[2] - bbox[0]),
        bbox[1] - margin * (bbox[3] - bbox[1]),
        bbox[2] + margin * (bbox[2] - bbox[0]),
        bbox[3] + margin * (bbox[3] - bbox[1])
    ]

    # Adicionar um retângulo envolvente sobre o município de interesse
    rect = plt.Rectangle((bbox_margin[0], bbox_margin[1]), bbox_margin[2] - bbox_margin[0], bbox_margin[3] - bbox_margin[1],
                         linewidth=0.5, edgecolor='red', alpha= 0.5, facecolor='pink')
    ax_estado.add_patch(rect)


    


    ax.tick_params(axis='both', labelsize=6)
    yticks = ax.get_yticks()[2:]  # Pule a primeira escala
    ax.set_yticks(yticks)

    # Adicionar a escala
    def add_scalebar(ax):
        # Calcular a extensão geográfica real no eixo x
        x_min, x_max = ax.get_xlim()
        real_distance = x_max - x_min  # Assumindo que os dados estão em um CRS em metros

        # Configurar o comprimento da escala (por exemplo, 10 km)
        scale_length_km = 100

        # Calcular o fator de conversão
        conversion_factor = scale_length_km / real_distance

        # Configurar a escala com base no comprimento real
        scale_length_real = real_distance * conversion_factor
        scalebar = ScaleBar(scale_length_real, location='lower right', units='km', length_fraction=0.1, scale_loc='bottom', border_pad=0.1)

        # Configurar outras propriedades da escala
        scalebar.box_alpha = 0.5
        scalebar.font_properties = {'weight': 'bold'}
        scalebar.label_x_offset = 0.1
        scalebar.label_y_offset = -0.1
        scalebar.height_fraction = 0.01
        scalebar.location = 'lower right'
        scalebar.scale_loc = 'bottom'
        scalebar.font_properties = {'size': 'small'}
        scalebar.width = 0.01
        scalebar.line_color = 'black'
        scalebar.line_style = 'solid'

        # Adicionar a escala ao eixo
        ax.add_artist(scalebar)

    # Chame a função add_scalebar antes de plt.show()
    add_scalebar(ax)
    
    
    plt.show()

    # Retornar o gráfico
    return plt



def get_image_download_link(plot):
    # Salvar a figura em um buffer de bytes
    image_stream = BytesIO()
    plot.savefig(image_stream, format='png')
    image_stream.seek(0)

    # Codificar a figura em base64
    image_base64 = base64.b64encode(image_stream.read()).decode('utf-8')

    # Gerar o link de download
    download_link = f'<a href="data:file/png;base64,{image_base64}" download="plot.png">Clique aqui para baixar</a>'

    return download_link




def main():
    st.set_page_config(
        page_title="AtlasGeo Technology",
        page_icon=":earth_africa:",
        layout="wide"
    )

    st.header('Bem-vindo à AtlasGeo Technology!')
    st.markdown("""----""")
    st.text('Descubra uma nova era em cartografia digital e experimente a inovação em geração de mapas automatizados com o toque distinto da tecnologia.\nEmbarque conosco em uma jornada única e descubra como a fusão da geotecnologia de ponta com a inspiração do mito grego de Atlas\npode transformar a maneira como você percebe o mundo.')

    uploaded_file = st.file_uploader("Escolha um arquivo", type=["shp", "kml"])

    if uploaded_file is not None:
        try:
            file_extension = os.path.splitext(uploaded_file.name)[1].lower()

            if file_extension == ".kml":
                gdf = read_kml(uploaded_file)

            elif file_extension == ".shp":
                gdf = gpd.read_file(uploaded_file, driver='ESRI Shapefile')
            else:
                st.error("Formato de arquivo não suportado. Por favor, escolha um arquivo KML ou SHP.")
                return

            st.write("### Pré-Visualização:")
            
            # Mostrar o mapa usando folium
            folium_map = generate_plot_folium(gdf)
            folium_static(folium_map)

            # Não há necessidade de manipular o CRS aqui
            brasil = load_municipality_data()
            estado = load_state_data()
            estado_intersectado = estado[estado.intersects(gdf.unary_union)]
            municipio = brasil[brasil.intersects(gdf.unary_union)]

            # Gerar o gráfico Matplotlib
            plot = generate_plot(gdf, brasil, estado_intersectado, municipio)
            # Exibir a figura no Streamlit
            st.pyplot(plot)

            # Adicionar o link de download
            download_link = get_image_download_link(plot)
            st.markdown(download_link, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Erro ao processar o arquivo: {e}")

if __name__ == "__main__":
    main()
    
