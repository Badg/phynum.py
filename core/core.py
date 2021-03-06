import pandas as pd
import numpy as np
from scipy.stats import gmean
import random as rand
import math

_basename = "nodecoord_"
_connect_col = "_connections"
_coord_row = "_coord"
_units_row = "_units"

"""
Goal is to extend pandas dataframes to nodes, providing direct support for 
n-dim coordinates, as well as connections between points.

"""
class NodeDataFrame(pd.DataFrame):
    """ A pandas.dataframe object that contains, at a minimum, N columns of 
    coordinates.  May also include a column defining connections between
    nodes. Mostly a convenience class.
    """
    # Need to add error traps such that connections are always a list of ints
    # and at least one coordinate must be defined.
    def __init__(self, data, coords, *args, units=None, columns=None, 
        **kwargs):
        # Do a quick pre-check on the data
        if type(data) is dict:
            columns = list(data.keys())
        elif type(data) is pd.DataFrame:
            columns = list(data.columns)

        # Argument error traps
        if not columns:
            # Can't have coordinates without at least one named column
            raise ValueError('At least one column must be named.')

        # Supported definitions of units: {<key>: <str>} and [<str>]
        if units:
            # First try it as a dictionary
            try:
                for key, value in units.items():
                    if key not in columns:
                        raise Warning('Coord ' + key + ' not in column names; '
                            'we\'ve appended it, but unexpected behavior may '
                            'occur.')
                        columns.append(key)
            # Okay, not a dictionary. Try it as a list.
            except AttributeError:
                try:
                    if len(units) != len(columns):
                        raise Warning('Number of units doesn\'nt match number'
                            'of columns.')
                    units = {col: unit for col, unit in zip(columns, units)}
                except (TypeError, AttributeError):
                    raise Warning('Ill-defined units. Proceeding without '
                        'units.')
                    units = {}
        else:
            units = {}


        # Coords must either be a dict of <field>: <bool>...
        try:
            # First try as a dictionary
            # Make sure the key is in the columns and the items are bools
            for key, coord in coords.items():
                if type(coord) is not bool:
                    raise ValueError('Coordinate dictionary values must '
                        'contain only bools.')
                if len(coords) > len(columns):
                    raise ValueError('Cannot have more coordinates than named'
                        ' columns.')
                if key not in columns:
                    raise Warning('Coord ' + key + ' not in column names; '
                        'we\'ve appended it, but unexpected behavior may '
                        'occur.')
                    columns.append(key)
        except AttributeError:
            # ... or a list of columns...
            try:
                if type(coords[0]) is str:
                    for coord in coords:
                        # Warn if the coordinate is missing from the columns
                        if coord not in columns:
                            raise Warning('Coord ' + coord + ' not in column '
                                'names; we\'ve appended it, but unexpected '
                                'behavior may occur.')
                            columns.append(coord)
                    # Convert it to a boolean dict
                    coords = {col: (col in coords) for col in columns}
                # ... or a list of bools, though that might be risky.
                elif type(coords[0]) is bool:
                    # Catch index exceptions to give a better description
                    if len(coords) != len(columns):
                        raise IndexError('Length of coords must match number '
                            'of columns.')
                    # No problems? Do a dict comprehension of the zip of the two.
                    else:
                        coords = {col: coord for col, coord in zip(columns, 
                            coords)}
                # Catch ill-formed coordinate declaration.
                else:
                    raise TypeError()
            except TypeError:
                raise TypeError('Coords must be in form [<str>], [<bool>], or '
                        '{<key>: <bool>}.')

        # Add internal columns
        if _connect_col not in columns:
            columns.append(_connect_col)

        super(NodeDataFrame, self).__init__(data, *args, columns=columns, 
            **kwargs)

        self.loc[_coord_row, :] = pd.Series(coords)
        self.loc[_units_row, :] = pd.Series(units)
    

class NodeSeries(pd.Series):
    """ A pandas.series object that contains, at a minimum, N columns of 
    coordinates.  May also include a column defining connections between 
    nodes, though it should be noted that this would only be useful if the 
    series is a view into a nodedataframe.
    """
    pass


def unit_norm(arr):
    """ Normalizes an np array along rows such that 
    sqrt(a1^2 + a2^2 + ...) = 1.


    """
    try:
        m = len(arr)
        return arr / (((arr ** 2).sum(axis=1, keepdims=True)) ** (1/2))
    except ValueError:
        try: return unit_norm(arr.reshape(1,m)).squeeze()
        except ValueError:
            raise ValueError("Value error in recursive call.")
    except TypeError:
        try: return unit_norm(np.array(arr))
        except TypeError:
            raise TypeError("Argument must be convertible to numpy array.")


