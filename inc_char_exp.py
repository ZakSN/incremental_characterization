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
        self.bmarkname = os.path.basename(os.path.normpath(gitroot))
        self.expdir = self.bmarkname + '_inc_exp'
        self.projdir = os.path.join(self.expdir, 'xpr')
        self.datadir = os.path.join(self.expdir, 'dcp')
        self.srcdir = os.path.join(self.projdir, 'src')

        # get a handle for the benchmark repository and collect commits
        self.repo = git.Repo(gitroot)
        self.commits = list(self.repo.iter_commits('master'))

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

        # copy all the files from the commit of interest to the new project dir
        for f in fileset:
            shutil.copy(f, self.srcdir)

    def _build_reference_implementation(self):
        '''
        Build a reference checkpoint
        TODO: vivado specific
        '''
        self._init_projdir_from_commit_index(-1)

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
