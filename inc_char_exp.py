import git
import os
import argparse
import shutil
import subprocess

class IncrementalCharacterizationExperiment:

    def __init__(self, gitroot):
        '''
        Initialize an incremental characterization experiment based on the
        benchmark repository located at gitroot.

        TODO: Vivado specific
        '''
        self.gitroot = gitroot

        self.branch_name = 'master'
        self.clk_name = 'clk'
        self.constraint_name = 'clk_constraint.sdc'
        self.vivado_synth_args = '-verilog_define EXT_F_DISABLE -mode out_of_context'

        self.reference_script = 'build_reference_dcp.tcl'

        self.bmarkname = os.path.basename(os.path.normpath(gitroot))
        self.expdir = self.bmarkname + '_inc_exp'
        self.projdir = os.path.join(self.expdir, 'xpr')
        self.datadir = os.path.join(self.expdir, 'dcp')
        self.srcdir = os.path.join(self.projdir, 'src')

        self.fmax_search_steps = 2

        # get a handle for the benchmark repository and collect commits
        self.repo = git.Repo(gitroot)
        self.commits = list(self.repo.iter_commits(self.branch_name))
        print("Found "+str(len(self.commits))+" commits")

    def run_experiment(self):
        self._build_experiment_directory()

        current_commit = len(self.commits) - 1

        self._fmax_search('reference', current_commit)
        current_commit -= 1
        self._fmax_search('incremental98', current_commit, 'reference.dcp')
        current_commit -= 1
        self._fmax_search('incremental97', current_commit, 'incremental98.dcp')

        #self._run_vivado_implementation(current_commit)
        #current_commit -= 1
        #self._run_vivado_implementation(current_commit, 'reference.dcp')

        #self._run_vivado_implementation(46, 'incremental98.dcp')

    def clean_experiment(self):
        '''
        Remove the directory structure for the incremental characterization experiment
        '''
        if not os.path.isdir(self.expdir):
            print("QUITTING "+self.expdir+" does not exist!")
            exit()

        shutil.rmtree(self.expdir)

    def _write_file(self, contents, filename):
        '''
        Write each string from the list contets to the filename
        '''
        with open(filename, 'w') as f:
            for line in contents:
                f.write(line+'\n')

    def _build_experiment_directory(self):
        '''
        Set up a directory structure for the incremental characterization experiment
        '''
        if not os.path.isdir(self.expdir):
            os.makedirs(self.expdir)
            os.makedirs(self.datadir)
        else:
            print("QUITTING: "+self.expdir+" already exists!")
            exit()

    def _init_projdir_from_commit_index(self, cidx):
        '''
        Overwrite the projdir with a the contents of a new commit
        '''
        commit = self.commits[cidx]

        # remove the old project directory
        if os.path.isdir(self.projdir):
            shutil.rmtree(self.projdir)

        # create a new project directory
        os.makedirs(self.projdir)
        os.makedirs(self.srcdir)

        # checkout the commit of interest and get a file list
        self.repo.git.checkout(commit)
        fileset = self._get_fileset_from_commit(commit.tree, fileset=[])
        fileset = [os.path.join(self.gitroot, f) for f in fileset]

        # copy all the files from the commit of interest to the new project dir
        for f in fileset:
            shutil.copy(f, self.srcdir)

    def _run_vivado_implementation(self, run_name, commit_idx, clk_period, ref_dcp=None):
        '''
        Build a checkpoint from the commit_idx. If ref_dcp is not provided build
        a reference checkpoint, otherwise build an incremental checkpoint based
        on the reference. Constrain the clk with clk_period.

        TODO: vivado specific
        '''
        # initialize the project directory with the oldest commit
        self._init_projdir_from_commit_index(commit_idx)

        # add a constraint file
        constraint = ['create_clock -name '+
                     self.clk_name+
                     ' -period '+
                     '{:.2f}'.format(clk_period)+
                     ' [get_ports '+
                     self.clk_name+
                     ']']
        self._write_file(constraint, os.path.join(self.srcdir, self.constraint_name))

        # figure out relative paths to required directories
        relative_srcdir = os.path.basename(os.path.normpath(self.srcdir))
        relative_constraint = os.path.join(relative_srcdir, self.constraint_name)
        relative_datadir = os.path.join('..',os.path.basename(os.path.normpath(self.datadir)),run_name)
        relative_refdcp = 'null'

        add_ref_lines = False
        add_inc_lines = False
        if ref_dcp is None:
            add_ref_lines = True
        else:
            add_inc_lines = True
            relative_refdcp = os.path.join(relative_datadir, os.path.basename(ref_dcp))

        script = [
            'file mkdir '+run_name,
            'create_project -part xcvu3p-ffvc1517-3-e '+run_name+' '+run_name,
            'add_files '+relative_srcdir,
            'import_files -fileset constrs_1 -force -norecurse '+relative_constraint,
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
            'write_checkpoint -force '+os.path.join(relative_datadir, run_name+'.dcp'),
            # reporting
            'report_timing -file '+os.path.join(relative_datadir, 'timing.log'),
            'report_utilization -file '+os.path.join(relative_datadir, 'util.log'),
            *([
            'report_incremental_reuse -file '+os.path.join(relative_datadir, 'reuse.log'),
            ]*add_inc_lines),
            'exit',
            ]
        self._write_file(script, os.path.join(self.projdir, self.reference_script))
        subprocess.run(['vivado', '-mode', 'tcl', '-source', self.reference_script], cwd=self.projdir, capture_output=True)
        shutil.copy(os.path.join(self.projdir, ('vivado.log')), os.path.join(self.datadir, run_name))

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

    def _fmax_search(self, run_name, commit_idx, ref_dcp=None):
        '''
        Run binary search to find the fmax of the design at the commit_idx, which
        may optionally be an incremental implementation of the ref_dcp
        '''

        # run binary search to determine fmax
        last_guess_too_high = None
        coef = 0.5
        guesses = []
        period_ns = 3
        for _ in range(self.fmax_search_steps):

            # guess Tmin == period_ns
            self._run_vivado_implementation(run_name, commit_idx, period_ns, ref_dcp)

            success = self._check_log(os.path.join(self.datadir,run_name,'timing.log'), 'Slack (MET) :')

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
            self._run_vivado_implementation(run_name, commit_idx, tmin, ref_dcp)
            print('\tPNR: Last guess failed, re-running last successful')
        else:
            print('\tPNR: Last guess successful')

        # record the value of Tmin found
        self._write_file(guesses, os.path.join(self.datadir,run_name, 'tmin.txt'))

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

def main():
    parser = argparse.ArgumentParser(
        prog = 'inc_char_exp.py',
        description = 'Run an incremental characterization experiment on a Chronbench-style benchmark'
    )

    parser.add_argument('benchmark', type=str, help='Path to the benchmark to characterize')
    parser.add_argument('-c', '--clean', action='store_true', help='Cleanup the characterization experiment associated with the named benchmark')

    args = parser.parse_args()

    ice = IncrementalCharacterizationExperiment(args.benchmark)

    if args.clean:
        ice.clean_experiment()
    else:
        ice.run_experiment()

if __name__ == '__main__':
    main()
