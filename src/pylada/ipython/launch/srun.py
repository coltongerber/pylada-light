###############################
#  This file is part of PyLaDa.
#
#  Copyright (C) 2013 National Renewable Energy Lab
#
#  PyLaDa is a high throughput computational platform for Physics. It aims to
#  make it easier to submit large numbers of jobs on supercomputers. It
#  provides a python interface to physical input, such as crystal structures,
#  as well as to a number of DFT (VASP, CRYSTAL) and atomic potential programs.
#  It is able to organise and launch computational jobs on PBS and SLURM.
#
#  PyLaDa is free software: you can redistribute it and/or modify it under the
#  terms of the GNU General Public License as published by the Free Software
#  Foundation, either version 3 of the License, or (at your option) any later
#  version.
#
#  PyLaDa is distributed in the hope that it will be useful, but WITHOUT ANY
#  WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
#  details.
#
#  You should have received a copy of the GNU General Public License along with
#  PyLaDa.  If not, see <http://www.gnu.org/licenses/>.
###############################

""" Launches calculations using srun within a single SLURM allocation.

    This launch strategy submits one large SLURM job and uses srun to
    launch individual calculations within that allocation.

    >>> %launch srun --walltime 24:00:00 --allocation-nodes 4
"""
__docformat__ = "restructuredtext en"


