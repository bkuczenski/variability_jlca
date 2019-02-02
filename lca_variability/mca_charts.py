"""
Helper functions and utilities for plotting results
"""
import numpy as np
from math import floor, ceil
from matplotlib import pyplot as plt


class TraceLine(object):
    """
    Little helper class for drawing vlines on a chart
    """
    def __init__(self, value, label=None, **kwargs):
        self.value = value
        self._label = label
        self._args = kwargs

    @property
    def label(self):
        if self._label is None:
            return 'TraceLine(%g)' % self.value
        return self._label

    @property
    def args(self):
        return self._args


'''
Numerical processing functions
'''

def _find_range(ax, dat):
    r1 = 1.2 * (max(dat) - min(dat))
    r2 = ax.get_xlim()[1] - ax.get_xlim()[0]
    return max([r1, r2])


def _kill_zeros(data, factor=10):
    _zero = data == 0
    if sum(_zero) > 0:
        low = next(k for k in sorted(data) if k > 0) / factor
        print('Warning: %d zero-valued scores found. Replacing with 1/%d the lowest nonzero value..' %
              (sum(_zero), factor))
        data[_zero] = low
    return data


def find_95(_data):
    _l = len(_data)
    _s = sorted(_data)
    _i025 = _s[int(ceil(_l * 0.025))]
    _i975 = _s[int(floor(_l * 0.975))]
    return _i025, _i975


def is_outlier(points, thresh=3.5):
    """
    Returns a boolean array with True if points are outliers and False
    otherwise.

    Parameters:
    -----------
        points : An numobservations by numdimensions array of observations
        thresh : The modified z-score to use as a threshold. Observations with
            a modified z-score (based on the median absolute deviation) greater
            than this value will be classified as outliers.

    Returns:
    --------
        mask : A numobservations-length boolean array.

    References:
    ----------
        Boris Iglewicz and David Hoaglin (1993), "Volume 16: How to Detect and
        Handle Outliers", The ASQC Basic References in Quality Control:
        Statistical Techniques, Edward F. Mykytka, Ph.D., Editor.
    """
    if len(points.shape) == 1:
        points = points[:, None]
    median = np.median(points, axis=0)
    diff = np.sum((points - median) ** 2, axis=-1)
    diff = np.sqrt(diff)
    med_abs_deviation = np.median(diff)

    modified_z_score = 0.6745 * diff / med_abs_deviation

    return modified_z_score > thresh


def _add_mc_hist_to_ax(_ax, _data, bins=50, density=False, show_ci=False, log_correct=False, log_scale=True, **kwargs):
    _npres = np.array(_data)
    if log_scale:
        _npres = _kill_zeros(_npres)

    _trim = is_outlier(_npres, thresh=6)
    _nptrim = _npres[~_trim]
    if show_ci:
        _tag = ' (w/95CI)'
    else:
        _tag = ''

    if log_correct:
        log_bins = np.logspace(np.log10(min(_nptrim)) - .001, np.log10(max(_nptrim)), bins + 1)
        vv, bins, _ = plt.hist(_nptrim, bins=log_bins, axes=_ax, histtype='step', density=False,
                               linestyle=':', linewidth=2,
                               label='Monte Carlo N=%d%s' % (len(_data), _tag))
    else:
        vv, bins, _ = plt.hist(_nptrim, bins=bins, axes=_ax, histtype='step', density=density,
                               linestyle=':', linewidth=2,
                               label='Monte Carlo N=%d%s' % (len(_data), _tag))
    if log_scale:
        _ax.set_xscale('log')

    if show_ci:
        _bounds = find_95(_nptrim)
        _ylim = _ax.get_ylim()
        _yval = 0.82 * _ylim[0] + 0.18 * _ylim[1]
        if show_ci == 'stem':
            _m, _s, _b = plt.stem(_bounds, (_yval, _yval))
            plt.setp(_m, color=[0.7, 0, 0.4], marker='+', markersize=8, markeredgewidth=2)
            plt.setp(_b, visible=False)
            plt.setp(_s, color=[0.7, 0, 0.4])
        else:
            plt.scatter(_bounds, (_yval, _yval), marker='|', s=500, c=[[0.7, 0, 0.4]])

    return vv, bins, _npres[_trim]


