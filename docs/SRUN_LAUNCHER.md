# Srun Launcher for Pylada

## Overview

The `srun` launcher is a new launch mode for Pylada that allows you to submit **one large SLURM job** and use `srun` to launch individual calculations within that allocation. This is more efficient than the `scattered` launcher which submits separate SLURM jobs for each calculation.

## How It Works

### Traditional `scattered` Launcher
- Submits one `sbatch` job per calculation
- Each job waits in the queue independently
- Queue overhead for each calculation
- Good for heterogeneous calculations with different resource needs

### New `srun` Launcher
- Submits **one** `sbatch` job with a large allocation
- Uses `srun --exclusive` to launch calculations within that allocation
- Multiple calculations run in parallel within the allocation
- Better queue efficiency and resource utilization
- Good for many similar calculations

## Usage

### Basic Example

```python
# In IPython
%launch srun --walltime 24:00:00 --allocation-nodes 4 --ppn 16 path/to/jobfolder.pkl
```

### Parameters

- `--walltime`: Total walltime for the allocation (e.g., "24:00:00")
- `--allocation-nodes`: Total number of nodes to allocate (default: 1)
- `--ppn`: Processes per node (default: from config)
- `--nbprocs`: Number of processes per calculation (can be integer or callable)
- `--queue`: SLURM partition/queue
- `--account`: Account/project code
- `--force`: Re-run successful calculations
- `--nolaunch`: Create script but don't submit

### Advanced Example

```python
# Allocate 10 nodes for 48 hours, run calculations with varying processor counts
%launch srun --walltime 48:00:00 --allocation-nodes 10 --ppn 32 \
             --nbprocs my_nbprocs_function --queue normal \
             --account myproject jobfolder.pkl
```

## Configuration

### Required Configuration File Changes

In your `~/.pylada` or project config file:

```python
# Use srun instead of mpirun
mpirun_exe = "srun -n {n} {placement} {program}"

# Set to False for srun mode
do_multiple_mpi_programs = False

# Configure for your system
default_comm = {'n': 32, 'placement': '', 'ppn': 16}

qsub_exe = "sbatch"
qdel_exe = "scancel"
```

See `config/slurm_srun_example.py` for a complete example.

## How Calculations Are Launched

When you use the srun launcher, Pylada:

1. Collects all jobs to run from the jobfolder
2. Calculates maximum concurrent jobs based on allocation size and job requirements
3. Creates a single SLURM script with intelligent job throttling
4. Inside that script, uses either:
   - **GNU parallel** (if available): Manages job queue automatically with `-j` flag
   - **Bash job control** (fallback): Custom semaphore-style throttling using `wait -n`

The script launches each calculation with:
```bash
srun -N <nodes> -n <nprocs> --ntasks-per-node=<ppn> --exclusive \
     python script.py --jobid=<name> <path>
```

### Automatic Resource Management

The launcher automatically:
- **Calculates max concurrent jobs**: `total_nodes / nodes_per_job`
- **Throttles job submission**: Only launches new jobs as resources become available
- **Prevents oversubscription**: Ensures no more than max concurrent jobs run
- **Waits for completion**: Monitors all jobs until completion

The `--exclusive` flag ensures each calculation gets exclusive access to its assigned resources, preventing interference between concurrent calculations.

### Example: 10 Jobs on 4 Nodes

If you have 10 jobs that each need 1 node, and allocate 4 nodes:
1. Jobs 1-4 start immediately
2. Job 5 waits for any of jobs 1-4 to finish
3. As soon as job 1 completes, job 5 starts
4. This continues until all 10 jobs complete

This ensures efficient resource utilization without overwhelming the system.

## Resource Allocation Logic

### How Many Calculations Run Simultaneously?

The number of concurrent calculations depends on:
- Total allocation: `allocation_nodes * ppn` processes
- Processes per calculation: `nbprocs`
- Maximum concurrent: `floor(total_allocation / nbprocs)`

### Example

```
allocation_nodes = 4
ppn = 16
Total processes = 4 * 16 = 64

If each calculation needs 16 processes:
  Concurrent calculations = 64 / 16 = 4

If each calculation needs 32 processes:
  Concurrent calculations = 64 / 32 = 2
```

## Comparison with Other Launchers

| Launcher | Use Case | Pros | Cons |
|----------|----------|------|------|
| **scattered** | Different resource needs | Independent jobs, flexible | Queue overhead, inefficient |
| **asone** | Sequential execution | Simple, one queue entry | No parallelism between jobs |
| **srun** | Many similar calculations | Efficient, parallel within allocation | Fixed allocation size |
| **array** | Job arrays | Built-in SLURM support | Limited by array size limits |
| **interactive** | Development/testing | Immediate feedback | Manual execution |

