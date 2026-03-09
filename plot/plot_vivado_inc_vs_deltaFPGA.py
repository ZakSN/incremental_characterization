import matplotlib.pyplot as plt
import argparse
import parse_logs
import numpy as np

def plot_results(v_data, d_data):
    parse_logs.print_experiment_results(v_data)
    parse_logs.print_experiment_results(d_data)
    fig, ax = plt.subplots()

    commits = [x['commit'] for x in v_data]
    x = np.arange(len(commits))
    width = 0.25
    multiplier = 0

    colours = {
        'Vivado' : 'tab:blue',
        'deltaFPGA' : 'tab:orange'
    }

    total = {
        'Vivado' : [y.get('cell_total', 0) for y in v_data],
        'deltaFPGA' : [y.get('reused_cells', 0)/y.get('p_cell_reuse', 0) for y in d_data] + [0]
    }

    reuse = {
        'Vivado' : [y.get('cell_total', 0)*y.get('p_cell_reuse', 0) for y in v_data],
        'deltaFPGA' : [0]+[y.get('reused_cells', 0) for y in d_data]
    }

    for tool, total_cell in total.items():
        offset = width*multiplier
        rects = ax.bar(x + offset,
                       total_cell,
                       width,
                       label=(tool+' - total'), 
                       alpha = 0.5,
                       color = colours[tool])
        multiplier += 1

    multiplier = 0

    for tool, cell_reuse in reuse.items():
        offset = width*multiplier
        rects = ax.bar(x + offset,
                       cell_reuse, 
                       width, 
                       label=(tool+' - reused'),
                       alpha = 1.0,
                       color = colours[tool])
        multiplier += 1

    ax.grid(visible=True, which='both', axis='y')
    ax.set_xticks(x + width, commits)
    ax.legend()
    plt.show()

    for key in total.keys():
        for series in (total, reuse):
            print(key, end=': ')
            for data in series[key]:
                print(data, end=' ')
            print()

def main():
    parser = argparse.ArgumentParser(prog='plot_vivado_inc_vs_deltaFPGA.py', description='Plot a comparison of incremental data from Vivado and deltaFPGA')
    parser.add_argument('vivado', type=str, help='Path to the root of the vivado incremental flow experiment')
    parser.add_argument('deltafpga', type=str, help='Path to the root of the deltaFPGA incremental flow experiment')
    args = parser.parse_args()

    v_data = parse_logs.read_vivado_incremental_logs(args.vivado)
    d_data = parse_logs.read_deltaFPGA_incremental_logs(args.deltafpga)
    plot_results(v_data, d_data)

if __name__ == '__main__':
    main()