def _add_discrete_bars_to_ax(_ax, _xv, _yv, _norm, _nbins=50, _color=(0.7, 0, 0), **kwargs):
    rang = _find_range(_ax, _xv)
    _wid = rang / _nbins
    # _wid = max(_yv) / _norm
    plt.bar(_xv, [_k / _wid for _k in _yv], width=_wid, color=_color, axes=_ax, **kwargs)


def _add_scaled_bars_to_ax(_ax, _xv, _yv, _scale, _nbins=50, _color=(0, 0.4, 0.3), **kwargs):
    rang = _find_range(_ax, _xv)
    _wid = rang / _nbins
    plt.bar(_xv, [_i * _scale for _i in _yv], width=_wid, color=_color, axes=_ax, **kwargs)


_marker_props = ('marker', 'markersize', 'markerfacecolor', 'markeredgecolor', 'markeredgewidth')
_stem_props = ('linewidth', 'linestyle')


def _add_stem_plot_to_ax(_ax, _xv, _yv, _scale, _color=(0, 0.62, 0.08), label=None, **kwargs):
    (mkrs, stems, baseline) = plt.stem(_xv, [_i * _scale for _i in _yv], label=label)
    plt.setp(baseline, visible=False)
    plt.setp(stems, color=_color, **{k: v for k, v in kwargs.items() if k in _stem_props})
    _mkr_set = {k: v for k, v in kwargs.items() if k in _marker_props}
    if len(_mkr_set) > 0:
        plt.setp(mkrs, **_mkr_set)


'''
Public-facing functions
'''


def mc_mkt_combo(ax, xvals, shares, mc_res, annot, style='stem', traces=None, **kwargs):
    """
    valid styles: 'norm', 'stem', 'scaled'
    """
    if style not in ('norm', 'stem', 'scaled'):
        raise ValueError('unknown style %s' % style)

    opt = style == 'norm'
    vv, bins, trimmed = _add_mc_hist_to_ax(ax, mc_res, density=opt, **kwargs)
    if len(trimmed) > 0:
        print('%s: Trimmed %d outliers' % (annot['method'], len(trimmed)))

    '''
    _npres = np.array(mc_res)
    _trim = is_outlier(_npres, thresh=6)
    if sum(_trim) > 0:
        print('%s: Trimming %d outliers' % (annot['method'], sum(_trim)))

    vv, bins, _ = plt.hist(_npres[~_trim], bins=50, axes=ax, histtype='step', density=opt, linestyle=':', linewidth=2,
                          label='Monte Carlo N=%d' % len(mc_res))
    '''
    if ax.get_xscale() == 'log':
        xvals = [bins[0] if x == 0 else x for x in xvals]
    if opt:
        _add_discrete_bars_to_ax(ax, xvals, shares, max(vv), label='suppliers')
        # , _color='none', linestyle='--', linewidth=0.8, edgecolor='black')
        ax.set_yticks([])
        ax.set_ylabel('Relative Frequency')
    else:
        mxsh = max(vv) / max(shares)
        if style == 'scaled':
            _add_scaled_bars_to_ax(ax, xvals, shares, mxsh, _nbins=65)
        else:
            _add_stem_plot_to_ax(ax, xvals, shares, mxsh, label='suppliers (%s)' % annot['ei'])
        # ax.yaxis.tick_right()
        ax.set_ylabel('Market Share')

        mxlb = int(ceil(max(shares) * 10))
        lbl_vals = [x / 10 for x in range(mxlb)]
        lbl_pos = [x * mxsh for x in lbl_vals]
        lbl_name = ['%.1f' % x for x in lbl_vals]

        ax.set_yticks(lbl_pos)
        ax.set_yticklabels(lbl_name)

    ax.set_title(annot['title'])
    ax.set_xlabel(annot['method'])
    if traces is not None:
        ylim = ax.get_ylim()
        for tr in traces:
            ax.vlines(tr.value, ylim[0], ylim[1], label=tr.label, **tr.args)
        ax.set_ylim(ylim)
