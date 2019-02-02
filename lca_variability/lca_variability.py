import json


class MarketImpactRangeResult(object):
    """
    An object which computes and stores the LCIA results for market suppliers.
    """
    def __init__(self, market, *quantities, index=None, saved_scores=None):
        """
        Note: use index=None to create a free-standing
        :param market: A process reference for a market process, supporting inventory queries
        :param quantities:
        :param index: [None] may only be set once
        :param saved_scores: [None] to restore scores from JSON
        """
        self._index = index
        self._market = market
        self._flowref = market.reference().flow.external_ref
        self._quantities = quantities
        self._suppliers = tuple([t for t in market.inventory(self._flowref)
                                 if t.flow.external_ref == self._flowref])
        self._scores = dict()
        if saved_scores is not None:
            for _q in self.quantities:
                if _q.external_ref not in saved_scores:
                    continue
                d = saved_scores[_q.external_ref]
                for _t in self.suppliers:
                    if _t not in d:
                        continue
                    key = (_q.external_ref, _t)
                    self._scores[key] = d[_t]

    @property
    def market(self):
        return self._market

    @property
    def index(self):
        return self._index

    @index.setter
    def index(self, val):
        if self._index is not None:
            raise ValueError('Index already set!')
        self._index = val

    @property
    def scored(self):
        if len(self._scores) < len(self._quantities) * (1 + len(self._suppliers)):
            return False
        return True

    def _add_scores_for_inventory(self, bg, ext_ref, **kwargs):
        if all((qty.external_ref, ext_ref) in self._scores for qty in self._quantities):
            return
        inv = [z for z in bg.lci(ext_ref, self._flowref, **kwargs)]
        for qty in self._quantities:
            if (qty.external_ref, ext_ref) in self._scores:
                continue
            res = qty.do_lcia(inv)
            self._scores[qty.external_ref, ext_ref] = res.total()

    def add_scores(self, bg, **kwargs):
        """

        :param bg: an interface supporting background queries (e.g. lci())
        :param kwargs: passed to lci()
        :return:
        """
        self._add_scores_for_inventory(bg, self._market.external_ref, **kwargs)
        for x in self._suppliers:
            self._add_scores_for_inventory(bg, x.termination, **kwargs)

    def _res_by_quantity(self, quantity):
        for x in self._suppliers:
            yield self._scores[quantity.external_ref, x.termination]

    @property
    def market_scores(self):
        return [self._scores[quantity.external_ref, self._market.external_ref] for quantity in self.quantities]

    @property
    def suppliers(self):
        return (x.termination for x in self._suppliers)

    @property
    def exchange_values(self):
        return [x.value for x in self._suppliers]

    @property
    def quantities(self):
        return (q for q in self._quantities)

    @property
    def size(self):
        return len(self._suppliers)

    def reset_scores(self, market=False):
        """
        Drop cached LCIA scores, enabling the scores to be re-computed via add_scores()
        :param market: [False] if False, discard supplier scores but retain scores for the market process.
         If True, discard the entire score set.
        :return:
        """
        if market:
            self._scores = dict()  # complete reset
        else:
            for x in self.suppliers:
                for q in self.quantities:
                    self._scores.pop((q.external_ref, x))

    def scores(self, quantity):
        return [x for x in self._res_by_quantity(quantity)]

    def unique(self, quantity):
        return len(set(self._res_by_quantity(quantity)))

    def ratio(self, quantity):
        scores = [s for s in filter(lambda x: x != 0, self._res_by_quantity(quantity))]
        if len(scores) == 0:
            return 0.0
        return max(abs(x) for x in scores) / min(abs(x) for x in scores)

    @property
    def ratios(self):
        return [self.ratio(k) for k in self.quantities]

    @property
    def max_ratio(self):
        """
        :return: a 2-tuple: max ratio, quantity that delivers max ratio
        """
        rs = [self.ratio(q) for q in self.quantities]
        mx = max(rs)
        return mx, self._quantities[rs.index(mx)]

    def __len__(self):
        return len(self._suppliers)

    def _serialize_scores(self):
        d = {q.external_ref: dict() for q in self.quantities}
        for k, v in self._scores.items():
            d[k[0]][k[1]] = v
        return d

    def serialize(self):
        return {
            'index': self.index,
            'market_external_ref': self.market.external_ref,
            'scores': self._serialize_scores()
        }


