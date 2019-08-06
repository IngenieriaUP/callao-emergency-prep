# Import dependencies
import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import osmnx as ox
import requests
import time
import googlemaps
from tqdm import tqdm
from shapely.geometry import LineString, Point, MultiPolygon, Polygon
from warnings import filterwarnings

filterwarnings('ignore')

# Coordinate system
proj_utm = {'datum': 'WGS84', 'ellps': 'WGS84', 'proj': 'utm', 'zone': 18, 'units': 'm'}

# Datasets
map_data = pd.read_csv('data/input/PuntosyCentros V5.csv', encoding='latin-1')
# Convert DataFrame to GeoDataFrame using lon lat columns
map_data = gpd.GeoDataFrame(
    data=map_data,
    crs={'init': 'epsg:4326'},
    geometry=[Point(xy) for xy in zip(map_data['LONGITUDE'], map_data['LATITUDE'])]
    )
# Project crs to UTM (meters)
map_data = map_data.to_crs(proj_utm)

print("Loading graph")
init = time.time()
graph = ox.load_graphml('input/callao_drive_network.graphml')
wait = time.time() - init
print("graph loaded in", wait)

print("Loading nodes")
init = time.time()
nodes = ox.graph_to_gdfs(graph, nodes=True, edges=False)
wait = time.time() - init
print("nodes loaded in", wait)
print('#'*40)
print('n_nodes:',len(nodes))
print('#'*40)

#### Obtain route from graph ####

## Helpers

def get_boundingbox(x, y, margin):
    x = x.geometry
    y = y.geometry
    xy = gpd.GeoDataFrame(geometry=[x, y], crs=proj_utm)
    xmin, ymin, xmax, ymax = xy.unary_union.bounds
    xmin -= margin
    ymin -= margin
    xmax += margin
    ymax += margin
    return xmin, ymin, xmax, ymax

def get_subgraph(graph, nodes, source, target, margin):
    xmin, ymin, xmax, ymax = get_boundingbox(source, target, margin=margin)
    subgraph_nodes_ix = nodes.cx[xmin:xmax, ymin:ymax].index

    init = time.time()
    subgraph = graph.subgraph(subgraph_nodes_ix)
    wait = time.time() - init

    return subgraph, subgraph_nodes_ix

def get_nearest_nodes(graph, source, target):

    init = time.time()
    origin_node = ox.get_nearest_node(G=graph, point=(source.geometry.y, source.geometry.x), method='euclidean')
    target_node = ox.get_nearest_node(G=graph, point=(target.geometry.y, target.geometry.x), method='euclidean')
    wait = time.time() - init

    return origin_node, target_node

def get_route_length(route, nodes, source, target):
    route_nodes = nodes.loc[route]
    route_line = route_nodes.geometry.values.tolist()
    route_line.insert(0, source.geometry)
    route_line.append(target.geometry)
    route_linestr = LineString(route_line)

    route_geom = gpd.GeoDataFrame(crs=nodes.crs)
    route_geom['geometry'] = None
    route_geom['osmids'] = None
    route_geom.loc[0,'geometry'] = route_linestr
    route_geom.loc[0,'osmids'] = str(list(route_nodes['osmid'].values))
    route_geom['length_m'] = route_geom.length

    return route_geom, route_geom.length

## Main function

def get_scattermap_lines(source, target, margin):
    '''
    source: GeoPandas GeoSeries with Point geometry
    target: GeoPandas GeoSeries with Point geometry
    margin: value in meters to expand a bounding box
    '''
    # Filter graph to reduce time
    subgraph, subgraph_nodes_ix = get_subgraph(graph, nodes, source, target, margin)
    # Get nearest nodes in the subgraph
    source_node_id, target_node_id = get_nearest_nodes(subgraph, source, target)
    try:
        # Get shortest_path (list of nodes)
        init = time.time()
        opt_route = nx.shortest_path(G=subgraph, source=source_node_id,
                                     target=target_node_id, weight='length')
        wait = time.time() - init

        # Get route data
        route_geom, route_lenght = get_route_length(opt_route, nodes, source, target)

        return route_lenght
    except:
        return 99999999999

if __name__ == '__main__':
    route_lenghts = np.zeros(shape=(map_data.shape[0], map_data.shape[0]))

    for i, source in tqdm(map_data.iterrows(), total=map_data.shape[0]):
        for j, target in map_data.iterrows():
            if i < j:
                # Obtain route lenght from graph
                try:
                    route_lenght = get_scattermap_lines(
                        source = map_data.iloc[i,:],
                        target = map_data.iloc[j,:],
                        margin = 1000)
                    route_lenghts[i,j] = route_lenght
                except:
                    route_lenghts[i,j] = -99999

                if i*j % 100 == 0:
                    np.savetxt('data/output/route_lenghts.csv', route_lenghts, delimiter=',')
            else:
                pass


# Sample code for using mapbox and google APIs
# # API keys
# mapbox_access_token = ""
# gmaps = googlemaps.Client(key='')

# ###################################
#
# #### Obtain route from external API ####
#
# def ldict2ltup(d):
#     #maps a list of dictionaries to a list of tuples
#     return (d['lat'],d['lng'])
#
# def llist2ltup(d):
#     #maps a list of coordinate lists to a list of tuples
#     return (d[1],d[0])
#
# def get_directions_mapbox(source, target, profile):
#     # Mapbox driving direction API call
#     source_str = "{},{}".format(source[1],source[0])
#     target_str = "{},{}".format(target[1],target[0])
#     coords = ";".join([source_str,target_str])
#     ROUTE_URL = "https://api.mapbox.com/directions/v5/mapbox/" + profile + "/" + str(source[1]) + "," + str(source[0]) + ";" + str(target[1]) + "," + str(target[0]) + "?geometries=geojson&access_token=" + mapbox_access_token
#     result = requests.get(ROUTE_URL)
#     data = result.json()
#     route_data = data["routes"][0]["geometry"]["coordinates"]
#     return list(map(llist2ltup,route_data))
#
# def get_directions_google(gmaps, origin, destination):
#     dirs = gmaps.directions(origin=origin, destination=destination)
#     overview_polyline = dirs[0].get('overview_polyline')
#     if overview_polyline is not None:
#         route_decoded = googlemaps.convert.decode_polyline(overview_polyline['points'])
#     else:
#         pass
#
#     return list(map(ldict2ltup,route_decoded))
#
# ########################################
#route_line = get_directions_google(gmaps, source, target) # Obtain route from google maps API
#route_line = get_directions_mapbox(source, target, profile=profile) # Obtain route from mapbox API
