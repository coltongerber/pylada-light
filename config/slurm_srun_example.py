# Example Slurm configuration for using srun within a single allocation
# This configuration is designed for the new 'srun' launcher mode

vasp_has_nlep = False
qsub_exe = "sbatch"
qdel_exe = "scancel"

# Important: Set this to False for srun mode
# When using srun, we don't need multiple MPI programs simultaneously
# because srun handles task parallelism within the allocation
do_multiple_mpi_programs = False

default_comm = {'n': 2, 'placement': '', 'ppn': 16}
""" Default mpirun parameters. """

# For srun mode, use srun instead of mpirun
# srun will automatically use the allocation from sbatch
mpirun_exe = "srun -n {n} {placement} {program}"
""" Command-line to launch external mpi programs with srun. """

def ipython_qstat(self, arg):
    """ squeue --user=`whoami` -o "%7i %.3C %3t  --   %50j" """
    from six import PY3
    from subprocess import Popen, PIPE
    from IPython.utils.text import SList
    from getpass import getuser
    whoami = getuser()
    squeue = Popen(["squeue", "--user=" + whoami, "-o", "\"%7i %.3C %3t    %j\""], stdout=PIPE)
    result = squeue.stdout.read().rstrip().splitlines()
    if PY3:
        result = SList([u[1:-1].decode("utf-8") for u in result[1:]])
    else:
        result = SList([u[1:-1] for u in result[1:]])

    return result if str(arg) == '' else result.grep(str(arg[1:-1]))

# PBS/SLURM script template for srun launcher
# Note: The srun launcher will add multiple srun commands in the body
pbs_string = """#!/bin/bash
#SBATCH --account={account}
#SBATCH --time={walltime}
#SBATCH -N {nnodes}
#SBATCH --ntasks-per-node={ppn}
#SBATCH --partition={queue}
#SBATCH -e {err}
#SBATCH -o {out}
#SBATCH -J {name}
#SBATCH -D {directory}

{header}

# The srun launcher will insert multiple srun commands here
# Each calculation runs with --exclusive flag to prevent interference
python {scriptcommand}

{footer}
"""

# Queue configuration - adjust for your system
queues = ['normal', 'debug', 'gpu']
""" Available queues on your system """

accounts = ['your_account']
""" Your account/project codes """

features = []
""" Available features """

debug_queue = "queue", "debug"
""" Debug queue configuration """

default_pbs = {
    'account': accounts[0],
    'walltime': "01:00:00",
    'nnodes': 4,  # Default allocation size
    'ppn': 16,    # Processes per node
    'header': '',
    'footer': ''
}
""" Default PBS/SLURM parameters """
