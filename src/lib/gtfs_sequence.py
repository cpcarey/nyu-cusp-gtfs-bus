from collections import Counter
from shapely.geometry import Point
import datetime
import numpy as np

import line_string_util


def deserialize_coord(values):
    return Point(values[0], values[1])


def get_stop_coord(stops_df, stop_id):
    """Returns the lon/lat Point for the stop with the given ID using the provided
    GTFS stops DataFrame."""
    row = stops_df.loc[stop_id]
    return Point(row['stop_lon'], row['stop_lat'])


def most_common(list):
    """Returns the most common value in the given list."""
    counts = Counter(list)
    return counts.most_common(1)[0][0]


def deserialize_trip_time(trip_time):
    return datetime.datetime.fromisoformat(trip_time)


def deserialize_trip_times(trip_times):
    return [deserialize_trip_time(t) for t in trip_times]


def deserialize_trip_times_dict(trip_times_dict):
    return {
        trip_id: deserialize_trip_times(trip_times)
        for trip_id, trip_times in trip_times_dict.items()
    }


def serialize_coord(coord):
    return [coord.x, coord.y]


def serialize_trip_time(trip_time):
    return trip_time.isoformat()


def serialize_trip_times(trip_times):
    return [serialize_trip_time(t) for t in trip_times]


def serialize_trip_times_dict(trip_times_dict):
    return {
        trip_id: serialize_trip_times(trip_times)
        for trip_id, trip_times in trip_times_dict.items()
    }


def snap_coord(coord, geometry):
    """Returns a Point on the given Geometry of the closest position to the given coordinate."""
    return geometry.interpolate(geometry.project(coord))


class Sequence:

    def __init__(self, stop_ids=[], trip_ids=[], trips_df=None, load_dict=None):
        # Create self instance loaded from dictionary representation.
        if load_dict:
            self.direction_id = load_dict['direction_id']
            self.route_id = load_dict['route_id']
            self.service_id = load_dict['service_id']
            self.shape_id = load_dict['shape_id']
            self.stop_distances = load_dict['stop_distances']
            self.stop_ids = load_dict['stop_ids']
            self.trip_durations_dict = load_dict['trip_durations_dict']
            self.trip_headsign = load_dict['trip_headsign']
            self.trip_ids = load_dict['trip_ids']
            self.trip_speeds_dict = load_dict['trip_speeds_dict']

            self.stop_coords = [
                deserialize_coord(c) for c in load_dict['stop_coords']
            ]
            self.trip_times_dict = deserialize_trip_times_dict(
                load_dict['trip_times_dict'])

        # Create new self genereated from GTFS data.
        else:
            if trips_df is None:
                raise Exception(
                    'Either GTFS trips DataFrame or saved sequence in dictionary format '
                    + 'must be provided.')

            self.stop_ids = stop_ids
            self.trip_ids = trip_ids
            self.set_attributes(trips_df)

            self.stop_coords = []
            self.stop_distances = []
            self.trip_durations_dict = {}
            self.trip_speeds_dict = {}
            self.trip_times_dict = {}

        self.length = len(self.stop_ids)
        self.trip_ids_set = set(self.trip_ids)

    def aggregate_speeds(self):
        stop_speeds = [[] for x in range(self.length)]
        for trip_speeds in self.trip_speeds_dict.values():
            for i, speed in enumerate(trip_speeds):
                stop_speeds[i].append(speed)
        self.stop_speeds = [np.mean(s) for s in stop_speeds]

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
            raise Exception(
                'Route geometry must be assigned before assigning stop coordinates.'
            )

        self.stop_coords = [get_stop_coord(stops_df, s) for s in self.stop_ids]
        self.stop_coords = [
            snap_coord(c, self.route_geometry) for c in self.stop_coords
        ]
        # TODO(cpcarey): Raise exception or return False if snapped coord is too far.

    def calculate_stop_distances(self):
        """Calculates the distance (in m) along the route geometry between each stop."""
        self.stop_distances = [0]
        for i in range(self.length - 1):
            p1 = self.stop_coords[i]
            p2 = self.stop_coords[i + 1]
            # TODO(cpcarey): Use accurate distance calculation.
            # Approximation of degrees to meters.
            self.stop_distances.append(p1.distance(p2) * (0.11 / 0.000001))

    def calculate_trip_durations(self):
        """Calculates the time duration (in s) between each stop for each trip."""
        self.trip_durations_dict = {}
        for trip_id, trip_times in self.trip_times_dict.items():
            self.trip_durations_dict[trip_id] = [0]
            for i in range(self.length - 1):
                t1 = trip_times[i]
                t2 = trip_times[i + 1]
                duration = (t2 - t1).total_seconds()
                self.trip_durations_dict[trip_id].append(duration)

    def calculate_trip_speeds(self):
        """Calculates the average speeds (in m/s) along the route geometry between each stop."""
        if self.stop_distances == []:
            self.calculate_stop_distances()
        if self.trip_durations_dict == {}:
            self.calculate_trip_durations()

        self.trip_speeds_dict = {}
        for trip_id in self.trip_times_dict.keys():
            self.trip_speeds_dict[trip_id] = [0]
            for i in range(1, self.length):
                distance = self.stop_distances[i]
                duration = self.trip_durations_dict[trip_id][i]
                self.trip_speeds_dict[trip_id].append(distance / duration)

    def get_route_dir(self):
        """Returns a string representation of the route ID and direction ID of this sequence."""
        # e.g. "M15_0".
        return f'{self.route_id}_{self.direction_id}'

    def get_most_common(self, trips_df, column):
        """Returns the most common value of the given column for this
        self."""
        values = [trips_df.loc[trip_id][column] for trip_id in self.trip_ids]
        return most_common(values)
        
    def get_speeds_gdf(self):
        """Returns a GeoDataFrame of line segments between stops marked with speeds
        at segment endpoints."""
        assert self.length > 0
        assert self.route_geometry != None
        speeds_gdf = line_string_util.segment_by_distances(
            self.route_geometry, self.stop_distances, self.stop_speeds)
        speeds_gdf.loc[:, 'route_id'] = self.route_id
        speeds_gdf.loc[:, 'direction_id'] = self.direction_id
        return speeds_gdf

    def has_trip_id(self, trip_id):
        return trip_id in self.trip_ids_set

    def set_attributes(self, trips_df):
        """Assigns attributes to this sequence based on the attribute that
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
            'stop_coords': [serialize_coord(c) for c in self.stop_coords],
            'stop_distances': self.stop_distances,
            'stop_ids': [int(s) for s in self.stop_ids],
            'trip_headsign': self.trip_headsign,
            'trip_ids': self.trip_ids,
            'trip_durations_dict': self.trip_durations_dict,
            'trip_speeds_dict': self.trip_speeds_dict,
            'trip_times_dict': serialize_trip_times_dict(self.trip_times_dict),
        }

    def trim_route_geometry(self):
        """Trims the route geometry of this sequence to start and end at the
        coordinates of the first and last stops."""
        assert self.length > 0
        assert self.route_geometry != None
        trimmed_geometry = self.route_geometry
        trimmed_geometry = line_string_util.cut(trimmed_geometry,
                               trimmed_geometry.project(
                                   self.stop_coords[-1]))[0]
        trimmed_geometry = line_string_util.cut(trimmed_geometry,
                               trimmed_geometry.project(
                                   self.stop_coords[0]))[-1]
        self.route_geometry = trimmed_geometry
