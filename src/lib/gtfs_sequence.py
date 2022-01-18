from collections import Counter
from shapely.geometry import Point

def get_stop_coord(stops_df, stop_id):
    """Returns the lon/lat Point for the stop with the given ID using the provided
    GTFS stops DataFrame."""
    row = stops_df.loc[stop_id]
    return Point(row['stop_lon'], row['stop_lat'])


def most_common(list):
    """Returns the most common value in the given list."""
    counts = Counter(list)
    return counts.most_common(1)[0][0]


def snap_coord(coord, geometry):
    """Returns a Point on the given Geometry of the closest position to the given coordinate."""
    return geometry.interpolate(geometry.project(coord))


class Sequence:

    def __init__(self, stop_ids=[], trip_ids=[], trips_df=None, load_dict=None):
        # Create sequence instance loaded from dictionary representation.
        if load_dict:
            self.direction_id = load_dict['direction_id']
            self.route_id = load_dict['route_id']
            self.service_id = load_dict['service_id']
            self.shape_id = load_dict['shape_id']
            self.stop_ids = load_dict['stop_ids']
            self.trip_headsign = load_dict['trip_headsign']
            self.trip_ids = load_dict['trip_ids']

        # Create new sequence genereated from GTFS data.
        else:
            if trips_df is None:
                raise Exception(
                    'Either GTFS trips DataFrame or saved Sequence in dictionary format '
                    + 'must be provided.')

            self.stop_ids = stop_ids
            self.trip_ids = trip_ids
            self.set_attributes(trips_df)

    def assign_route_geometry(self, routes_gdf):
        """Assigns the matching route geometry in the given GeoDataFrame to this
        sequence. Returns True if a matching route geometry was found. Raises
        Exception if multiple matching route geometries were found."""
        matching_rows = routes_gdf[routes_gdf['route_dir'] ==
                                   self.get_route_dir()]

        if len(matching_rows) == 0:
            return False
        if len(matching_rows) > 1:
            raise Exception(
                'Multiple route geometries matched ' +
                f'(route_id={self.route_id}, direction_id={self.direction_id})')
        self.route_geometry = matching_rows.iloc[0]['geometry']
        return True
            
    def assign_stop_coords(self, stops_df):
        if self.route_geometry is None:
            raise Exception('Route geometry must be assigned before assigning stop coordinates.')
            
        self.stop_coords = [get_stop_coord(stops_df, s) for s in self.stop_ids]
        self.stop_coords = [snap_coord(c, self.route_geometry) for c in self.stop_coords]
        # TODO(cpcarey): Raise exception or return False if snapped coord is too far.

    def get_route_dir(self):
        """Returns a string representation of the route ID and direction ID of this sequence."""
        # e.g. "M15_0".
        return f'{self.route_id}_{self.direction_id}'

    def get_most_common(self, trips_df, column):
        """Returns the most common value of the given column for this
        sequence."""
        values = [trips_df.loc[trip_id][column] for trip_id in self.trip_ids]
        return most_common(values)

    def set_attributes(self, trips_df):
        """Assign attributes to this sequence based on the attribute that
        appears most often in matching trips. For example, if the majority of
        trips with this stop sequence have a route ID "M15", then this sequence
        of stops will be labelled as having an "M15" route ID. This is necessary
        due to mislabelled attributes."""
        self.direction_id = self.get_most_common(trips_df, 'direction_id')
        self.route_id = self.get_most_common(trips_df, 'route_id')
        self.service_id = self.get_most_common(trips_df, 'service_id')
        self.shape_id = self.get_most_common(trips_df, 'shape_id')
        self.trip_headsign = self.get_most_common(trips_df, 'trip_headsign')

    def to_dict(self):
        return {
            'direction_id': int(self.direction_id),
            'route_id': self.route_id,
            'service_id': self.trip_headsign,
            'shape_id': self.shape_id,
            'stop_ids': [int(s) for s in self.stop_ids],
            'trip_headsign': self.trip_headsign,
            'trip_ids': self.trip_ids,
        }
