from collections import Counter

def most_common(list):
    """Returns the most common value in the given list."""
    counts = Counter(list)
    return counts.most_common(1)[0][0]

class Sequence:
    def __init__(self, stop_ids, trip_ids, trips_df):
        self.stop_ids = stop_ids
        self.trip_ids = trip_ids
        self.set_attributes(trips_df)

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
        self.trip_headsign = self.get_most_common(trips_df, 'trip_headsign')
        self.shape_id = self.get_most_common(trips_df, 'shape_id')
    
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