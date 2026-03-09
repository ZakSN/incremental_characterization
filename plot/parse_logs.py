import os
import logging
logger = logging.getLogger(__name__)
import glob

def print_experiment_results(exps):
    kl = list(exps[0].keys())
    print(' '.join(kl))
    for idx in range(len(exps)):
        for k in kl:
            try:
                data = exps[idx][k]
                if type(data) is float:
                    data = '{:.3f}'.format(data)
                print(data, end=' ')
            except KeyError:
                print('ND', end=' ')
        print()

def read_util_log_clb_luts(path, e):
    try:
        with open(path, 'r') as log:
            report = log.readlines()
            for line in report:
                if "CLB LUTs" in line:
                    e['clb_luts'] = int(line.split('|')[2])
                    return e
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return e

def read_util_log_primitives(path, e):
    prims = 0
    border_count = 0
    cs = 'start'
    try:
        with open(path, 'r') as log:
            report = log.readlines()
            for line in report:
                if cs == 'start':
                    if 'Primitives' in line:
                        cs = 'dashes'
                elif cs == 'dashes':
                    if '---' in line:
                        cs = 'border'
                        border_count = 0
                    else:
                        cs = 'start'
                elif cs == 'border':
                    if len(line.split('+')) == 5:
                        border_count += 1
                    if border_count == 2:
                        cs = 'data'
                elif cs == 'data':
                    if len(line.split('+')) == 5:
                        cs = 'done'
                    else:
                        prims += int(line.split('|')[2])
                elif cs == 'done':
                    e['primitives'] = prims
                    return e
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return e

def read_runtime_log(path, e):
    try:
        with open(path, 'r') as log:
            e['runtime'] = float(log.readline())
            return e
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return e

def read_timing_log(path, e):
    try:
        with open(path, 'r') as log:
            report = log.readlines()
            idx = -1
            min_hi = None
            max_lo = None
            while (min_hi is None) or (max_lo is None):
                if 'too low' in report[idx]:
                    max_lo = float(report[idx].split()[0])
                else:
                    min_hi = float(report[idx].split()[0])
                idx = idx -1
            fmax_hi = 1/(max_lo*1e-9)
            fmax_lo = 1/(min_hi*1e-9)
            fmax_mid = (fmax_hi + fmax_lo)/2
            rerun = False
            if 'too low' in report[-1]:
                rerun = True
            e['fmax_hi']  = fmax_hi
            e['fmax_lo']  = fmax_lo
            e['fmax_mid'] = fmax_mid
            e['rerun']    = rerun
            return e
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return e

def read_vivado_reuse_log(path, e):
    cell_line = 47
    try:
        reuse_log = open(path)
        reuse_log = reuse_log.readlines()
        cell_total = int(reuse_log[cell_line].split('|')[-2])
        percent_reuse = float(reuse_log[cell_line].split('|')[-4])
        e['cell_total'] = cell_total
        e['p_cell_reuse'] = percent_reuse/100
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return e

def read_df_reuse_log(path, e):
    try:
        reuse_log = open(path)
        reuse_log = reuse_log.readlines()
        cell_reuse = int(reuse_log[2].split(' ')[1])
        p_cell_reuse = float(reuse_log[2].split(' ')[8].replace('(', '').replace(')', ''))
        net_reuse = int(reuse_log[4].split(' ')[1])
        p_net_reuse = float(reuse_log[4].split(' ')[8].replace('(', '').replace(')', ''))
        e['reused_cells'] = cell_reuse
        e['p_cell_reuse'] = p_cell_reuse/100
        e['reused_nets']  = net_reuse
        e['p_net_reuse']  = p_net_reuse/100
        return e
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return e

def read_vivado_incremental_logs(expdir):
    # get a list of available experiment directories
    exps = [f.path for f in os.scandir(expdir) if f.is_dir()]
    # for each experiment start building a results dictionary
    exps = [{'commit': int(x.split('_')[-1]), 'path': x} for x in exps]
    # sort the list of experiment dictionaries in dependence order
    exps.sort(reverse=True, key=lambda x: x['commit'])

    for e in exps:
        e = read_util_log_clb_luts(os.path.join(e['path'], 'util.log'), e)
        e = read_util_log_primitives(os.path.join(e['path'], 'util.log'), e)
        e = read_runtime_log(os.path.join(e['path'], 'elapsed.txt'), e)
        e = read_timing_log(os.path.join(e['path'], 'tmin.txt'), e)
        e['reuse'] = os.path.isfile(os.path.join(e['path'], 'reuse.log'))
        e = read_vivado_reuse_log(os.path.join(e['path'], 'reuse.log'), e)

    return exps

def read_vivado_standard_logs(expdir):
    # get a list of available experiment directories
    exps = [f.path for f in os.scandir(expdir) if f.is_dir()]
    # for each experiment start building a results dictionary
    exps = [{'commit': int(os.path.basename(x).split('_')[0]), 'path': x} for x in exps]
    # sort the list of experiment dictionaries in dependence order
    exps.sort(reverse=True, key=lambda x: x['commit'])

    for e in exps:
        e = read_util_log_clb_luts(os.path.join(e['path'],'autoxpr', 'util.log'), e)
        e = read_timing_log(os.path.join(e['path'], 'tmin.txt'), e)
        if e['rerun'] == True:
            e['steps'] = 11
        elif e['rerun'] == False:
            e['steps'] = 10
        e = read_runtime_log(os.path.join(e['path'], 'vivado_synth.PASS'), e)
        synth_time = e['runtime']
        e = read_runtime_log(os.path.join(e['path'], 'vivado_pnr.PASS'), e)
        e['runtime'] = synth_time + e['runtime']/e['steps']

    return exps

def read_deltaFPGA_incremental_logs(expdir):
    # get a list of available experiment directories
    exps = [f.path for f in os.scandir(expdir) if f.is_dir()]
    # for each experiment start building a results dictionary
    exps = [{'commit': int(os.path.basename(x).split('_')[-1]), 'path': x} for x in exps]
    # sort the list of experiment dictionaries in dependence order
    exps.sort(reverse=True, key=lambda x: x['commit'])

    for e in exps:
        e = read_util_log_clb_luts(os.path.join(e['path'], 'after_PNR_util.log'), e)
        e = read_util_log_primitives(glob.glob(os.path.join(e['path'], '1_*_util.log'))[0], e)
        e = read_util_log_primitives(os.path.join(e['path'], 'after_PNR_util.log'), e)
        e = read_df_reuse_log(os.path.join(e['path'], 'test_report.log'), e)

    return exps
