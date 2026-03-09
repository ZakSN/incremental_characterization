import matplotlib.pyplot as plt
import argparse
import parse_logs

def plot_area(ax, inc_data, std_data):
    x = [e['commit'] for e in inc_data]
    y_inc = [e['clb_luts'] for e in inc_data]
    y_std = [e['clb_luts'] for e in std_data]
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
    cell_reuse = [e.get('cell_total', 0)*e.get('p_cell_reuse', 0) for e in inc_data]

    ax.scatter(x, cell_reuse, marker='.', label='Vivado')
    ax.set_ylabel("# Cells Reused")

def plot_percent_reuse(ax, inc_data):
    x = [e['commit'] for e in inc_data]
    percent_reuse = [e.get('p_cell_reuse', 0)*100 for e in inc_data]

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
    parser = argparse.ArgumentParser(prog='plot_vivado_std_vs_inc.py', description='Plot a comparison of incremental and standard data for Vivado')
    parser.add_argument('std_exp', type=str, help='Path to the root of the standard flow experiment')
    parser.add_argument('inc_exp', type=str, help='Path to the root of the incremental flow experiment')
    args = parser.parse_args()

    inc_data = parse_logs.read_vivado_incremental_logs(args.inc_exp)
    std_data = parse_logs.read_vivado_standard_logs(args.std_exp)
    plot_results(inc_data, std_data)

    plot_reuse(inc_data)

if __name__ == '__main__':
    main()
