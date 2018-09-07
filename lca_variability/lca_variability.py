import json


class MarketImpactRangeResult(object):
    """
    An object which computes and stores the LCIA results for market suppliers.
    """
    def __init__(self, market, index, *quantities, saved_scores=None):
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
        mi = cls(catalog.query(j['origin']), *quantities)
        for r in j['results']:
            idx = r['index']
            assert idx == len(mi)
            res = MarketImpactRangeResult(catalog.query(j['origin']).get(r['market_external_ref']), idx, *quantities,
                                          saved_scores=r['scores'])
            mi._res_add(res)
        return mi

    def __init__(self, query, *quantities):
        """

        :param query: a catalog query that provides full bg + ix + inv implementation
        :param quantities: 1 or more quantity refs that deliver working LCIA results
        """
        self._query = query
        self._mkt_iterator = (mkt for mkt in self._query.processes(Name='^market for') if not
                              mkt['Name'].startswith('market for electricity'))
        self._results = []
        self._result_map = dict()
        self._quantities = quantities

    def _res_add(self, res):
        self._results.append(res)
        assert self._results[res.index] is res
        self._result_map[res.market.external_ref] = res

    def _res_gen(self):
        mkt = next(self._mkt_iterator)
        res = MarketImpactRangeResult(mkt, len(self._results), *self._quantities)
        self._res_add(res)
        return res

    def _res_populate(self, res):
        res.add_scores(self._query)

    def __iter__(self):
        return self

    def __next__(self):
        res = self._res_gen()
        self._res_populate(res)
        return res

    def get_next(self):
        mkt = next(self._mkt_iterator)
        if mkt.external_ref in self._result_map:
            return self._result_map[mkt.external_ref].index
        return -1

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
            'results': [r.serialize() for r in self._results]
        }

    def save(self, filename):
        with open(filename, 'w') as fp:
            json.dump(self.serialize(), fp, indent=2)
