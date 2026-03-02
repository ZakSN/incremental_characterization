import os
import logging
logger = logging.getLogger(__name__)
import matplotlib.pyplot as plt
import argparse

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

def read_util_log(path):
    try:
        with open(path, 'r') as log:
            report = log.readlines()
            for line in report:
                if "CLB LUTs" in line:
                    return int(line.split('|')[2])
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return None

def read_runtime_log(path):
    try:
        with open(path, 'r') as log:
            return float(log.readline())
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return None

def read_timing_log(path):
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
            return fmax_hi, fmax_lo, fmax_mid, rerun
    except FileNotFoundError:
        logger.warning('Could not open '+path)
    return None, None, None, None

def read_reuse_log(expdir):
    cell_reuse = 0
    percent_reuse = 0.0
    try:
        reuse_log = open(expdir)
        reuse_log = reuse_log.readlines()
        cell_reuse = int(reuse_log[48].split('|')[-2])
        percent_reuse = float(reuse_log[48].split('|')[-4])
    except:
        pass
    return cell_reuse, percent_reuse


def read_incremental_logs(expdir):
    # get a list of available experiment directories
    exps = [f.path for f in os.scandir(expdir) if f.is_dir()]
    # for each experiment start building a results dictionary
    exps = [{'commit': int(x.split('_')[-1]), 'path': x} for x in exps]
    # sort the list of experiment dictionaries in dependence order
    exps.sort(reverse=True, key=lambda x: x['commit'])

    for e in exps:
        # Collect resource utilization for experiment e
        e['area'] = read_util_log(os.path.join(e['path'], 'util.log'))
        # Collect runtime for experiment e
        e['runtime'] = read_runtime_log(os.path.join(e['path'], 'elapsed.txt'))
        # Collect timing information for experiment e
        e['fmax_hi'], e['fmax_lo'], e['fmax_mid'], e['steps'] = read_timing_log(os.path.join(e['path'], 'tmin.txt'))
        # Check if this commit is incremental or not
        e['reuse'] = os.path.isfile(os.path.join(e['path'], 'reuse.log'))
        # Reuse stats
        e['cell_reuse'], e['percent_reuse'] = read_reuse_log(os.path.join(e['path'], 'reuse.log'))

    return exps

def read_standard_logs(expdir):
    # get a list of available experiment directories
    exps = [f.path for f in os.scandir(expdir) if f.is_dir()]
    # for each experiment start building a results dictionary
    exps = [{'commit': int(os.path.basename(x).split('_')[0]), 'path': x} for x in exps]
    # sort the list of experiment dictionaries in dependence order
    exps.sort(reverse=True, key=lambda x: x['commit'])

    for e in exps:
        # Collect resource utilization for experiment e
        e['area'] = read_util_log(os.path.join(e['path'],'autoxpr', 'util.log'))
        # Collect timing information for experiment e
        e['fmax_hi'], e['fmax_lo'], e['fmax_mid'], e['steps'] = read_timing_log(os.path.join(e['path'], 'tmin.txt'))
        if e['steps'] == True:
            e['steps'] = 11
        elif e['steps'] == False:
            e['steps'] = 10
        # Compute runtime esitmate for experiment e
        synth_time = read_runtime_log(os.path.join(e['path'], 'vivado_synth.PASS'))
        pnr_time = read_runtime_log(os.path.join(e['path'], 'vivado_pnr.PASS'))
        e['runtime'] = synth_time + pnr_time/e['steps']

    return exps

def plot_area(ax, inc_data, std_data):
    x = [e['commit'] for e in inc_data]
    y_inc = [e['area'] for e in inc_data]
    y_std = [e['area'] for e in std_data]
    ax.scatter(x, y_inc, marker='.', label='inc')
    ax.scatter(x, y_std, marker='.', label='std')
    ax.set_ylabel("Area [# LUTs]")

def plot_cumulative_runtime(ax, inc_data, std_data):
    x = [e['commit'] for e in inc_data]
    t_inc = [e['runtime'] for e in inc_data]
    t_std = [e['runtime'] for e in std_data]

    sigma_t_inc = [t_inc[0]]
    sigma_t_std = [t_std[0]]
    for idx in range(len(t_inc)-1):
        sigma_t_inc.append(t_inc[idx+1]+sigma_t_inc[idx])
        sigma_t_std.append(t_std[idx+1]+sigma_t_std[idx])

    ax.scatter(x, sigma_t_inc, marker='.', label='inc')
    ax.scatter(x, sigma_t_std, marker='.', label='std')
    ax.set_ylabel("IRT [s]")

def plot_fmax(ax, inc_data, std_data):
    x = [e['commit'] for e in inc_data]
    fmax_inc = [e['fmax_mid'] for e in inc_data]
    fmax_inc_error = [e['fmax_hi'] - e['fmax_lo'] for e in inc_data]
    fmax_std = [e['fmax_mid'] for e in std_data]
    fmax_std_error = [e['fmax_hi'] - e['fmax_lo'] for e in std_data]

    ax.errorbar(x, fmax_inc, fmax_inc_error, fmt='.', label='inc')
    ax.errorbar(x, fmax_std, fmax_std_error, fmt='.', label='std')
    ax.set_ylabel("$f_{max}$ [Hz]")

def plot_cell_reuse(ax, inc_data):
    x = [e['commit'] for e in inc_data]
    cell_reuse = [e['cell_reuse'] for e in inc_data]

    ax.scatter(x, cell_reuse, marker='.', label='Vivado')
    ax.set_ylabel("# Cells Reused")

def plot_percent_reuse(ax, inc_data):
    x = [e['commit'] for e in inc_data]
    percent_reuse = [e['percent_reuse'] for e in inc_data]

    ax.scatter(x, percent_reuse, marker='.', label='Vivado')
    ax.set_ylim(0.0, 100.0)
    ax.set_ylabel("% Cells Reused")

def plot_results(inc_data, std_data):
    fig, axs = plt.subplots(3,1)
    plot_area(axs[0], inc_data, std_data)
    plot_fmax(axs[1], inc_data, std_data)
    plot_cumulative_runtime(axs[2], inc_data, std_data)
    rebuilds = [e['commit'] for e in inc_data if not e['reuse']]
    for ax in axs:
        ax.invert_xaxis()
        for x in rebuilds:
            ax.axvline(x=x, color='tab:gray')
        ax.grid(visible=True, which='both')
        ax.legend()
    axs[-1].set_xlabel("Commit Number")
    plt.show()

def plot_reuse(inc_data):
    fig, axs = plt.subplots(2,1)
    plot_cell_reuse(axs[0], inc_data)
    plot_percent_reuse(axs[1], inc_data)
    rebuilds = [e['commit'] for e in inc_data if not e['reuse']]
    for ax in axs:
        ax.invert_xaxis()
        for x in rebuilds:
            ax.axvline(x=x, color='tab:gray')
        ax.grid(visible=True, which='both')
        ax.legend()
    axs[-1].set_xlabel("Commit Number")
    plt.show()

def main():
    parser = argparse.ArgumentParser(prog='plot_results.py', description='Plot a comparison of incremental and standard data')
    parser.add_argument('std_exp', type=str, help='Path to the root of the standard flow experiment')
    parser.add_argument('inc_exp', type=str, help='Path to the root of the incremental flow experiment')
    args = parser.parse_args()

    inc_data = read_incremental_logs(args.inc_exp)
    std_data = read_standard_logs(args.std_exp)
    plot_results(inc_data, std_data)

    plot_reuse(inc_data)

if __name__ == '__main__':
    main()
