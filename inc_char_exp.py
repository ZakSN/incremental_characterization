import git
import os
import argparse
import shutil

class IncrementalCharacterizationExperiment:

    def __init__(self, gitroot):
        '''
        Initialize an incremental characterization experiment based on the
        benchmark repository located at gitroot.

        TODO: Vivado specific
        '''
        self.gitroot = gitroot

        self.branch_name = 'master'
        self.clk_period = '3'
        self.clk_name = 'clk'
        self.constraint_name = 'clk_constraint.sdc'
        self.vivado_synth_args = '-verilog_define EXT_F_DISABLE -mode out_of_context'

        self.reference_script = 'build_reference_dcp.tcl'

        self.bmarkname = os.path.basename(os.path.normpath(gitroot))
        self.expdir = self.bmarkname + '_inc_exp'
        self.projdir = os.path.join(self.expdir, 'xpr')
        self.datadir = os.path.join(self.expdir, 'dcp')
        self.srcdir = os.path.join(self.projdir, 'src')

        # get a handle for the benchmark repository and collect commits
        self.repo = git.Repo(gitroot)
        self.commits = list(self.repo.iter_commits(self.branch_name))

    def run_experiment(self):
        self._build_experiment_directory()

        self._build_reference_implementation()

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
        fileset = self._get_fileset_from_commit(commit.tree)
        fileset = [os.path.join(self.gitroot, f) for f in fileset]

        # add a constraint file
        constraint = ['create_clock -name '+
                     self.clk_name+
                     ' -period '+
                     self.clk_period+
                     ' [get_ports '+
                     self.clk_name+
                     ']']
        self._write_file(constraint, os.path.join(self.srcdir, self.constraint_name))

        # copy all the files from the commit of interest to the new project dir
        for f in fileset:
            shutil.copy(f, self.srcdir)

    def _build_reference_implementation(self):
        '''
        Build a reference checkpoint
        TODO: vivado specific
        '''
        # initialize the project directory with the oldest commit
        self._init_projdir_from_commit_index(-1)

        # write a tcl script to build a reference implementation
        relative_srcdir = os.path.basename(os.path.normpath(self.srcdir))
        relative_constraint = os.path.join(relative_srcdir, self.constraint_name)
        relative_datadir = os.path.join('..',os.path.basename(os.path.normpath(self.datadir)))
        outputdir = 'reference'
        script = [
            'file mkdir '+outputdir,
            'create_project -part xcvu3p-ffvc1517-3-e '+outputdir+' '+outputdir,
            'add_files '+relative_srcdir,
            'import_files -fileset constrs_1 -force -norecurse '+relative_constraint,
            'import_files -force',
            'set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {'+self.vivado_synth_args+'} -objects [get_runs synth_1]',
            'set_property AUTO_INCREMENTAL_CHECKPOINT 1 [get_runs impl_1]',
            'set_property AUTO_INCREMENTAL_CHECKPOINT.DIRECTORY . [get_runs impl_1]',
            'launch_runs synth_1',
            'wait_on_run synth_1',
            'launch_runs impl_1',
            'wait_on_run impl_1',
            'open_run impl_1',
            'write_checkpoint '+os.path.join(relative_datadir, 'reference.dcp'),
            'exit',
            ]

        self._write_file(script, os.path.join(self.projdir, self.reference_script))

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