class MarketIterator(object):
    """

    """
    @classmethod
    def restore(cls, filename, catalog):
        with open(filename, 'r') as fp:
            j = json.load(fp)
        quantities = [catalog.query(q['origin']).get(q['external_ref']) for q in j['quantities']]
        factorize = j.pop('lu_factorization', False)
        mi = cls(catalog.query(j['origin']), *quantities, lu_factorization=factorize)
        for r in j['results']:
            idx = r['index']
            assert idx == len(mi)
            res = MarketImpactRangeResult(catalog.query(j['origin']).get(r['market_external_ref']), *quantities,
                                          index=idx,
                                          saved_scores=r['scores'])
            mi._res_add(res)
        return mi

    def __init__(self, query, *quantities, lu_factorization=True):
        """

        :param query: a catalog query with available background, index, and inventory implementations
        :param quantities: 1 or more quantity refs that deliver working LCIA results
        :param lu_factorization: [True] Perform LU decomposition- costs about 30s first time through, in exchange for
        speeding up LCI computations by about 10x thereafter (30-40ms vs 300-400ms). This means it's worth it if you
        are going to do more than about 100 computations.
        """
        self._query = query
        self._factorize = lu_factorization
        self._mkt_iterator = (mkt for mkt in self._query.processes(Name='^market for') if not
                              mkt['Name'].startswith('market for electricity'))
        self._results = []
        self._result_map = dict()
        self._quantities = quantities

    @property
    def origin(self):
        return self._query.origin

    @property
    def results(self):
        for k in self._results:
            yield k

    def _res_add(self, res):
        l = len(self._results)
        self._results.append(res)

        if res.index is None:
            res.index = l
        assert self._results[res.index] is res
        self._result_map[res.market.external_ref] = res

    def _res_gen(self, ext_ref=None):
        if ext_ref is None:
            mkt = next(self._mkt_iterator)
            if mkt.external_ref in self._result_map:
                return self._result_map[mkt.external_ref]
        else:
            # check result_map to avoid running the query if possible
            if ext_ref in self._result_map:
                return self._result_map[ext_ref]
            mkt = self._query.get(ext_ref)
        res = MarketImpactRangeResult(mkt, *self._quantities, index=len(self._results))
        self._res_add(res)
        self._res_populate(res)
        return res

    def _res_populate(self, res):
        if self._factorize:
            res.add_scores(self._query, solver='factorize')  # this takes about 30s the first time through
        else:
            res.add_scores(self._query)

    def __iter__(self):
        return self

    def __next__(self):
        return self._res_gen()

    '''# what is this for?
    def get_next(self):
        mkt = next(self._mkt_iterator)
        if mkt.external_ref in self._result_map:
            return self._result_map[mkt.external_ref].index
        return -1
    '''

    def get_result(self, ext_ref):
        return self._res_gen(ext_ref=ext_ref)

    @property
    def quantities(self):
        return [q for q in self._quantities]

    @property
    def markets(self):
        return [res.market for res in self._results]

    @property
    def ratios(self):
        return [res.max_ratio[0] for res in self._results]

    def ratios_for_quantity(self, quantity):
        return [res.ratio(quantity) for res in self._results]

    def __getitem__(self, item):
        return self._results[item]

    def __len__(self):
        return len(self._results)

    def serialize(self):
        return {
            'origin': self._query.origin,
            'quantities': [{'origin': q.origin, 'external_ref': q.external_ref} for q in self._quantities],
            'results': [r.serialize() for r in self._results],
            'lu_factorization': self._factorize
        }

    def save(self, filename):
        with open(filename, 'w') as fp:
            json.dump(self.serialize(), fp, indent=2)