def launch(self, event, jobfolders):
    """ Launch jobs using srun within a single SLURM allocation. """
    from copy import deepcopy
    import os
    import re
    import subprocess
    from os.path import exists, basename, dirname
    from os import remove
    import pylada
    from .. import get_shell
    from ...misc import local_path, testValidProgram
    from ... import pbs_string, default_pbs, qsub_exe, default_comm
    from . import get_walltime, get_mppalloc, get_queues, srun_script
    from .. import logger

    logger.info("launch/srun: event: %s" % event)
    shell = get_shell(self)

    pbsargs = deepcopy(dict(default_comm))
    pbsargs.update(default_pbs)
    pbsargs['ppn'] = event.ppn

    # Set walltime
    if not get_walltime(shell, event, pbsargs):
        return

    # Set queue and account
    if not get_queues(shell, event, pbsargs):
        return
    
    # Get total nodes for the allocation
    allocation_nodes = getattr(event, 'allocation_nodes', 1)
    pbsargs['nnodes'] = allocation_nodes
    pbsargs['n'] = allocation_nodes * pbsargs['ppn']
    
    logger.info("launch/srun: pbsargs: %s" % pbsargs)

    # Get python script to launch in PBS/SLURM
    pyscript = srun_script.__file__
    logger.info("launch/srun: pyscript: %s" % pyscript)
    if pyscript[-1] == 'c':
        pyscript = pyscript[:-1]   # change .pyc to .py

    # Create file names
    hasprefix = getattr(event, "prefix", None)

    def pbspaths(directory, suffix):
        """ creates filename paths. """
        suffix = '{0}-srun{1}'.format(event.prefix, suffix) if hasprefix \
            else 'srun{0}'.format(suffix)
        return str(directory.join(suffix))

    # Collect all jobs to launch
    all_jobs = []
    for current, path in jobfolders:
        logger.info("launch/srun: current: %s  path: %s" % (current, path))
        directory = local_path(path).dirpath()
        directory.ensure(dir=True)
        
        for name, job in current.root.items():
            logger.info('launch/srun: name: %s' % name)
            logger.info('launch/srun: job.is_tagged: %s' % job.is_tagged)

            # Skip tagged jobs
            if job.is_tagged:
                continue

            # Skip successful jobs unless forced
            if hasattr(job.functional, 'Extract') and not event.force:
                p = directory.join(name)
                extract = job.functional.Extract(str(p))
                if extract.success:
                    print(("Job {0} completed successfully. "
                           "It will not be relaunched.".format(name)))
                    continue

            # Determine number of processors for this job
            mppalloc = get_mppalloc(shell, event)
            if mppalloc is None:
                nprocs = event.nbprocs if hasattr(event, 'nbprocs') and event.nbprocs != "None" else pbsargs['ppn']
            else:
                nprocs = mppalloc(job) if hasattr(mppalloc, "__call__") else mppalloc
            
            all_jobs.append({
                'name': name,
                'path': path,
                'directory': str(directory),
                'nprocs': nprocs
            })

    if len(all_jobs) == 0:
        print("No jobs to launch.")
        return

    print(("Collected {0} jobs to launch with srun.".format(len(all_jobs))))

    # Create single PBS/SLURM script
    pbsargs['err'] = pbspaths(local_path(dirname(jobfolders[0][1])), 'err')
    pbsargs['out'] = pbspaths(local_path(dirname(jobfolders[0][1])), 'out')
    pbsargs['name'] = 'pylada_srun' if not hasprefix else event.prefix
    pbsargs['directory'] = dirname(jobfolders[0][1])
    pbsargs['logging'] = 'debug'
    pbsargs['testValidProgram'] = testValidProgram

    # Calculate max concurrent jobs based on resources
    # Each job needs certain number of nodes
    total_nodes = pbsargs['nnodes']
    
    # Build job list with proper resource management
    job_commands = []
    for job_info in all_jobs:
        nodes_per_job = (job_info['nprocs'] + pbsargs['ppn'] - 1) // pbsargs['ppn']
        job_cmd = "srun -N {nnodes} -n {nprocs} --ntasks-per-node={ppn} --exclusive " \
                  "python {pyscript} --logging {logging} --testValidProgram {testValidProgram} " \
                  "--nbprocs {nprocs} --ppn {ppn} --jobid={jobid} {path}".format(
                      nnodes=nodes_per_job,
                      nprocs=job_info['nprocs'],
                      ppn=pbsargs['ppn'],
                      pyscript=pyscript,
                      logging=pbsargs['logging'],
                      testValidProgram=pbsargs['testValidProgram'],
                      jobid=job_info['name'],
                      path=job_info['path']
                  )
        job_commands.append(job_cmd)
    
    # Calculate max concurrent jobs (based on largest job size to avoid oversubscription)
    max_nodes_per_job = max((j['nprocs'] + pbsargs['ppn'] - 1) // pbsargs['ppn'] for j in all_jobs)
    max_concurrent = max(1, total_nodes // max_nodes_per_job)
    
    print(f"Resource allocation: {total_nodes} nodes, max {max_concurrent} concurrent jobs")
    print(f"Jobs will be throttled and launched as resources become available")
    
    # Build script with job throttling using GNU parallel if available, otherwise use bash job control
    job_list = []
    job_list.append("# Check if GNU parallel is available for better job management")
    job_list.append("if command -v parallel &> /dev/null; then")
    job_list.append("  echo 'Using GNU parallel for job management'")
    
    # Create array of job commands for parallel
    for i, cmd in enumerate(job_commands):
        job_list.append(f"  JOBS[{i}]='{cmd}'")
    
    job_list.append(f"  printf '%s\\n' \"${{JOBS[@]}}\" | parallel -j {max_concurrent} --halt soon,fail=1")
    job_list.append("else")
    job_list.append("  # Fallback: use bash job control with semaphore-style throttling")
    job_list.append(f"  MAX_JOBS={max_concurrent}")
    job_list.append("  JOBS=()")
    
    for cmd in job_commands:
        # Escape single quotes in the command
        escaped_cmd = cmd.replace("'", "'\\''")
        job_list.append(f"  JOBS+=( '{escaped_cmd}' )")
    
    job_list.append("""
  running_jobs=0
  for job_cmd in "${JOBS[@]}"; do
    # Wait if we've hit the max concurrent jobs
    while [ $running_jobs -ge $MAX_JOBS ]; do
      wait -n  # Wait for any job to finish
      running_jobs=$((running_jobs - 1))
    done
    
    # Launch the job in background
    eval "$job_cmd" &
    running_jobs=$((running_jobs + 1))
  done
  
  # Wait for all remaining jobs to complete
  wait
fi""")
    
    pbsargs['srun_commands'] = '\n'.join(job_list)
    
    ppath = pbspaths(local_path(dirname(jobfolders[0][1])), 'script')
    logger.info("launch/srun: ppath: \"%s\"" % ppath)
    logger.info("launch/srun: pbsargs: \"%s\"" % pbsargs)

    # Write PBS/SLURM script
    local_path(dirname(jobfolders[0][1])).ensure(dir=True)
    if exists(ppath):
        remove(ppath)
    
    with open(ppath, "w") as file:
        # Use custom PBS string for srun launcher
        string = """#!/bin/bash
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

# Launch all jobs using srun in background
{srun_commands}

{footer}
""".format(**pbsargs)
        
        logger.info("launch/srun: ===== start script: %s =====" % ppath)
        logger.info('%s' % string)
        logger.info("launch/srun: ===== end script: %s =====" % ppath)
        
        lines = string.split('\n')
        omitTag = '# omitted for testValidProgram: '
        for line in lines:
            if testValidProgram != None \
                and (re.match('^ *module ', line)
                     or re.match('^\. .*/bin/activate$', line)):
                line = omitTag + line
            file.write(line + '\n')
    
    assert exists(ppath)
    print(("Created srun job script {0} with {1} jobs.".format(ppath, len(all_jobs))))

    if event.nolaunch:
        return
    
    # Launch the job
    logger.info("launch/srun: launch: shell: %s" % shell)
    logger.info("launch/srun: launch: qsub_exe: %s" % qsub_exe)
    logger.info("launch/srun: launch: script: \"%s\"" % ppath)

    if testValidProgram != None:
        cmdLine = '/bin/bash ' + ppath
    else:
        cmdLine = "{0} {1}".format(qsub_exe, ppath)

    nmerr = ppath + '.stderr'
    nmout = ppath + '.stdout'
    with open(nmerr, 'w') as ferr:
        with open(nmout, 'w') as fout:
            subprocess.call(cmdLine, shell=True, stderr=ferr, stdout=fout)
    
    if os.path.getsize(nmerr) != 0:
        with open(nmerr) as fin:
            print('launch/srun: stderr: %s' % (fin.read(),))
    with open(nmout) as fin:
        print('launch/srun: stdout: %s' % (fin.read(),))


def completer(self, info, data):
    """ Completer for srun launcher. """
    from .. import jobfolder_file_completer
    from ... import queues, accounts, debug_queue, features
    if len(data) > 0:
        if data[-1] == "--walltime":
            return [u for u in self.user_ns
                    if u[0] != '_' and isinstance(self.user_ns[u], str)]
        elif data[-1] == "--nbprocs":
            result = [u for u in self.user_ns
                      if u[0] != '_' and isinstance(self.user_ns[u], int)]
            result.extend([u for u in self.user_ns
                           if u[0] != '_' and hasattr(u, "__call__")])
            return result
        elif data[-1] == '--ppn':
            return ['']
        elif data[-1] == "--allocation-nodes":
            return ['']
        elif data[-1] == "--prefix":
            return ['']
        elif data[-1] == "--queue":
            return queues
        elif data[-1] == "--account":
            return accounts
        elif data[-1] == "--feature":
            return features
    result = ['--force', '--walltime', '--nbprocs', '--allocation-nodes', '--help']
    if len(queues) > 0:
        result.append("--queue")
    if len(accounts) > 0:
        result.append("--account")
    if len(features) > 0:
        result.append("--feature")
    if debug_queue is not None:
        result.append("--debug")
    result.extend(jobfolder_file_completer([info.symbol]))
    result = list(set(result) - set(data))
    return result


def parser(self, subparsers, opalls):
    """ Adds subparser for srun launcher. """
    from ... import default_comm
    from . import set_queue_parser, set_default_parser_options
    result = subparsers.add_parser('srun',
                                   description="Submit one SLURM job and use srun to "
                                   "launch calculations within that allocation.",
                                   parents=[opalls])
    set_default_parser_options(result)
    result.add_argument('--nbprocs', type=str, default="None", dest="nbprocs",
                        help="Can be an integer, in which case it specifies "
                        "the number of processes to execute jobs with. "
                        "Can also be a callable taking a JobFolder as "
                        "argument and returning an integer. Will default "
                        "to ppn if not specified.")
    result.add_argument('--ppn', dest="ppn",
                        default=default_comm.get('ppn', 1), type=int,
                        help="Number of processes per node. Defaults to {0}."
                        .format(default_comm.get('ppn', 1)))
    result.add_argument('--allocation-nodes', dest='allocation_nodes',
                        type=int, default=1,
                        help='Total number of nodes to allocate for the entire job.')
    set_queue_parser(result)
    result.set_defaults(func=launch)
    return result
