"""
This module uses BW2 to generate and store Monte Carlo results fro already-configured databases.  Serializes results
as JSON files in the working directory.  The files are named by the activity ID (uuid) and results strictly append.
To start over you have to delete the file.
"""


import os
import time
import re

from collections import defaultdict
# from argparse import ArgumentParser

from lcatools import from_json, to_json
from brightway2 import Database, MonteCarloLCA
from bw2calc.matrices import MatrixBuilder
from bw2calc.utils import get_filepaths, global_index


FILE_PREFIX = 'BW2_MCA'


def _generate_c_matrix(method, biosphere_dict):
    """
    this whole segment taken from bw2calc.lca.LCA.load_lcia_data()
    :param method:
    :param biosphere_dict:
    :return:
    """

    method_path = get_filepaths(method, 'method')
    params, _, _, c_m = MatrixBuilder.build(method_path, "amount", "flow", "row", row_dict=biosphere_dict, one_d=True)
    if global_index is not None:
        mask = params['geo'] == global_index
        params = params[mask]
        c_m = MatrixBuilder.build_diagonal_matrix(params, biosphere_dict, "row", "amount")
    return c_m


class Bw2McaContainer(object):
    @classmethod
    def from_file(cls, filename, folder=None):
        if folder is None:
            folder = os.path.dirname(os.path.abspath(filename))
        if not os.path.isabs(filename):
            filename = os.path.join(folder, filename)
        j = from_json(filename)

        activity_id = re.search('%s_(.+)\.json\.gz$' % FILE_PREFIX, filename).group(1)
        act = next(a for a in Database(j['database']) if a.get('activity') == activity_id)

        b = cls(act, folder=folder, _do_load=False)
        b._install_data(j)
        b._update_results()
        return b

    def _install_data(self, j):
        for k, v in j['method_map'].items():
            self.add_method(tuple(v), key=k, _suppress_update=True)

        for k, v in j['results'].items():
            self._res[k].extend(v)

        self._steps = j['steps']

    def _load_file(self, steps):
        if steps is None:
            steps = 0
        if os.path.exists(self.full_path):
            j = from_json(self.full_path)
            assert(j['database'] == self.database)
            j['steps'] = max([steps, int(j['steps'])])
            self._install_data(j)
        else:
            self._steps = steps

    def __init__(self, activity, *args, folder=None, steps=None, _do_load=True):
        self._folder = folder
        self._a = activity
        self._sol = MonteCarloLCA({self._a: 1}, method=None)
        next(self._sol)  # appears to be necessary to force generation of biosphere dict, not sure
        self._m_map = dict()  # map method name (hashable) to tuple
        self._c_ms = dict()  # c matrices
        self._res = defaultdict(list)
        self._steps = 0
        if _do_load:
            self._load_file(steps)
        self.add_methods(*args)

    @property
    def activity(self):
        return self._a

    @property
    def database(self):
        return self._a.get('database')

    @property
    def methods(self):
        for k in sorted(self._res.keys()):
            yield self._m_map[k]

    @property
    def steps(self):
        return self._steps

    @property
    def full_path(self):
        if self._folder is None:
            return os.path.abspath(self.filename)
        return os.path.join(os.path.abspath(self._folder), self.filename)

    @property
    def filename(self):
        return '%s_%s.json.gz' % (FILE_PREFIX, self._a.get('activity'))

    def _write_file(self):
        j = {'database': self.database,
             'steps': self.steps,
             'method_map': {k: list(v) for k, v in self._m_map.items()},
             'results': {k: v for k, v in self._res.items()}
             }
        to_json(j, self.full_path, gzip=True)
        print('Written to %s' % os.path.abspath(self.full_path))

    @property
    def _up_to_date(self):
        ck = all(len(v) >= self.steps for v in self._res.values())
        if ck and len(self._res) > 0:
            print('Up to date with %d samples, %d methods' % (self.steps, len(self._res)))
        return ck

    def _update_results(self):
        """
        Ensure that every listed method has [at least] the required number of steps
        :return:
        """
        if self._up_to_date:
            return
        tstart = time.time()
        count = rcount = 0
        while not self._up_to_date:
            count += 1
            next(self._sol)
            for k, cm in self._c_ms.items():
                if len(self._res[k]) >= self.steps:
                    continue
                res = cm * self._sol.inventory
                self._res[k].append(res.sum())
                rcount += 1
            if count % 100 == 0:
                print('Completed %i MCA samples (%.3f sec)' % (count, time.time() - tstart))
        print('Added %i results from %i MCA samples (%.3f sec)' % (rcount, count, time.time() - tstart))
        self._write_file()

    @steps.setter
    def steps(self, value):
        value = int(value)
        if value > self._steps:
            self._steps = value
        self._update_results()

    def scores(self, method):
        key = next(k for k, v in self._m_map.items() if v == method)
        return self._res[key]

    def add_method(self, method, key=None, _suppress_update=False):
        """

        :param method: an LCIA method digestible by brightway (3-tuple)
        :param key: [None] the serializable key to represent the method (default is constructed as '__'.join(method))
        :return:
        """
        if key is None:
            key = '__'.join(method)
        self._m_map[key] = method
        if method not in self.methods:
            self._res[key].extend([])
        self._c_ms[key] = _generate_c_matrix(method, self._sol._biosphere_dict)
        if _suppress_update:
            return
        self._update_results()

    def add_methods(self, *args):
        for arg in args:
            self.add_method(arg, _suppress_update=True)
        self._update_results()


def initialize_activity(db_name, activity_id, *args, steps=100):
    try:
        act = next(a for a in Database(db_name) if a.get('activity').startswith(activity_id))
    except StopIteration:
        raise ValueError('Activity not found: %s'% activity_id)
    return Bw2McaContainer(act, *args, steps=steps)


'''
if __name__ == '__main__':
    """
    """
'''
