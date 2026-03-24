import matplotlib as mpl
import matplotlib.pyplot as plt
import argparse
import parse_logs
import numpy as np

def grouped_stacked_bar_chart(ax, commits, base_mask, total, reuse, colours, titles):
    x = np.arange(len(commits))
    width = 0.25
    multiplier = 0

    for tool in base_mask.keys():
        total[tool] = [y[0]*y[1] for y in list(zip(total[tool], base_mask[tool]))]    
        reuse[tool] = [y[0]*y[1] for y in list(zip(reuse[tool], base_mask[tool]))]    
    
    for tool, total_obj in total.items():
        offset = width*multiplier
        rects = ax.bar(x + offset,
                       total_obj,
                       width,
                       label=(tool+' - total'), 
                       alpha = 0.5,
                       color = colours[tool])
        multiplier += 1

    multiplier = 0

    for tool, reuse_obj in reuse.items():
        offset = width*multiplier
        rects = ax.bar(x + offset,
                       reuse_obj, 
                       width, 
                       label=(tool+' - reused'),
                       alpha = 1.0,
                       color = colours[tool])
        multiplier += 1

    ax.grid(visible=True, which='both', axis='y')
    xticks = []
    for idx in range(len(commits)):
        if idx % 5 == 0:
            xticks.append(commits[idx])
        else:
            xticks.append('')
    ax.set_xticks(x + width, xticks)
    ax.set_title(titles[0])
    ax.set_xlabel(titles[1])
    ax.set_ylabel(titles[2])

def colour_chart(ax, commits, base_mask, total, reuse, colours, titles):
    x = np.arange(len(commits))
    width = 1
    multiplier = 0

    for tool in base_mask.keys():
        total[tool] = [y[0]*y[1] for y in list(zip(total[tool], base_mask[tool]))]    
        reuse[tool] = [y[0]*y[1] for y in list(zip(reuse[tool], base_mask[tool]))]    
   
    direction = {
        'Vivado' : -1,
        'deltaFPGA' : 1
    }

    def calc_reuse(y):
        if y[1] == 0:
            return 0
        return min(y[0]/y[1], 1.0)

    p_reuse = {
        'Vivado' : [calc_reuse(y) for y in list(zip(reuse['Vivado'], total['Vivado']))],
        'deltaFPGA' : [calc_reuse(y) for y in list(zip(reuse['deltaFPGA'], total['deltaFPGA']))]
    }

    r_data = list(filter(lambda x: x>0, p_reuse['Vivado'] + p_reuse['deltaFPGA']))
    min_reuse = min(r_data)
    max_reuse = max(r_data)

    norm = mpl.colors.Normalize(vmin=min_reuse, vmax=max_reuse, clip=False)

    print(min_reuse, max_reuse)

    cmap = plt.colormaps['viridis_r']

    for tool in total.keys():
        mag = [y*direction[tool] for y in total[tool]]
        for i in range(len(total[tool])):
            p = norm(p_reuse[tool][i])
            rects = ax.bar(x[i], mag[i], width,
                           color=cmap(p))

    ax.grid(visible=True, which='both', axis='y')
    xticks = []
    for idx in range(len(commits)):
        if idx % 5 == 0:
            xticks.append(commits[idx])
        else:
            xticks.append('')
    ax.set_xticks(x + width, xticks)

    yticks = ax.get_yticks()
    ytick_labels = [int(abs(y)) for y in yticks]
    ax.set_yticks(yticks, ytick_labels)

    ax.axhline(y=0, color='black')

    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap),
                      ax=ax, label="Reuse (%)")
    
    ax.set_title(titles[0])
    ax.set_xlabel(titles[1])
    #ax.set_ylabel(titles[2]) 
    min_pixel = ax.get_tightbbox().p0
    inv = ax.transData.inverted()
    min_data = inv.transform(min_pixel)
    for tool in direction.keys():
        if direction[tool] > 0:
            y = max(yticks)/2
        else:
            y = min(yticks)/2
        ax.text(min_data[0], y, s=tool, ha='right', va='center',
                rotation='vertical')


def plot_results(v_data, d_data):
    #parse_logs.print_experiment_results(v_data)
    #parse_logs.print_experiment_results(d_data)
    fig, axs = plt.subplots(2, 1, layout='constrained')

    commits = [x['commit'] for x in v_data]

    colours = {
        'Vivado' : 'tab:blue',
        'deltaFPGA' : 'tab:orange'
    }

    cell_total = {
        'Vivado' : [y.get('primitives', 0) for y in v_data],
        'deltaFPGA' : [y.get('last_cell_total', 0) for y in d_data] + [0]
    }

    cell_reuse = {
        'Vivado' : [y.get('cell_total', 0)*y.get('p_cell_reuse', 0) for y in v_data],
        'deltaFPGA' : [0] + [y.get('reused_cells', 0) for y in d_data]
    }

    net_total = {
        'Vivado' : [y.get('net_total', 0) for y in v_data],
        'deltaFPGA' : [y.get('last_net_total', 0) for y in d_data] + [0]
    }
    
    net_reuse = {
        'Vivado' : [y.get('net_total', 0)*y.get('p_net_reuse', 0) for y in v_data],
        'deltaFPGA' : [0] + [y.get('reused_nets', 0) for y in d_data]
    }

    base_mask = {
        'Vivado' : [y.get('reuse', False) for y in v_data],
        'deltaFPGA' : [False] + [y.get('reuse', False) for y in d_data[1:]] + [True]
    }

    for y in d_data:
        try:
            y['reuse']
        except KeyError:
            print("Failed During RE: "+y['path'])

    #grouped_stacked_bar_chart(axs[0], commits, base_mask, cell_total, cell_reuse, colours, ('Commit vs. Cell Count', 'Commmit', '# Cells'))
    #grouped_stacked_bar_chart(axs[1], commits, base_mask, net_total, net_reuse, colours, ('Commit vs. Net Count', 'Commmit', '# Nets'))
    
    colour_chart(axs[0], commits, base_mask, cell_total, cell_reuse, colours, ('Commit vs. Cell Count', 'Commmit', '# Cells'))
    colour_chart(axs[1], commits, base_mask, net_total, net_reuse, colours, ('Commit vs. Net Count', 'Commmit', '# Nets'))

    axs[0].legend()
    plt.show()
    '''
    for e in v_data:
        vprim = e.get('primitives', 0)
        vtotl = e.get('cell_total', 0)
        print(vprim, vtotl, vtotl - vprim)
    '''

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
