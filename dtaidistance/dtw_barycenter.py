# -*- coding: UTF-8 -*-
"""
dtaidistance.dtw_barycenter
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Dynamic Time Warping (DTW) Barycenter

:author: Wannes Meert
:copyright: Copyright 2020 KU Leuven, DTAI Research Group.
:license: Apache License, Version 2.0, see LICENSE for details.

"""
import logging
import math
import array

from .dtw import warping_path
from . import ed
from . import util
from . import util_numpy
from .util import SeriesContainer
from .exceptions import NumpyException


logger = logging.getLogger("be.kuleuven.dtai.distance")


dtw_cc = None
try:
    from . import dtw_cc
except ImportError:
    logger.debug('DTAIDistance C library not available')
    dtw_cc = None


try:
    if util_numpy.test_without_numpy():
        raise ImportError()
    import numpy as np
except ImportError:
    np = None


def dba_loop(s, c=None, max_it=10, thr=0.001, mask=None,
             keep_averages=False, use_c=False, **kwargs):
    s = SeriesContainer.wrap(s)
    avg = None
    avgs = None
    if keep_averages:
        avgs = []
    if c is None:
        # If no initial sequence is given, use the first one.
        if mask is None:
            c = s[0]
        else:
            curi = 0
            while mask[curi] is False:
                curi += 1
            c = s[curi]
        # You can also use a constant function, but this gives worse performance.
        # After the first iteration, this will be the average of all
        # sequences. The disadvantage is that this might create e.g. multiple
        # peaks for a sequence with only one peak (but shifted) and then the
        # original sequences will map their single peak to the different peaks
        # in the first average and converge to that as a local optimum.
        # t = s.get_avg_length()
        # c = array.array('d', [0] * t)
    if mask is None:
        mask = np.full((len(s),), True, dtype=bool)
    for it in range(max_it):
        logger.debug(f'DBA Iteration {it}')
        if use_c:
            assert(c is not None)
            c_copy = c.copy()  # The C code reuses this array
            if np is not None and isinstance(mask, np.ndarray):
                # The C code requires a bit array of uint8 (or unsigned char)
                mask_copy = np.packbits(mask, bitorder='little')
            else:
                raise Exception('Mask only implemented for C when passing a Numpy array. '
                                f'Got {type(mask)}')
            dtw_cc.dba(s, c_copy, mask=mask_copy, **kwargs)
            avg = c_copy
        else:
            avg = dba(s, c, mask=mask, use_c=use_c, **kwargs)
        if keep_averages:
            avgs.append(avg)
        if thr is not None and c is not None:
            diff = 0
            # diff = np.sum(np.subtract(avg, c))
            for av, cv in zip(avg, c):
                diff += abs(av - cv)
            diff /= len(avg)
            if diff <= thr:
                logger.debug(f'DBA converged at {it} iterations (avg diff={diff}).')
                break
        c = avg
    if keep_averages:
        return avg, avgs
    return avg


def dba(s, c, mask=None, use_c=False, **kwargs):
    """

    F. Petitjean, A. Ketterlin, and P. Gan ̧carski.
    A global averaging method for dynamic time warping, with applications to clustering.
    Pattern Recognition, 44(3):678–693, 2011.

    :param s: Container of sequences
    :param c: Initial averaging sequence.
        If none is given, the first one is used.
        Better performance can be achieved by starting from an informed
        starting point (Petitjean et al. 2011).
    :param kwargs: Arguments for dtw.distance
    :return: Bary-center of length len(c).
    """
    s = SeriesContainer.wrap(s)
    if mask is not None and not mask.any():
        # Mask has not selected any cluster
        print("Empty mask, returning zero-constant average")
        c = array.array('d', [0] * len(s[0]))
        return c
    t = len(c)
    assoctab = [[] for _ in range(t)]
    for idx, seq in enumerate(s):
        if mask is not None and not mask[idx]:
            continue
        if use_c:
            m = dtw_cc.warping_path(c, seq, **kwargs)
        else:
            m = warping_path(c, seq, **kwargs)
        for i, j in m:
            assoctab[i].append(seq[j])
    cp = array.array('d', [0] * t)
    for i, values in enumerate(assoctab):
        if len(values) == 0:
            print('XXX zero values XXX')
            print(c)
            for seq in s:
                print(seq)
            print(assoctab)
        cp[i] = sum(values) / len(values)  # barycenter
    return cp
