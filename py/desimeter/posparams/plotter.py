# -*- coding: utf-8 -*-
"""
Plot time series of positioner parameters.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.colors
import numpy as np
from astropy.time import Time

# common options
img_ext = '.png'
error_series_filename = 'fiterror' + img_ext
tick_period_days = 7
day_in_sec = 24*60*60
DATE_SEC = 'DATA_END_DATE_SEC'

def plot_params(table, savepath, statics_during_dynamic):
    '''Plot time series of positioner parameters for a single positioner.
    
    Inputs:
        table    ... Astropy table as generated by fit_params, then reduced to
                     just the rows for a single POS_ID.
        
        savepath ... Where to save output plot file. Extension determines image
                     format.
        
        statics_during_dynamic ... Dict of static params used during the
                     dynamic params best-fit
        
    Outputs:
        The plot image file is saved to savepath. A log string is returned
        suitable for print to stdout, stating what was done.
    '''
    fig = _init_plot()
    table.sort(DATE_SEC)
    posid = table['POS_ID'][0]
    fig.subplots_adjust(wspace=.3, hspace=.3)
    times = table[DATE_SEC]
    tick_values, tick_labels = _ticks(times)
    n_pts = len(table)
    marker = ''
    for p in param_subplot_defs:
        plt.subplot(2, 3, p['subplot'])
        for key in p['keys']:
            ax_right = None
            if p['keys'].index(key) == 1:
                ax_right = plt.twinx()
                color = 'red'
                linestyle = '--'
                if n_pts == 1:
                    marker = '^'
            else:
                color = 'blue'
                linestyle = '-'
                if n_pts == 1:
                    marker = 'v'
            y = [val * p['mult'] for val in table[key]]#.tolist()]
            plt.plot(times, y, color=color, linestyle=linestyle, marker=marker)
            if not ax_right:
                ax_left = plt.gca()
            units = f' ({p["units"]})' if p['units'] else ''
            plt.ylabel(key + units, color=color)
            if p['logscale']:
                plt.yscale('log')
            if 'ylims' in p:
                plt.ylim(p['ylims'])
            if ax_right and p['equal_scales']:
                min_y = min(ax_left.get_ylim()[0], ax_right.get_ylim()[0])
                max_y = max(ax_left.get_ylim()[1], ax_right.get_ylim()[1])
                ax_left.set_ylim((min_y, max_y))
                ax_right.set_ylim((min_y, max_y))
            plt.xticks(tick_values, tick_labels, rotation=90, horizontalalignment='center', fontsize=8)
            plt.yticks(fontsize=8)
            if 'SCALE_P_DYNAMIC' in key:
                s = statics_during_dynamic
                plt.text(min(plt.xlim()), min(plt.ylim()),
                         f' Using static params:\n'
                         f' LENGTH_R1 = {s["LENGTH_R1"]:>7.3f}, LENGTH_R2 = {s["LENGTH_R2"]:>7.3f}\n'
                         f' OFFSET_X = {s["OFFSET_X"]:>8.3f}, OFFSET_Y = {s["OFFSET_Y"]:>8.3f}\n'
                         f' OFFSET_T = {s["OFFSET_T"]:>8.3f}, OFFSET_P = {s["OFFSET_P"]:>8.3f}\n',
                         verticalalignment='bottom', fontfamily='monospace')
    analysis_date = table['ANALYSIS_DATE_DYNAMIC'][-1]
    title = f'{posid}'
    title += f'\nbest-fits to historical data'
    title += f'\nanalysis date: {analysis_date}'
    plt.suptitle(title)
    _save_and_close_plot(fig, savepath)
    return f'{posid}: plot saved to {savepath}'

def plot_passfail(binned, savepath, title='', printf=print):
    '''Plot time series of positioenr pass/fail groups, binned by error ceilings.
    
    Inputs:
        binned   ... Data structure as returned by bin_errors() function.
        
        savepath ... Where to save output plot file. Extension determines image
                     format.
        
        title    ... str to print at top of plot
        
        printf ... print function (so you can control how this module spits any messages)
        
    Outputs:
        The plot image file is saved to savepath.
    '''
    x = binned['periods']
    split = os.path.splitext(savepath)
    for p in passfail_plot_defs:
        y = binned[p['key']]
        ceilings = list(y.keys())
        colors = _colors(ceilings)
        fig = _init_plot(figsize=(15,10))
        for ceiling, counts in y.items():
            i = ceilings.index(ceiling)
            plt.plot(x, counts, label=f'fit err <= {ceiling:5.3f}',
                     color=colors[i],
                     linewidth=2)
        tick_values, tick_labels = _ticks(x)
        plt.xticks(tick_values, tick_labels, rotation=90, horizontalalignment='center')
        plt.ylabel(p['ylabel'], fontsize=14)
        plt.legend(title='THRESHOLDS (mm)')
        path = split[0] + p['suffix'] + split[1]
        plt.title(title, fontfamily='monospace')
        plt.grid(color='0.9')
        plt.minorticks_on()
        plt.gca().tick_params(axis='x', which='minor', bottom=False)
        plt.gca().tick_params(axis='y', which='minor', right=True)
        plt.gca().tick_params(axis='y', which='both', labelleft='on', labelright='on')
        _save_and_close_plot(fig, savepath=path)
        printf(f'Pass/fail plot saved to: {path}')
    
def bin_errors(table, bins=5, mode='static', printf=print):
    '''Bin the positioners over time by best-fit error.
    
    Inputs:
        table ... Astropy table as generated by fit_params, containing data
                  rows for multiple positioners.
                     
        bins  ... int or sequence of scalars. Works like "bins: arg in numpy
                  histogram(). If bins is an int, it defines the number of
                  equal-width error bins to accumulate positioner counts. If
                  bins is a sequence, it defines the bin edges, including
                  the rightmost edge, allowing for non-uniform bin widths.
        
        mode  ... 'static' or 'dynamic', indicating which best-fit error data
                  to use. (static --> SCALE_T and SCALE_P forced to 1.0)
                  
        printf ... print function (so you can control how this module spits any messages)
                     
    Outputs:
        binned ... dict data structure containing:
            
                lists...
                    'bin_ceilings' ... error ceilings
                    'periods' ... dates in seconds-since-epoch
                    'total_known' ... num POS_ID with known status (pass or fail)

                dicts of dicts...
                (keys --> bin_ceiling, subkeys --> periods)
                    'passing' ... lists of POS_ID for which fit  error <= ceiling
                    'failing' ... lists of POS_ID for which fit error > ceiling
                e.g. binned['passing'][ceiling][period] --> list of POS_ID
                    
                dicts...
                (keys --> bin_ceiling, vals --> sequences corresponding to periods)
                    'passing_counts' ... num POS_ID passing ceiling
                    'failing_counts' ... num POS_ID failing ceiling
                    'passing_fracs'  ... passing_counts / total_known
                    'failing_fracs'  ... failing_counts / total_known
                e.g. binned['passing_counts'][ceiling] --> list of values
    '''
    err_key = 'FIT_ERROR_' + mode.upper()
    min_err = min(table[err_key])
    max_err = max(table[err_key])
    try:
        n_bins = int(bins)
        edges = np.linspace(min_err, max_err, n_bins + 1)
    except:
        n_bins = len(bins) - 1
        edges = np.array(bins)
    bin_ceilings = edges[1:]
    period_duration = day_in_sec
    periods = sorted(set(table[DATE_SEC]))
    posids = set(table['POS_ID'])
    subtables = {}
    for i in range(len(periods)):
        period = periods[i]
        start = period - period_duration
        if i == 0:
            after = start <= table[DATE_SEC]
        else:
            after = start < table[DATE_SEC]
        until = period >= table[DATE_SEC]
        selected = until & after
        subtables[period] = table[selected]
    passing = {}
    failing = {}
    for ceiling in bin_ceilings:
        passing[ceiling] = {}
        failing[ceiling] = {}
        for i in range(len(periods)):
            period = periods[i]
            subtable = subtables[period]
            pass_selection = subtable[err_key] <= ceiling
            fail_selection = ~pass_selection
            pass_set = set(subtable[pass_selection]['POS_ID'])
            fail_set = set(subtable[fail_selection]['POS_ID'])
            pass_set -= fail_set  # if two conflicting entries for same posid in that data window
            if i > 0:
                known = pass_set | fail_set
                unknown = posids - known
                prev_period = periods[i-1]
                prev_pass_set = passing[ceiling][prev_period]
                prev_fail_set = failing[ceiling][prev_period]
                keep_prev_pass = prev_pass_set & unknown
                keep_prev_fail = prev_fail_set & unknown
                pass_set |= keep_prev_pass
                fail_set |= keep_prev_fail
            passing[ceiling][period] = pass_set
            failing[ceiling][period] = fail_set
        printf(f'Pass/fails binned for ceiling {ceiling:.3f} ({bin_ceilings.tolist().index(ceiling) + 1} of {len(bin_ceilings)})')
    passing_counts = {}
    failing_counts = {}
    total_known = {}
    passing_fracs = {}
    failing_fracs = {}
    for ceiling in bin_ceilings:
        passing_counts[ceiling] = []
        failing_counts[ceiling] = []
        for period in periods:
            n_pass = len(passing[ceiling][period])
            n_fail = len(failing[ceiling][period])
            passing_counts[ceiling].append(n_pass)
            failing_counts[ceiling].append(n_fail)
        passing_counts[ceiling] = np.array(passing_counts[ceiling])
        failing_counts[ceiling] = np.array(failing_counts[ceiling])
        total_known = passing_counts[ceiling] + failing_counts[ceiling]
        passing_fracs[ceiling] = passing_counts[ceiling] / total_known
        failing_fracs[ceiling] = failing_counts[ceiling] / total_known
    binned = {'bin_ceilings': bin_ceilings.tolist(),
              'periods': periods,
              'total_known': total_known.tolist(),
              'passing': passing,
              'failing': failing,
              'passing_counts': passing_counts,
              'failing_counts': failing_counts,
              'passing_fracs': passing_fracs,
              'failing_fracs': failing_fracs}
    for key in {'passing', 'failing'}:
        for ceiling in binned[key]:
            binned[key][ceiling] = {period:list(posids) for period, posids in binned[key][ceiling].items()}
    for key in {'passing_counts', 'failing_counts', 'passing_fracs', 'failing_fracs'}:
        binned[key] = {ceiling: values.tolist() for ceiling, values in binned[key].items()}
    return binned

def _init_plot(figsize=(20,10)):
    '''Internal common plot initialization function. Returns figure handle.'''
    plt.ioff()
    fig = plt.figure(figsize=figsize, dpi=150)
    plt.clf()
    return fig
    
def _save_and_close_plot(fig, savepath):
    '''Internal common plot saving and closing function. Argue the figure
    handle to close, and the path where to save the image. Extension determines
    image format.'''
    plt.savefig(savepath, bbox_inches='tight')
    plt.close(fig)
    
def _ticks(times):
    '''Internal common function to generate tick values and labels, given a
    vector of dates in seconds since epoch.'''
    tick_values = np.arange(times[0], times[-1]+day_in_sec, tick_period_days*day_in_sec)
    tick_labels = [Time(t, format='unix', out_subfmt='date').iso for t in tick_values]
    return tick_values, tick_labels

def _colors(v):
    '''Generate colors for vector v of scalar values.'''
    V = np.abs(v)
    finite = np.isfinite(V)
    Vmax = max(V[finite])
    scaled = V / Vmax * 0.7 + 0.25
    scaled[~finite] = np.sign(scaled[~finite])
    hsv = [(s, 0.7, 0.7) for s in scaled]
    colors = matplotlib.colors.hsv_to_rgb(hsv)
    return colors

# plot definitions for parameter subplots
param_subplot_defs = [
    {'keys': ['FIT_ERROR_STATIC', 'FIT_ERROR_DYNAMIC'],
     'units': 'um RMS',
     'mult': 1000,
     'subplot': 1,
     'logscale': True,
     'equal_scales': True},
            
    {'keys': ['NUM_POINTS'],
     'units': 'USED IN FIT',
     'mult': 1,
     'subplot': 4,
     'logscale': False},
            
    {'keys': ['LENGTH_R1_STATIC', 'LENGTH_R2_STATIC'],
     'units': 'mm',
     'mult': 1,
     'subplot': 2,
     'logscale': False,
     'equal_scales': True},
            
    {'keys': ['OFFSET_X_STATIC', 'OFFSET_Y_STATIC'],
     'units': 'mm',
     'mult': 1,
     'subplot': 5,
     'logscale': False,
     'equal_scales': False},
            
    {'keys': ['OFFSET_T_STATIC', 'OFFSET_P_STATIC'],
     'units': 'deg',
     'mult': 1,
     'subplot': 6,
     'logscale': False,
     'equal_scales': False},
            
    {'keys': ['SCALE_T_DYNAMIC', 'SCALE_P_DYNAMIC'],
     'units': '',
     'mult': 1,
     'subplot': 3,
     'logscale': False,
     'equal_scales': True},
    ]

# plot definitions for pass/fail subplots
passfail_plot_defs = [
    {'key': 'passing_counts',
     'ylabel': 'NUM WITHIN THRESHOLD',
     'suffix': '_pass_num'},
    
    {'key': 'failing_counts',
     'ylabel': 'NUM EXCEEDING THRESHOLD',
     'suffix': '_fail_num'},
    
    {'key': 'passing_fracs',
     'ylabel': 'FRACTION WITHIN THRESHOLD',
     'suffix': '_pass_frac'},
    
    {'key': 'failing_fracs',
     'ylabel': 'FRACTION EXCEEDING THRESHOLD',
     'suffix': '_fail_frac'},
    ]
