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

""" Runs one job from the jobfolder. """


def main():
    import re
    from sys import path as python_path
    from os.path import exists
    from argparse import ArgumentParser
    from pylada import jobfolder
    from pylada.process.mpi import create_global_comm
    import pylada

    # below would go additional imports.

    parser = ArgumentParser(prog="runone", description=re.sub("\\s+", " ", __doc__[1:]))
    # colton_mod_start: Change logging level to debug
    parser.add_argument('--logging', dest="logging", default="critical", type=str,
    # parser.add_argument('--logging', dest="logging", default="debug", type=str,
                        help="Debug level.")
    # colton_mod_end
    parser.add_argument('--testValidProgram', dest="testValidProgram",
                        default=None, type=str,
                        help="testValidProgram")
    parser.add_argument("--jobid", dest="names", nargs='+', type=str,
                        help="Job name", metavar="N")
    parser.add_argument("--ppath", dest="ppath", default=None,
                        help="Directory to add to python path",
                        metavar="Directory")
    parser.add_argument('--nbprocs', dest="nbprocs", default=pylada.default_comm['n'], type=int,
                        help="Number of processors with which to launch job.")
    parser.add_argument('--ppn', dest="ppn", default=pylada.default_comm['ppn'], type=int,
                        help="Number of processors with which to launch job.")
    # colton_mod_start: Reduce timeout to 30s, probably bad idea if locking with lockfile still enabled
    #  parser.add_argument('--timeout', dest="timeout", default=300, type=int,
    parser.add_argument('--timeout', dest="timeout", default=30, type=int,
    # colton_mod_end
                        help="Time to wait for job-dictionary to becom available "
                             "before timing out (in seconds). A negative or null "
                             "value implies forever. Defaults to 5mn.")
    parser.add_argument('pickle', metavar='FILE', type=str, help='Path to a job-folder.')

    try:
        options = parser.parse_args()
    except SystemExit:
        return

    from pylada import logger
    logger.setLevel(level=options.logging.upper())
    # colton_mod_start: Print logger level setting
    print(f'Logger level set to {options.logging.upper()}')
    # colton_mod_end
    from pylada.misc import setTestValidProgram
    tstPgm = options.testValidProgram
    if tstPgm.lower() == 'none':
        tstPgm = None
    setTestValidProgram(tstPgm)
    from pylada.misc import testValidProgram

    # additional path to look into.
    if options.ppath is not None:
        python_path.append(options.ppath)

    if not exists(options.pickle):
        print("Could not find file {0}.".format(options.pickle))
        return

    # Set up mpi processes.
    pylada.default_comm['ppn'] = options.ppn
    pylada.default_comm['n'] = options.nbprocs
    if testValidProgram is None:
        create_global_comm(options.nbprocs)   # Sets pylada.default_comm
    else:
        pylada.default_comm = None            # use testValidProgram

    timeout = None if options.timeout <= 0 else options.timeout

    jobfolder = jobfolder.load(options.pickle, timeout=timeout)
    print(('  ipy/lau/scattered_script: jobfolder: %s' % jobfolder))
    print(('  ipy/lau/scattered_script: options: %s' % options))
    for name in options.names:
        logger.info('ipy/lau/scattered_script: testValidProgram: %s' % testValidProgram)
        logger.info('ipy/lau/scattered_script: name: %s' % name)
        logger.info('ipy/lau/scattered_script: jobfolder[name]: %s' % jobfolder[name])
        logger.info('ipy/lau/scattered_script: type(jobfolder[name]): %s' %
                         type(jobfolder[name]))
        logger.info(
            'ipy/lau/scattered_script: jobfolder[name].compute: %s' % jobfolder[name].compute)
        logger.info(
            'ipy/lau/scattered_script: type(jobfolder[name].compute): %s' \
            % type(jobfolder[name].compute))
        logger.info('ipy/lau/scattered_script: before compute for name: %s' % name)

        comm = pylada.default_comm
        if testValidProgram is not None:
            comm = None
        jobfolder[name].compute(comm=comm, outdir=name)
        logger.info('ipy/lau/scattered_script: after compute for name: %s' % name)

if __name__ == "__main__":
    main()