## Best Practices

1. **Right-size your allocation**: 
   - Estimate total runtime for all jobs
   - Choose `allocation_nodes` to maximize utilization
   - Aim for allocation to stay busy for full walltime

2. **Monitor resource usage**:
   ```bash
   squeue -u $USER
   scontrol show job <jobid>
   ```

3. **Check individual calculation outputs**:
   - Each calculation writes to its own directory
   - Check `<jobname>/stdout` and `<jobname>/stderr`

4. **Adjust for failed calculations**:
   - Re-run with `--force` to retry failed jobs
   - Or remove successful jobs from jobfolder before re-launching

## Troubleshooting

### Problem: Jobs not starting
- Check allocation size: may be waiting for resources
- Reduce `allocation_nodes` or increase `walltime` limit

### Problem: Calculations interfere with each other
- Ensure `--exclusive` flag is in srun commands (should be automatic)
- Check that `do_multiple_mpi_programs = False` in config

### Problem: Some calculations fail
- Check individual output directories for errors
- Verify `nbprocs` matches calculation requirements
- Ensure enough memory per node

## Limitations

1. **Fixed allocation**: Cannot dynamically adjust node count during execution
2. **Single queue entry**: All jobs share the same priority/queue time
3. **Walltime limit**: Must estimate maximum time for all calculations
4. **Same partition**: All calculations run in the same SLURM partition

## When to Use srun Launcher

✅ **Use srun when:**
- Running many calculations with similar resource needs
- Want better queue efficiency
- Have predictable runtimes
- Working on systems with limited queue slots

❌ **Don't use srun when:**
- Calculations have vastly different resource requirements
- Runtimes are highly unpredictable
- Need maximum flexibility per calculation
- Prefer separate queue entries for tracking

## Example Workflow

```python
# 1. Load and prepare jobfolder
%load path/to/calculations.pkl

# 2. Tag jobs you don't want to run
%goto job_name
job.tag = True

# 3. Save modified jobfolder
%savejobs

# 4. Launch with srun
%launch srun --walltime 12:00:00 --allocation-nodes 8 --ppn 32 --queue normal

# 5. Monitor progress
!squeue -u $USER
!ls -la */stdout  # Check calculation outputs

# 6. Re-run failed calculations
%launch srun --walltime 6:00:00 --allocation-nodes 4 --force
```

## Technical Details

### Generated SLURM Script Structure

```bash
#!/bin/bash
#SBATCH --account=myaccount
#SBATCH --time=24:00:00
#SBATCH -N 4
#SBATCH --ntasks-per-node=16
#SBATCH --partition=normal
#SBATCH -e srun_err
#SBATCH -o srun_out
#SBATCH -J pylada_srun
#SBATCH -D /path/to/work/dir

# Check if GNU parallel is available for better job management
if command -v parallel &> /dev/null; then
  echo 'Using GNU parallel for job management'
  JOBS[0]='srun -N 1 -n 16 --ntasks-per-node=16 --exclusive python script.py --jobid=calc1 jobfolder.pkl'
  JOBS[1]='srun -N 1 -n 16 --ntasks-per-node=16 --exclusive python script.py --jobid=calc2 jobfolder.pkl'
  JOBS[2]='srun -N 1 -n 16 --ntasks-per-node=16 --exclusive python script.py --jobid=calc3 jobfolder.pkl'
  # ... more jobs ...
  printf '%s\n' "${JOBS[@]}" | parallel -j 4 --halt soon,fail=1
else
  # Fallback: use bash job control with semaphore-style throttling
  MAX_JOBS=4
  JOBS=()
  JOBS+=( 'srun -N 1 -n 16 --ntasks-per-node=16 --exclusive python script.py --jobid=calc1 jobfolder.pkl' )
  JOBS+=( 'srun -N 1 -n 16 --ntasks-per-node=16 --exclusive python script.py --jobid=calc2 jobfolder.pkl' )
  # ... more jobs ...
  
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
fi
```

**Key features:**
- Automatically detects GNU parallel for optimal performance
- Falls back to bash job control if parallel is unavailable
- Throttles job submission to prevent resource exhaustion
- Maximum concurrent jobs calculated from allocation size

### Implementation Files

- **Launcher**: `src/pylada/ipython/launch/srun.py`
- **Script runner**: `src/pylada/ipython/launch/srun_script.py`
- **Integration**: `src/pylada/ipython/launch/__init__.py`
- **Config example**: `config/slurm_srun_example.py`
