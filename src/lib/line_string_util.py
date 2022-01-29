import geopandas as gpd
from shapely.geometry import LineString
from shapely.geometry import Point

CRS_LATLON = 'EPSG:4326'

def cut(line, distance):
    """Splits the given LineString at the point at the given distance
    from the line starting point."""
    
    # Credit: From Shapely User Manual.
    
    # Return copy of line if distance will not segment it.
    if distance <= 0.0 or distance >= line.length:
        return [LineString(line)]
    
    coords = list(line.coords)
    
    # Iterate through each coordinate in LineString.
    for i, coord in enumerate(coords):
        coord_distance = line.project(Point(coord))
        
        # The desired distance is exactly at this coordinate; segment here.
        if coord_distance == distance:
            return [LineString(coords[:i + 1]), LineString(coords[i:])]
        
        # The desired distance is at a point between this coordinate and the
        # last one. Create a new coordinate at the desired distance then
        # segment there.
        if coord_distance > distance:
            split_point = line.interpolate(distance)
            
            return [
                LineString(coords[:i] + [(split_point.x, split_point.y)]),
                LineString([(split_point.x, split_point.y)] + coords[i:])
            ]

def segment_by_distances(line, distances=[], values=[]):
    """Splits the given LineString at the sequence of points formed from
    the sequence of distance values between each point. Attaches the
    given sequential values to the start and end points of
    each LineString segments. Returns a GeoDataFrame with each LineString
    geometry and values."""
    segments = []
    start_values = []
    end_values = []
    
    current_line = LineString(line)
    
    # Iterate through distance points. For each distance point, split off
    # a LineString segment and attach values.
    for i in range(1, len(distances)):
        # TODO(cpcarey): Use accurate distance calculation.
        # Approximation of meters to degrees.
        segment_distance = distances[i] / (0.11 / 0.000001)

        # Split LineString at next distance point. Add first segment to
        # GeoDataFrame of segments. Set second segment as LineString to
        # continue segmenting.
        split_segments = cut(current_line, segment_distance)
        segments.append(split_segments[0])
        if len(split_segments) == 2:
            current_line = split_segments[1]
            
        # Attach values.
        if len(values) == len(distances):
            start_values.append(values[i - 1])
            end_values.append(values[i])
        
    # Attach final remaining segment and values.
    segments.append(current_line)
    start_values.append(values[-1])
    end_values.append(values[-1])
    
    data = {'start_value': start_values, 'end_value': end_values}
    segments_gdf = gpd.GeoDataFrame(data=data, geometry=segments, crs=CRS_LATLON)
    return segments_gdf