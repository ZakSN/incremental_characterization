import git
import os
import argparse
import shutil
import subprocess
import math
import time
import configparser

class IncrementalCharacterizationExperiment:

    def __init__(self, benchmark_desc_file, start_commit=None, stop_commit=None):
        '''
        Initialize an incremental characterization experiment based on the
        benchmark repository located at gitroot.
        '''

        # Read a chronbench benchmark description file
        benchmark_desc = self._parse_benchmark_desc_file(benchmark_desc_file)
        self.name = benchmark_desc.sections()[0]

        # Initialize benchmark settings
        self.benchmark         = benchmark_desc[self.name]
        self.branch_name       = self.benchmark['branch']
        self.clk_name          = self.benchmark['clock']
        self.vivado_synth_args = self.benchmark['vivado-synth-args']

        # Assume the benchmark repo is located in the same directory as the desc
        self.gitroot = benchmark_desc_file.split('.')[0]

        # Set default names for project directories
        self.expdir = self.name + '_inc_exp'
        self.srcdir = 'src'
        self.tmin_file = 'tmin.txt'
        self.commitdirs = []

        # Experimental settings
        self.fmax_search_steps = 2
        self.start_commit = start_commit
        self.stop_commit = stop_commit

    def clean_experiment(self):
        '''
        Remove the directory structure for the incremental characterization experiment
        '''
        if not os.path.isdir(self.expdir):
            print("QUITTING "+self.expdir+" does not exist!")
            exit()

        shutil.rmtree(self.expdir)

    def run_experiment(self):
        '''
        Run an incremental characterization experiment for the current benchmark
        '''
        self._initialize_experiment()

        # The root commit is the oldes commit in the benchmark history
        root_commit = len(self.commits)-1

        # If start and stop commits were not specified run the experiment across
        # the entire available design history.
        if self.stop_commit is None:
            self.stop_commit = 0
        if self.start_commit is None:
            self.start_commit = root_commit

        # check validity of start and stop commits
        if self.stop_commit > self.start_commit:
            print("QUITTING: stop_commit should be younger than start_commit")
            exit()
        if self.stop_commit < 0:
            print("QUITTING: stop_commit invalid")
            exit()
        if self.start_commit > root_commit:
            print("QUITTING: start_commit invalid")
            exit()

        # TODO: mechanism to choose other tools
        tool_fn = self._run_vivado_implementation
        def compute_extra_args(cidx):
            if cidx == root_commit:
                return {'ref_dcp': None}
            else:
                prev_commit = os.path.basename(self.commitdirs[cidx+1])
                prev_dcp = os.path.join(prev_commit,prev_commit+'.dcp')
                return {'ref_dcp': prev_dcp}

        for cidx in reversed(range(self.stop_commit, self.start_commit+1)):
            if os.path.isfile(os.path.join(self.commitdirs[cidx],self.tmin_file)):
                print("Skipping commit "+str(cidx))
            else:
                if cidx == root_commit:
                    print("Building root commit")
                    self._fmax_search(cidx, tool_fn, compute_extra_args(cidx))
                else:
                    if os.path.isfile(os.path.join(self.commitdirs[cidx+1],self.tmin_file)):
                        print("Building commit: "+str(cidx))
                        self._fmax_search(cidx, tool_fn, compute_extra_args(cidx))
                    else:
                        print("QUITTING: Could not build commit "+str(cidx)+" since ancestor incomplete")
                        exit()

    def _parse_benchmark_desc_file(self, benchmark_desc_file):
        '''
        Read a benchmark description file. Return a populated config object.
        '''
        config = configparser.ConfigParser()
        config.read(benchmark_desc_file)
        return config

    def _initialize_experiment(self):
        '''
        Create an experiment directory if it does not already exist, and
        create projects for each commit in the benchmark if they do not already
        exist.
        '''
        # Create the experiment directory
        if not os.path.isdir(self.expdir):
            os.makedirs(self.expdir)
        else:
            print("Found existing "+self.expdir+" experiment directory")
            print("\tPerhaps you meant to run with `--clean`?")

        # get a handle for the benchmark repository and collect commits
        self.repo = git.Repo(self.gitroot)
        self.commits = list(self.repo.iter_commits(self.branch_name))
        print("Found "+str(len(self.commits))+" commits in "+self.name)

        # create names for each commit level project
        digits = math.ceil(math.log(len(self.commits), 10))
        digit_fmt = "{:0"+str(digits)+"d}"

        new_commit_dirs = 0
        existing_commit_dirs = 0
        for cidx in range(len(self.commits)):
            commit_name = digit_fmt.format(cidx)
            self.commitdirs.append(os.path.join(self.expdir, self.branch_name+'_'+commit_name))
            this_commitdir = self.commitdirs[-1]
            if not os.path.isdir(this_commitdir):
                os.makedirs(this_commitdir)
                new_commit_dirs += 1
                self._initialize_commit(cidx, this_commitdir)
            else:
                existing_commit_dirs += 1

        print("Found "+str(existing_commit_dirs)+" existing commit directories")
        print("Initialized "+str(new_commit_dirs)+" new commit directories")

    def _initialize_commit(self, cidx, commitdir):
        '''
        Initialize commitdir with the contents of self.commits[cidx]
        '''
        commit = self.commits[cidx]

        # checkout the commit of interest and get a file list
        self.repo.git.checkout(commit)
        fileset = self._get_fileset_from_commit(commit.tree, fileset=[])
        fileset = [os.path.join(self.gitroot, f) for f in fileset]

        # create a source directory for the current project
        this_srcdir = os.path.join(commitdir, self.srcdir)
        os.makedirs(this_srcdir)

        # copy all the files from the commit of interest to the new project dir
        for f in fileset:
            shutil.copy(f, this_srcdir)

    def _get_fileset_from_commit(self, root, level=0, fileset=[]):
        '''
        Recurse from the root tree (commit) to collect the fileset at this tree
        '''
        for entry in root:
            if entry.type == 'blob':
                fileset.append(entry.path)
            if entry.type == 'tree':
                fileset = self._get_fileset_from_commit(entry, level + 1, fileset)
        return fileset

    def _write_file(self, contents, filename):
        '''
        Write each string from the list contets to the filename
        '''
        with open(filename, 'w') as f:
            for line in contents:
                f.write(line+'\n')

    def _check_log(self, logfile, success_msg):
        '''
        Check each line of logfile to see if it contains success_msg.
        '''
        with open(logfile, 'r') as log:
            loglines = log.readlines()
        for line in loglines:
            if success_msg in line:
                return True
        return False

    def _fmax_search(self, commit_idx, tool_fn, extra_tool_args):
        '''
        Run binary search to find the fmax of the design at the commit_idx, which
        may optionally be an incremental implementation
        '''

        # run binary search to determine fmax
        last_guess_too_high = None
        coef = 0.5
        guesses = []
        period_ns = 3
        for step in range(self.fmax_search_steps):
            print('\tT SEARCH: Running step '+str(step)+' of '+str(self.fmax_search_steps))
            # guess Tmin == period_ns
            success = tool_fn(commit_idx, period_ns, **extra_tool_args)

            if success: # period_ns too high
                guesses.append(str(period_ns)+' too high')
                if last_guess_too_high == False:
                    coef = coef/2
                period_ns = period_ns*(1-coef)
                last_guess_too_high = True
            else: # period_ns too low
                guesses.append(str(period_ns)+' too low')
                if last_guess_too_high == True:
                    coef = coef/2
                period_ns = period_ns*(1+coef)
                last_guess_too_high = False

        # we don't want to report area numbers if timing wasn't met. therefore
        # may need to re-run last 'too high' guess to get a valid area number:
        if last_guess_too_high == False:
            for idx in reversed(range(len(guesses))):
                tmin = float(guesses[idx].split()[0])
                success = guesses[idx].split()[-1]
                if success == 'high':
                    break
            print('\tT SEARCH: Last guess failed, re-running last successful')
            tool_fn(commit_idx, period_ns, **extra_tool_args)
        else:
            print('\tT SEARCH: Last guess successful')

        # record the value of Tmin found
        self._write_file(guesses, os.path.join(self.commitdirs[commit_idx], self.tmin_file))

    def _run_vivado_implementation(self, commit_idx, period_ns, ref_dcp=None):
        '''
        Use Vivado to build a checkpoint from commit_idx, constrained with
        period_ns, and optionally based on ref_dcp.

        if ref_dcp is None build using the reference flow
        Otherwise attempt to build an incremental checkpoint based on ref_dcp

        returns True if timing constraints were met, False otherwise.
        '''

        # filenames and paths
        constraint_name = 'vivado_sdc.sdc'
        build_script_name = 'vivado_build.tcl'

        this_commitdir = self.commitdirs[commit_idx]
        this_constraint = os.path.join(this_commitdir, constraint_name)

        run_name = os.path.basename(this_commitdir)

        # add a constraint file
        constraint = ['create_clock -name '+
                     self.clk_name+
                     ' -period '+
                     '{:.2f}'.format(period_ns)+
                     ' [get_ports '+
                     self.clk_name+
                     ']']
        self._write_file(constraint, this_constraint)

        add_ref_lines = False
        add_inc_lines = False
        if ref_dcp is None:
            add_ref_lines = True
            relative_refdcp = ''
        else:
            add_inc_lines = True
            relative_refdcp = os.path.join('..', ref_dcp)

        script = [
            'file mkdir '+run_name,
            'create_project -force -part xcvu3p-ffvc1517-3-e '+run_name+' '+run_name,
            'add_files '+self.srcdir,
            'import_files -fileset constrs_1 -force -norecurse '+constraint_name,
            'import_files -force',
            'set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {'+self.vivado_synth_args+'} -objects [get_runs synth_1]',
            *([ # build reference implementation
            'set_property AUTO_INCREMENTAL_CHECKPOINT 1 [get_runs impl_1]',
            'set_property AUTO_INCREMENTAL_CHECKPOINT.DIRECTORY . [get_runs impl_1]',
            ]*add_ref_lines),
            *([ # build incremental implementation
            'set_property incremental_checkpoint '+relative_refdcp+' [get_runs impl_1]',
            ]*add_inc_lines),
            'launch_runs synth_1',
            'wait_on_run synth_1',
            'launch_runs impl_1',
            'wait_on_run impl_1',
            'open_run impl_1',
            'write_checkpoint -force '+run_name+'.dcp',
            # reporting
            'report_timing -file timing.log',
            'report_utilization -file util.log',
            *([
            'report_incremental_reuse -file reuse.log',
            ]*add_inc_lines),
            'exit',
            ]
        self._write_file(script, os.path.join(this_commitdir, build_script_name))

        # run Vivado and measure how long it takes to complete
        start = time.time()
        subprocess.run(['vivado', '-mode', 'tcl', '-source', build_script_name], cwd=this_commitdir, capture_output=True)
        stop = time.time()

        elapsed = stop - start
        self._write_file([str(elapsed)], os.path.join(this_commitdir, 'elapsed.txt'))

        success = self._check_log(os.path.join(this_commitdir,'timing.log'), 'Slack (MET) :')
        return success

def main():
    parser = argparse.ArgumentParser(
        prog = 'inc_char_exp.py',
        description = 'Run an incremental characterization experiment on a Chronbench-style benchmark'
    )

    parser.add_argument('benchmark', type=str, help='Path to the benchmark to characterize')
    parser.add_argument('-c', '--clean', action='store_true', help='Cleanup the characterization experiment associated with the named benchmark')
    parser.add_argument('--start_commit', type=int, default=None, help='Index of commit to start experiment at')
    parser.add_argument('--stop_commit', type=int, default=None, help='Index of commit to stop experiment at')

    args = parser.parse_args()

    ice = IncrementalCharacterizationExperiment(args.benchmark, args.start_commit, args.stop_commit)

    if args.clean:
        ice.clean_experiment()
    else:
        ice.run_experiment()

if __name__ == '__main__':
    main()