def linterp_1D(series1, series2, colname, coord, ignore=None):
    """Simple 1d linear interpolator between 2 pandas series.
    """
    if ignore:
        ignore.append(colname)
    else:
        ignore = [colname]    

    index1 = series1.index
    index2 = series2.index

    datcols = [col for col in index1 if col not in ignore and col in index2]

    x1 = series1.loc[colname]
    x2 = series2.loc[colname]

    if x1 == x2:
        # HOW TO HANDLE THIS?!?!?!
        #########################################################
        #########################################################
        pass

    return series1.loc[datcols] + (coord - x1) * (series2.loc[datcols] - 
        series1.loc[datcols]) / (x2 - x1)

def get_cubic_weight(pd_ser):
    """Assigns a normalized (w1+w2=1) weight to pd_ser, decaying with r^3.
    """
    closest = min(pd_ser)
    weights = (closest / pd_ser) ** 3
    return (weights / weights.sum()).fillna(0)

def pd_dist(pd_ser1, pd_ser2 = pd.Series({'x': 0, 'y': 0, 'z': 0}), 
    coords=['x', 'y', 'z']):
    """ Gets a distance between 2 points in cartesian space, or to the origin.
    """
    # Predeclare total to zero
    total = 0
    for coord in coords:
        if coord in pd_ser1.index and coord in pd_ser2.index:
            total += (pd_ser2.loc[coord] - pd_ser1.loc[coord]) ** 2
        else:
            raise KeyError("Key " + coord + " missing from series.")
    return total ** (1/2)
        
def get_dist(coords1, coords2):
    """ Gets the scalar distance from coords1 to coords2.
    
    +"coords1" and "coords2" are lists.  If one is longer than the other, 
    execution halts at the end of the shortest list.
    """
    deltas = []
    summe = 0
    
    for coord1, coord2 in zip(coords1, coords2):
        deltas.append(coord2-coord1)
    
    for delta in deltas:
        summe += delta**2
    
    return (summe ** .5)

def get_deltas(iterable):
    """ Calculates the deltas between adjacent elements in an iterable.
    
    + Iterable is an iterable of length minimum n = 2
    
    Returns an iterable of length n - 1.
    """
    # Initialize the offset variable with an "empty" element
    offset = [0]
    offset.extend(iterable)
    # Create a list of spread-normalized deltas (first will be zero)
    deltas = [(it - off) for off, it in zip(offset, iterable)]
    # Remove first element so it doesn't screw up calculations
    del deltas[0]
    
    return deltas

# Note: this search could be improved by progressive bucketing, ie: for each
# coordinate, slice by range.  That would greatly decrease the search space
# for each coordinate, theoretically (maybe?) decreasing time to select,
# instead of needing to satisfy multiple conditions.  I guess it depends on
# the internals of the selection on the pandas side.

# At any rate, this needs to be generalized to N-dimensional coordinates.
def knn_coords(df, k, coords, scale_length=None):
    """ Searches a pandas <df> for the <k> nearest neighbours to <coords>.
    
    Arguments
    =========
    + <df> : pandas dataframe to search
    + <k> : integer number of neighbors to find
    + <coords> : tuple or list of coordinates to search
    + <scale_length> : optional approximate side length of each coordinate 
    cell.  Used to preselect search bucket for faster search and highly 
    recommended for any large <df>.
    
    Returns
    =======
    + <nameless> : pandas dataframe
    """    
    # Extract coords
    x = coords[0]
    y = coords[1]
    z = coords[2]
    
    # Create the search bucket
    bucket = pd.DataFrame()
    bucketslop = 2
    
    # If scale length is defined, shrink the search bucket
    if scale_length:
        # Conservatively select a "cube" of data with side length bucket_leg
        # centered at coords
        bucket_leg = k * scale_length / 2
        # If the bucket is smaller than bucketslop*k (cannot be k, since this 
        # is searching manhattan distance and we want euclidian distance), 
        # select a bucket and then (just in case) scale the bucket_leg
        while len(bucket) < k * bucketslop:
            bucket = df[(df.x - x > -bucket_leg) & (df.x - x < bucket_leg) &
                        (df.y - y > -bucket_leg) & (df.y - y < bucket_leg) &
                        (df.z - z > -bucket_leg) & (df.z - z < bucket_leg)]
            # Double the bucket leg length in case this is too small
            bucket_leg *= 2
    # If scale length isn't defined, use the whole df
    else:
        bucket = df
        
    # Progress report: we have a search bucket.  Now let's search it.
    # Examine each row in the bucket and calculate the distance to target, 
    # creating a zip of [(<distance>, <index>)]
    dists = ((bucket.loc[:,'x'] - x)**2 + (bucket.loc[:,'y'] - y)**2 + 
             (bucket.loc[:,'z'] - z)**2)**(1/2)
    dists = zip(dists, range(len(dists)))
    
    # Now sort dists ascendingly and select the k indices
    dists = sorted(dists, key=lambda item: item[0])
    dists = dists[:k]
    sel = [it[1] for it in dists]
    
    # Return the corresponding first k elements from bucket
    return bucket.iloc[sel]
    
def remove_duplicates(lst):
    """ Removes duplicates in a list, preserving list order."""
    unique = []
    for ii in lst:
        if ii not in unique:
            unique.append(ii)
    return unique

