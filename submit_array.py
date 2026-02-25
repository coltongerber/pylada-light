"""
Submit a SLURM array job for Pylada jobfolder calculations.
This script generates a job list and SLURM array script, then submits it.
"""
import os
from pylada.jobfolder import load
import subprocess

def create_array_job(
    jobfolder_path="jobs.pkl",
    account="project_462000290",
    partition="standard",
    nodes=1,
    ntasks_per_node=128,  # Match the number of MPI ranks
    cpus_per_task=1,      # 1 CPU per task
    walltime="24:00:00",
    max_concurrent=10,
    output_prefix="array_job",
    force_rerun=False
):
    """
    Create and submit a SLURM array job for a jobfolder.
    
    Parameters
    ----------
    jobfolder_path : str
        Path to the jobfolder pickle file
    account : str
        SLURM account/project
    partition : str
        SLURM partition/queue
    nodes : int
        Number of nodes per array task
    ntasks_per_node : int
        Number of MPI tasks per node
    cpus_per_task : int
        Number of CPUs per task
    walltime : str
        Walltime in HH:MM:SS format
    max_concurrent : int
        Maximum number of concurrent array tasks
    output_prefix : str
        Prefix for output files
    force_rerun : bool
        If True, rerun even completed jobs
    """
    
    # Load jobfolder using module-level load function
    print(f"Loading jobfolder from {jobfolder_path}...")
    jobfolder = load(jobfolder_path)
    
    # Get list of jobs to run
    jobnames = []
    for name, job in jobfolder.items():
        # Skip tagged jobs
        if job.is_tagged:
            continue
        
        # Skip successful jobs unless force_rerun is True
        if not force_rerun and hasattr(job, 'functional'):
            if hasattr(job.functional, 'Extract'):
                try:
                    extract = job.functional.Extract(os.path.join(os.path.dirname(jobfolder_path), name))
                    if extract.success:
                        print(f"Skipping completed job: {name}")
                        continue
                except Exception:
                    pass
        
        jobnames.append(name)
    
    if not jobnames:
        print("No jobs to run!")
        return
    
    print(f"Found {len(jobnames)} jobs to run")
    
    # Create job list file
    joblist_file = f"{output_prefix}_joblist.txt"
    with open(joblist_file, "w") as f:
        f.write("\n".join(jobnames))
    print(f"Created {joblist_file}")
    
    # Calculate total processors per job
    # Total MPI ranks = ntasks_per_node * nodes
    nprocs = ntasks_per_node * nodes
    ppn = ntasks_per_node
    
    # Create SLURM array script
    script_path = f"{output_prefix}_submit.sh"
    script_content = f"""#!/bin/bash
#SBATCH --account={account}
#SBATCH --partition={partition}
#SBATCH --nodes={nodes}
#SBATCH --ntasks-per-node={ntasks_per_node}
#SBATCH --cpus-per-task={cpus_per_task}
#SBATCH --time={walltime}
#SBATCH --array=1-{len(jobnames)}%{max_concurrent}
#SBATCH --output={output_prefix}_%A_%a.out
#SBATCH --error={output_prefix}_%A_%a.err
#SBATCH --job-name={output_prefix}

# Load required modules
module load LUMI/24.03
module load EasyBuild-user
module load partition/C
module load QuantumESPRESSO/7.3.1-cpeGNU-24.03

# Add custom container wrapper to PATH if it exists
if [ -f /users/coltgerb/scratch/coltgerb/qe/container_wrapper/add_to_path.sh ]; then
    source /users/coltgerb/scratch/coltgerb/qe/container_wrapper/add_to_path.sh
fi

# Get job name from array index
JOB_NAME=$(sed -n "${{SLURM_ARRAY_TASK_ID}}p" {joblist_file})

echo "Array task ${{SLURM_ARRAY_TASK_ID}}: Running job ${{JOB_NAME}}"
echo "Node: ${{SLURM_NODELIST}}"
echo "Start time: $(date)"

# Run the specific job from the jobfolder
python -c "
import sys
import os
from pylada.jobfolder import load
from pylada.process.mpi import create_global_comm
import pylada

# Debug: Print environment
print('Working directory:', os.getcwd())
print('Job name: ${{JOB_NAME}}')
print('PATH:', os.environ.get('PATH', 'not set'))

# Set up MPI communicator
pylada.default_comm['ppn'] = {ppn}
pylada.default_comm['n'] = {nprocs}
create_global_comm({nprocs})

# Load jobfolder
jobfolder = load('{jobfolder_path}')

# Get the specific job
job = jobfolder['${{JOB_NAME}}']

# Debug: Print job info
print('Job type:', type(job))
print('Job functional:', type(job.functional) if hasattr(job, 'functional') else 'No functional')

# Run the job using compute method
print('Starting job: ${{JOB_NAME}}')
try:
    result = job.compute(comm=pylada.default_comm, outdir='${{JOB_NAME}}')
    print('Completed job: ${{JOB_NAME}}')
    print('Result:', result)
except Exception as e:
    print('Job failed with error:', str(e))
    import traceback
    traceback.print_exc()
    # Print any output files that might exist
    outdir = '${{JOB_NAME}}'
    if os.path.exists(outdir):
        print('\\nOutput directory contents:')
        for root, dirs, files in os.walk(outdir):
            for f in files:
                fpath = os.path.join(root, f)
                print(f'  {{fpath}}')
                if f.endswith('.err') or f.endswith('.out'):
                    print(f'  --- Contents of {{f}} ---')
                    try:
                        with open(fpath, 'r') as ff:
                            print(ff.read()[-2000:])  # Last 2000 chars
                    except:
                        pass
    raise
"

EXIT_CODE=$?
echo "End time: $(date)"
echo "Exit code: ${{EXIT_CODE}}"

exit ${{EXIT_CODE}}
"""
    
    with open(script_path, "w") as f:
        f.write(script_content)
    
    print(f"Created {script_path}")
    
    subprocess.run(["sbatch", script_path])
    print("Submitted array job")

    print("\nTo monitor the jobs:")
    print("  squeue -u $USER --array")
    
    return script_path, joblist_file


if __name__ == "__main__":
    # Example usage
    script, joblist = create_array_job(
        jobfolder_path="jobs.pkl",
        account="project_462000290",
        partition="standard",
        nodes=1,
        ntasks_per_node=128,  # 128 MPI ranks per node
        cpus_per_task=1,      # 1 CPU per MPI rank
        walltime="00:10:00",
        max_concurrent=10,
        output_prefix="qe_array",
        force_rerun=False
    )
