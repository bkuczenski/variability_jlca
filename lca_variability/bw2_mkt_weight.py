from brightway2 import MonteCarloLCA, Database
from .bw2_mca import Bw2McaContainer
from random import random
from numpy import cumsum


class WeightedChooser(object):
    """
    This random number generator accepts an ordered list of weights, and each iteration returns an index into the
    list chosen in proportion to the weights.  The frequency that a given index should appear should equal its weight
    value in proportion to the sum of all weights.
    """
    def __init__(self, array):
        self._a = array
        self._c = cumsum(array)
        self._m = self._c[-1]

    def __iter__(self):
        return self

    def __next__(self):
        r = random() * self._m
        return sum(r > self._c)  # this works despite lint because of numpy

    @property
    def list(self):
        return list(self._a)


class MarketMonteCarloIterator(object):
    """
    This takes in a BW2 activity, presumed to be a market process, and for each iteration returns a monte carlo
    inventory for one of the market suppliers (plus non-supplier inputs), chosen at random in proportion to each
    supplier's market share.
    """
    def __init__(self, market):
        mkt_flow = market.get('flow')
        demand_base = {x.input: x.amount for x in market.technosphere() if x.get('flow') != mkt_flow}
        suppliers = [(x.amount, x.input) for x in market.technosphere() if x.get('flow') == mkt_flow]
        mkt_shares = [x[0] for x in suppliers]
        self._chooser = WeightedChooser(mkt_shares)
        self._suppliers = [x[1] for x in suppliers]
        self._mca = []

        self._biosphere_dict = None
        self._inventory = None
        self._last_index = None

        for x in self._suppliers:
            demand = dict(demand_base)
            demand[x] = 1.0
            self._mca.append(MonteCarloLCA(demand, method=None))

    @property
    def biosphere(self):
        if self._biosphere_dict is None:
            next(self)
        return self._biosphere_dict

    @property
    def inventory(self):
        next(self)
        return self._inventory

    @property
    def market_shares(self):
        return self._chooser.list

    @property
    def suppliers(self):
        return self._suppliers

    @property
    def last_index(self):
        return self._last_index

    def __iter__(self):
        return self

    def __next__(self):
        r = next(self._chooser)
        m = self._mca[r]
        next(m)
        if self._biosphere_dict is None:
            self._biosphere_dict = m._biosphere_dict  # assuming this is going to be the same for all
        self._inventory = m.inventory
        self._last_index = r
        return r


class Bw2McaMarketWeight(Bw2McaContainer):

    FILE_PREFIX = 'BW2_MktWt'

    def __init__(self, market, *args, **kwargs):
        self._sol = MarketMonteCarloIterator(market)
        super(Bw2McaMarketWeight, self).__init__(market, *args, **kwargs)

    @property
    def biosphere(self):
        return self._sol.biosphere

    def _next_inventory(self):
        return self._sol.inventory


def initialize_market_model(db_name, activity_id, *args, steps=100):
    try:
        act = next(a for a in Database(db_name) if a.get('activity').startswith(activity_id))
    except StopIteration:
        raise ValueError('Activity not found: %s'% activity_id)
    return Bw2McaMarketWeight(act, *args, steps=steps)
