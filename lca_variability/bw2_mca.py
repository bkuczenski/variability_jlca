"""
This module uses BW2 to generate and store Monte Carlo results fro already-configured databases.  Serializes results
as JSON files in the working directory.  The files are named by the activity ID (uuid) and results strictly append.
To start over you have to delete the file.
"""


import os
import time

from collections import defaultdict
# from argparse import ArgumentParser

from lcatools import from_json, to_json
from brightway2 import Database, MonteCarloLCA, methods


FILE_PREFIX = 'BW2_MCA'


def run_montecarlo(activity, method, steps):
    _sol = MonteCarloLCA({activity: 1}, method=method)
    _res = [next(_sol) for x in range(steps)]
    return _res


class Bw2McaContainer(object):
    def _load_file(self, steps):
        if steps is None:
            steps = 0
        if os.path.exists(self.filename):
            j = from_json(self.filename)
            assert(j['database'] == self.database)
            if steps < j['steps']:
                steps = j['steps']
            for k, v in j['results'].items():
                self._res[k].extend(v)

        self.steps = int(steps)

    def __init__(self, activity, *args, steps=None):
        self._a = activity
        self._res = defaultdict(list)
        self._steps = 0
        self._load_file(steps)
        for m in args:
            self.add_method(m)
        self._update_results()

    @property
    def database(self):
        return self._a.database

    @property
    def methods(self):
        for k in sorted(self._res.keys()):
            yield k

    @property
    def steps(self):
        return self._steps

    @property
    def filename(self):
        return '%s_%s.json.gz' % (FILE_PREFIX, self._a.activity)

    def _write_file(self):
        j = {'database': self.database,
             'steps': self.steps,
             'results': {k: v for k, v in self._res.items()}
             }
        to_json(j, self.filename, gzip=True)

    def _update_results(self):
        """
        Ensure that every listed method has [at least] the required number of steps
        :return:
        """
        for k in self.methods:
            tstart = time.time()
            l = len(self._res[k])
            if l < self.steps:
                req = self.steps - l
                self._res[k].extend(run_montecarlo(self._a, k, req))
                print('%s: Added %i samples (%.3f sec)' % (k, req, time.time() - tstart))
        self._write_file()

    @steps.setter
    def steps(self, value):
        self._steps = int(value)
        self._update_results()

    def add_method(self, method):
        if method not in self.methods:
            self._res[method].extend([])
        self._update_results()


def initialize_activity(db_name, activity_id, *args, steps=100):
    try:
        act = next(a for a in Database(db_name) if a.activity.startswith(activity_id))
    except StopIteration:
        raise ValueError('Activity not found: %s'% activity_id)
    return Bw2McaContainer(act, *args, steps=steps)


'''
if __name__ == '__main__':
    """
    """
'''
