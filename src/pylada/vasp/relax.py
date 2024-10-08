###############################
#  This file is part of PyLaDa.
#
#  Copyright (C) 2013 National Renewable Energy Lab
#
#  PyLaDa is a high throughput computational platform for Physics. It aims to make it easier to submit
#  large numbers of jobs on supercomputers. It provides a python interface to physical input, such as
#  crystal structures, as well as to a number of DFT (VASP, CRYSTAL) and atomic potential programs. It
#  is able to organise and launch computational jobs on PBS and SLURM.
#
#  PyLaDa is free software: you can redistribute it and/or modify it under the terms of the GNU General
#  Public License as published by the Free Software Foundation, either version 3 of the License, or (at
#  your option) any later version.
#
#  PyLaDa is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
#  the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#  Public License for more details.
#
#  You should have received a copy of the GNU General Public License along with PyLaDa.  If not, see
#  <http://www.gnu.org/licenses/>.
###############################

""" Relaxation Methods

    An accurately strain-relaxed VASP calculation requires multiple restarts.
    The reasons for this lies in that the plane-wave basis is determined at the
    start of any particular VASP run. Hence, the basis is incorrect if the
    cell-shape changes during the run. The same can be said of real-space
    pseudo-potential grids when relaxing ionic positions. 

    This module contains methods to chain together VASP calculations until a
    fully relaxed structure is obtained.
"""
__docformat__ = "restructuredtext en"
__all__ = ['relax', 'iter_relax', 'Relax', 'epitaxial', 'iter_epitaxial', 'RelaxExtract']
from ..vasp import logger
from ..tools.makeclass import makeclass, makefunc
from .functional import Vasp
from .extract import Extract, MassExtract


class RelaxExtract(Extract):
    """ Extractor class for vasp relaxations. """
    class IntermediateMassExtract(MassExtract):
        """ Focuses on intermediate steps. """

        def __iter_alljobs__(self):
            """ Goes through all directories with an OUTVAR. """
            from glob import iglob
            from os.path import relpath, join, exists
            from itertools import chain

            for dir in chain(iglob(join(self.rootpath, 'relax_cellshape', '*/')),
                             iglob(join(self.rootpath, 'relax_ions', '*/'))):
                if not exists(join(self.rootpath, dir, 'OUTCAR')):
                    continue
                try:
                    result = Extract(dir[:-1])
                except:
                    continue
                yield join('/', relpath(dir[:-1], self.rootpath)), result

    @property
    def details(self):
        """ Intermediate steps. """
        if '_details' not in self.__dict__:
            from os.path import exists
            if not exists(self.directory):
                return None
            self.__dict__['_details'] = None
            self._details = self.IntermediateMassExtract(self.directory)
            """ List of intermediate calculation extractors. """
        return self._details

    def files(self, **kwargs):
        """ Iterates over input/output files. """
        from itertools import chain
        for file in chain(super(RelaxExtract, self).files(**kwargs),
                          self.details.files(**kwargs)):
                               yield file

    @property
    def is_running(self):
        """ True if program is running on this functional. 

            A file '.pylada_is_running' is created in the output folder when it is
            set-up to run CRYSTAL_. The same file is removed when CRYSTAL_ returns
            (more specifically, when the :py:class:`pylada.process.ProgramProcess` is
            polled). Hence, this file serves as a marker of those jobs which are
            currently running.
        """
        from os.path import join, exists
        is_run = exists(join(self.directory, '.pylada_is_running'))
        if not is_run:
            for value in self.details.values():
                if value.is_running:
                    is_run = True
        return is_run

# colton_mod: Change maxcalls to 20 as it seems hardcoded without a way to change it.
# The vasp.maxiter line in HT_relax does not appear to do anything as there is no maxiter.
def iter_relax(vasp, structure, outdir=None, first_trial=None,
               maxcalls=20, keepsteps=True, nofail=False,
               convergence=None, minrelsteps=-1, **kwargs):
    """ Iterator over calls to VASP during relaxation.

        This generator iterates over successive VASP calculations until a fully
        relaxed structure is obtained. Its last calculation is *static*, ensuring
        that the final electronic structure accurately represents the relaxed
        structure.

        The full process is to first relax the cell-shape (and internal degrees of
        freedom upon request) until convergence is achieved, as determined by the
        difference in total energies (see the keyword argument ``convergence``)
        within the current VASP run. Subsequent runs keep the cell-shape constant
        while allowing ionic degrees of freedom to relax, until the same
        convergence criteria is achieved. Finally, a static calculation is
        performed.

        It is possible to bypass cell-shape relaxations and perform only
        ionic-relaxations.

        :param vasp:
          :py:class:`Vasp <pylada.vasp.functional.Vasp>` object with which to
          perform the relaxation.
        :param structure:
          :py:class:`Structure <pylada.crystal.Structure>` object for which to
          perform the relaxation.
        :param outdir:
          Directory where to perform the calculations. Defaults to current
          working directory. The actual calculations are stored within the
          *relax* subdirectory.
        :param dict first_trial:
          Holds parameters which are used only for the very first VASP
          calculation. It can be used to accelerate the first step of the
          relaxation if starting far from the optimum. Defaults to empty
          dictionary.
        :param int maxcalls:
          Maximum number of calls to VASP before aborting. Defaults to 10.
        :param bool keepsteps:
          If true, intermediate steps are kept. If False, intermediate steps are
          erased.
        :param bool nofail:
          If True, will not fail if convergence is not achieved. Just keeps going. 
          Defaults to False.
        :param convergence:
          Convergence criteria. If ``minrelsteps`` is positive, it is only
          checked after ``minrelsteps`` have been performed. Convergence is
          checked according to last VASP run, not from one VASP run to another.
          Eg. If a positive real number, convergence is achieved when the
          difference between the last two total-energies of the current run fall
          below that real number (times structure size), not when the total
          energies of the last two runs fall below that number. Faster, but
          possibly less safe.

          * None: defaults to ``vasp.ediff * 1e1``
          * positive real number: energy convergence criteria in eV per atom. 
          * negative real number: force convergence criteria in eV/angstrom. 
          * callable: Takes an extraction object as input. Should return True if
            convergence is achieved and False otherwise.
        :param int minrelsteps:
          Fine tunes how convergence criteria is applied.

          * positive: at least ``minrelsteps`` calls to VASP are performed before
            checking for convergence. If ``relaxation`` contains "cellshape",
            then these calls occur during cellshape relaxation. If it does not,
            then the calls occur during the ionic relaxations. The calls do count
            towards ``maxcalls``.
          * negative (default): argument is ignored.
        :param kwargs:
          Other parameters are applied to the input
          :py:class:`~pylada.vasp.functional.Vasp` object.

        :return: At each step, yields an extraction object if the relevant VASP
                 calculation already exists. Otherwise, it yields a
                 :py:class:`~pylada.process.program.ProgramProcess` object
                 detailing the call to the external VASP program.
    """
    from re import sub
    from copy import deepcopy
    from os import getcwd
    from os.path import join
    from shutil import rmtree
    from ..misc import RelativePath
    from ..error import ExternalRunFailed

    logger.debug("vasp/relax: iter_relax: entry.  type(vasp): %s" % (type(vasp)))
    logger.debug('vasp/relax: iter_relax: entry. === start vasp:\n%s' % repr(vasp))
    logger.debug('===== end vasp')
    logger.debug('vasp/relax: iter_relax: entry. structure:\n%s' % structure)
    logger.debug('vasp/relax: iter_relax: type(structure): %s' % type(structure))
    logger.debug('vasp/relax: iter_relax: entry.  outdir: %s' % outdir)
    logger.debug('vasp/relax: iter_relax: entry.  first_trial: %s' % first_trial)
    logger.debug('vasp/relax: iter_relax: entry.  maxcalls: %s' % maxcalls)
    # colton_mod_start: Print warning for maxcalls/maxiter
    logger.warning('vasp/relax: iter_relax: entry.  Setting maxcalls with maxiter does not work!!! It is hardcoded into vasp.relax.iter_relax')
    # colton_mod_end
    logger.debug('vasp/relax: iter_relax: entry.  keepsteps: %s' % keepsteps)
    logger.debug('vasp/relax: iter_relax: entry.  nofail: %s' % nofail)
    logger.debug('vasp/relax: iter_relax: entry.  convergence: %s' % convergence)
    logger.debug('vasp/relax: iter_relax: entry.  minrelsteps: %s' % minrelsteps)
    logger.debug('vasp/relax: iter_relax: entry.  kwargs: %s' % kwargs)

    # make this function stateless.
    vasp = deepcopy(vasp)
    relaxed_structure = structure.copy()
    if first_trial is None:
        first_trial = {}
    outdir = getcwd() if outdir is None else RelativePath(outdir).path
    logger.debug("vasp/relax: iter_relax: final outdir: %s\n" % outdir)
    # .../mos2_024000/mos2_024000.cif/non-magnetic

    # convergence criteria and behavior.
    is_converged = _get_is_converged(
        vasp, relaxed_structure, convergence=convergence,
        minrelsteps=minrelsteps, **kwargs)

    # number of restarts.
    nb_steps, output = 0, None

    # sets parameter dictionary for first trial.
    if first_trial is not None:
        params = kwargs.copy()
        params.update(first_trial)
    else:
        params = kwargs

    # defaults to vasp.relaxation
    relaxation = kwargs.pop('relaxation', vasp.relaxation)
    # could be that relaxation comes from vasp.relaxation which is a tuple.
    if isinstance(relaxation, tuple):
        vasp = deepcopy(vasp)
        vasp.relaxation = relaxation
        relaxation = relaxation[0]
    # cellshape ionic volume

    # performs cellshape relaxation calculations.
    while (maxcalls <= 0 or nb_steps < maxcalls) and relaxation.find("cellshape") != -1:
        # Invokes vasp/functional.Vasp.__init__
        # and vasp/functional: iter, which calls bringup,
        # which calls write_incar, write_kpoints, etc.
        fulldir = join(outdir, "relax_cellshape", str(nb_steps))
        for u in vasp.iter\
                (
                    relaxed_structure,
                    outdir=fulldir,
                    restart=output,
                    relaxation=relaxation,
                    **params
                ):
            yield u

        output = vasp.Extract(join(outdir, "relax_cellshape", str(nb_steps)))
        if not output.success:
            ExternalRunFailed("VASP calculations did not complete.")
        relaxed_structure = output.structure

        nb_steps += 1
        if nb_steps == 1 and len(first_trial) != 0:
            params = kwargs
            continue
        # check for convergence.
        isConv = is_converged(output)
        if isConv:
            break

    # Does not perform ionic calculation if convergence not reached.
    if nofail == False and is_converged(output) == False:
        raise ExternalRunFailed("Could not converge cell-shape in {0} iterations.".format(maxcalls))

    # performs ionic calculation.
    while (maxcalls <= 0 or nb_steps < maxcalls + 1) and relaxation.find("ionic") != -1:
        fulldir = join(outdir, "relax_ions", str(nb_steps))
        for u in vasp.iter\
                (
                    relaxed_structure,
                    outdir=fulldir,
                    relaxation="ionic",
                    restart=output,
                    **params
                ):
            yield u

        output = vasp.Extract(join(outdir, "relax_ions", str(nb_steps)))
        if not output.success:
            ExternalRunFailed("VASP calculations did not complete.")
        relaxed_structure = output.structure

        nb_steps += 1
        if nb_steps == 1 and len(first_trial) != 0:
            params = kwargs
            continue
        # check for convergence.
        isConv = is_converged(output)
        if isConv:
            break

    # xxxxxxxxxxxxxxxxx start here
    # xxx set INCAR parameters by:
    #  vasp._input['xxxxxfoobar'] = 'xxxxxFOOBAREDxxxxx'
    # Similarly, in the files test/highthroughput/input*.py,
    # one can use the same assignment.

    # gwmod: same while loop as above, but with relaxation="gwcalc"
    # performs gwcalc calculation, at most once
    if (maxcalls <= 0 or nb_steps < maxcalls + 2) \
            and relaxation.find("relgw") != -1:

        fulldir = join(outdir, "relax_gwcalc", str(nb_steps))
        for u in vasp.iter\
                (
                    relaxed_structure,
                    outdir=fulldir,
                    relaxation="relgw",
                    restart=output,
                    **params
                ):
            yield u

        output = vasp.Extract(join(outdir, "relax_gwcalc", str(nb_steps)))
        if not output.success:
            ExternalRunFailed("VASP calculations did not complete.")
        relaxed_structure = output.structure

        nb_steps += 1

    # Does not perform static calculation if convergence not reached.
    if nofail == False and is_converged(output) == False:
        raise ExternalRunFailed("Could not converge ions in {0} iterations.".format(maxcalls))

    # performs final calculation outside relaxation directory.

    # xxx skip if gwmod:
    # gwmod: if relaxation.find("relgw") == -1 ...

    for u in vasp.iter\
            (
                relaxed_structure,
                outdir=outdir,
                relaxation="static",
                restart=output,
                **kwargs
            ):
        yield u

    output = vasp.Extract(outdir)
    if not output.success:
        ExternalRunFailed(
            "VASP calculations did not complete.")

    if output.success and (not keepsteps):
        rmtree(join(outdir, "cellshape"))
        rmtree(join(outdir, "ions"))

    # yields final extraction object.
    yield iter_relax.Extract(outdir)


iter_relax.Extract = RelaxExtract
""" Extraction method for relaxation runs. """

relax = makefunc('relax', iter_relax, module='pylada.vasp.relax')
Relax = makeclass('Relax', Vasp, iter_relax, None, module='pylada.vasp.relax',
                  doc='Functional form of the :py:class:`pylada.vasp.relax.iter_relax` method.')

def _get_is_converged(vasp, structure, convergence=None, minrelsteps=-1, **kwargs):
    """ Returns convergence function. """
    from ..error import ExternalRunFailed
    # tries and devine the convergence criteria from the input.
    if convergence is None:
        convergence = 1e1 * vasp.ediff
    elif hasattr(convergence, "__call__"):
        pass
    elif convergence > 0:
        convergence *= float(len(structure))
    if convergence > 0 and convergence < vasp.ediff:
        raise ValueError("Energy convergence criteria ediffg({0}) is smaller than ediff({1})."
                         .format(vasp.ediffg, vasp.ediff))
    # creates a convergence function.
    if hasattr(convergence, "__call__"):
        def is_converged(extractor):
            if extractor is None:
                return True
            if not extractor.success:
                raise ExternalRunFailed("VASP calculation did not succeed.")
            i = int(extractor.directory.split('/')[-1]) + 1
            if minrelsteps > 0 and minrelsteps > i:
                return False
            return convergence(extractor)
    elif convergence > 0e0:
        def is_converged(extractor):
            if extractor is None:
                return True
            if not extractor.success:
                raise ExternalRunFailed("VASP calculation did not succeed.")
            i = int(extractor.directory.split('/')[-1]) + 1
            if minrelsteps > 0 and minrelsteps > i:
                return False
            if extractor.total_energies.shape[0] < 2:
                return True
            return abs(extractor.total_energies[-2] - extractor.total_energies[-1:]) < convergence
    else:
        def is_converged(extractor):
            from numpy import max, abs, all
            if extractor is None:
                return True
            if not extractor.success:
                raise ExternalRunFailed("VASP calculation did not succeed.")
            i = int(extractor.directory.split('/')[-1]) + 1
            if minrelsteps > 0 and minrelsteps > i:
                return False
            return all(max(abs(extractor.forces)) < abs(convergence))
    return is_converged


def iter_epitaxial(vasp, structure, outdir=None, direction=[0, 0, 1], epiconv=1e-4,
                   initstep=0.05, **kwargs):
    """ Performs epitaxial relaxation in given direction. 

        This generator iterates over successive VASP calculations until an
        epitaxially relaxed structure is obtained.  The external (cell)
        coordinates of the structure can only relax in the growth/epitaxial
        direction. Internal coordinates (ions), however, are allowed to relax in
        whatever direction. 

        Since VASP does not intrinsically allow for such a relaxation, it is
        performed by chaining different vasp calculations together. The
        minimization procedure itself is the secant method, enhanced by the
        knowledge of the stress tensor. The last calculation is static, for
        maximum accuracy.

        :param vasp: 
          :py:class:`Vasp <pylada.vasp.functional.Vasp>` functional with wich to
          perform the relaxation.
        :param structure:
          :py:class:`Structure <pylada.crystal.Structure>` for which to perform the
          relaxation.
        :param str outdir: 
          Directory where to perform calculations. If None, defaults to current
          working directory. The intermediate calculations are stored in the
          relax_ions subdirectory.
        :param direction:
          Epitaxial direction. Defaults to [0, 0, 1].
        :param float epiconv: 
          Convergence criteria of the total energy.

        :return: At each step, yields an extraction object if the relevant VASP
                 calculation already exists. Otherwise, it yields a
                 :py:class:`~pylada.process.program.ProgramProcess` object
                 detailing the call to the external VASP program.
    """
    from os import getcwd
    from os.path import join
    from copy import deepcopy
    from re import sub
    from numpy.linalg import norm
    from numpy import array, dot

    direction = array(direction, dtype='float64') / norm(direction)
    if outdir is None:
        outdir = getcwd()

    # creates relaxation functional.
    vasp = deepcopy(vasp)
    kwargs.pop('relaxation', None)
    vasp.relaxation = 'ionic'
    vasp.encut = 1.4
    if 'encut' in kwargs:
        vasp.encut = kwargs.pop('encut')
    if 'ediff' in kwargs:
        vasp.ediff = kwargs.pop('ediff')
    if vasp.ediff < epiconv:
        vasp.ediff = epiconv * 1e-2
    kwargs['istruc'] = 'input'
    kwargs['relaxation'] = 2

    allcalcs = []

    def change_structure(x):
        """ Creates new structure with input change in c. """
        from numpy import outer
        newstruct = structure.copy()
        strain = outer(direction, direction) * x
        newstruct.cell += dot(strain, structure.cell)
        for atom in newstruct:
            atom.pos += dot(strain, atom.pos)
        return newstruct

    def component(stress):
        """ Returns relevant stress component. """
        return dot(dot(direction, stress), direction)

    # Tries and find a bracket for minimum.
    # To do this, we start from current structure, look at stress in relevant
    # direction for the direction in which to search, and expand/contract in that direction.
    xstart = 0.0
    for u in vasp.iter(change_structure(xstart),
                       outdir=join(outdir, "relax_ions", "{0:0<12.10}".format(xstart)),
                       restart=None if len(allcalcs) == 0 else allcalcs[-1],
                       **kwargs):
                            yield u
    estart = vasp.Extract(join(outdir, 'relax_ions', '{0:0<12.10}'.format(xstart)))
    allcalcs.append(estart)

    # then checks stress for actual direction to look at.
    stress_direction = 1.0 if component(allcalcs[-1].stress) > 0e0 else -1.0
    xend = initstep if stress_direction > 0e0 else -initstep
    # compute xend value.
    for u in vasp.iter(change_structure(xend),
                       outdir=join(outdir, "relax_ions", "{0:0<12.10}".format(xend)),
                       restart=None if len(allcalcs) == 0 else allcalcs[-1],
                       **kwargs):
                            yield u
    eend = vasp.Extract(join(outdir, 'relax_ions', '{0:0<12.10}'.format(xend)))
    allcalcs.append(eend)
    # make sure xend is on other side of stress tensor sign.
    while stress_direction * component(allcalcs[-1].stress) > 0e0:
        xstart, estart = xend, eend
        xend += initstep if stress_direction > 0e0 else -initstep
        for u in vasp.iter(change_structure(xend),
                           outdir=join(outdir, "relax_ions", "{0:0<12.10}".format(xend)),
                           restart=None if len(allcalcs) == 0 else allcalcs[-1],
                           **kwargs):
                                yield u
        eend = vasp.Extract(join(outdir, 'relax_ions', '{0:0<12.10}'.format(xend)))
        allcalcs.append(eend)

    # now we have a bracket. We start bisecting it.
    while abs(estart.total_energy - eend.total_energy) > epiconv * float(len(structure)):
        xmid = 0.5 * (xend + xstart)
        for u in vasp.iter(change_structure(xmid),
                           outdir=join(outdir, "relax_ions", "{0:0<12.10}".format(xmid)),
                           restart=None if len(allcalcs) == 0 else allcalcs[-1],
                           **kwargs):
                                yield u
        emid = vasp.Extract(join(outdir, 'relax_ions', '{0:0<12.10}'.format(xmid)))
        allcalcs.append(emid)
        if stress_direction * component(emid.stress) > 0:
            xstart, estart = xmid, emid
        else:
            xend, eend = xmid, emid

    # last two calculation: relax mid-point of xstart, xend, then  perform static.
    efinal = eend if estart.total_energy > eend.total_energy else estart
    kwargs['relaxation'] = 'static'
    for u in vasp.iter(efinal.structure, outdir=outdir, restart=efinal, **kwargs):
        yield u
    final = vasp.Extract(outdir)

    # replace initial structure with that with which this function was called.
    # Caution: this edits OUTCAR, overwrites OUTCAR, rewrites OUTCAR.
    with final.__outcar__() as file:
        filename = file.name
        string = sub('#+ INITIAL STRUCTURE #+\n((.|\n)*)\n#+ END INITIAL STRUCTURE #+',
                     """################ INITIAL STRUCTURE ################\n"""
                     """from {0.__class__.__module__} import {0.__class__.__name__}\n"""
                     """structure = {1}\n"""
                     """################ END INITIAL STRUCTURE ################\n"""
                     .format(structure, repr(structure).replace('\n', '\n            ')),
                     file.read())
    with open(filename, 'w') as file:
        file.write(string)

    # yields final extraction object.
    yield iter_epitaxial.Extract(outdir)

iter_epitaxial.Extract = RelaxExtract
""" Extraction method for epitaxial relaxation runs. """
Epitaxial = makeclass('Epitaxial', Vasp, iter_epitaxial, None, module='pylada.vasp.relax',
                      doc='Functional form of the :py:class:`pylada.vasp.relax.iter_epitaxial` method.')
epitaxial = makefunc('epitaxial', iter_epitaxial, module='pylada.vasp.relax')

# colton_mod_start: Add iter_training method, either for NSW=2 boondoggle 
# or to try and check job progress while it is running

def iter_training(vasp, structure, outdir=None, first_trial=None,
               maxcalls=50, nofail=False,
               convergence=None, minrelsteps=-1,
               **kwargs):
    """ Iterator over calls to VASP during relaxation.

        This generator iterates over successive VASP calculations until a fully
        relaxed structure is obtained. Its last calculation is *static*, ensuring
        that the final electronic structure accurately represents the relaxed
        structure.

        The full process is to first relax the cell-shape (and internal degrees of
        freedom upon request) until convergence is achieved, as determined by the
        difference in total energies (see the keyword argument ``convergence``)
        within the current VASP run. Subsequent runs keep the cell-shape constant
        while allowing ionic degrees of freedom to relax, until the same
        convergence criteria is achieved. Finally, a static calculation is
        performed.

        It is possible to bypass cell-shape relaxations and perform only
        ionic-relaxations.

        :param vasp:
          :py:class:`Vasp <pylada.vasp.functional.Vasp>` object with which to
          perform the relaxation.
        :param structure:
          :py:class:`Structure <pylada.crystal.Structure>` object for which to
          perform the relaxation.
        :param outdir:
          Directory where to perform the calculations. Defaults to current
          working directory. The actual calculations are stored within the
          *relax* subdirectory.
        :param dict first_trial:
          Holds parameters which are used only for the very first VASP
          calculation. It can be used to accelerate the first step of the
          relaxation if starting far from the optimum. Defaults to empty
          dictionary.
        :param int maxcalls:
          Maximum number of calls to VASP before aborting. Defaults to 10.
        :param bool nofail:
          If True, will not fail if convergence is not achieved. Just keeps going. 
          Defaults to False.
        :param convergence:
          Convergence criteria. If ``minrelsteps`` is positive, it is only
          checked after ``minrelsteps`` have been performed. Convergence is
          checked according to last VASP run, not from one VASP run to another.
          Eg. If a positive real number, convergence is achieved when the
          difference between the last two total-energies of the current run fall
          below that real number (times structure size), not when the total
          energies of the last two runs fall below that number. Faster, but
          possibly less safe.

          * None: defaults to ``vasp.ediff * 1e1``
          * positive real number: energy convergence criteria in eV per atom. 
          * negative real number: force convergence criteria in eV/angstrom. 
          * callable: Takes an extraction object as input. Should return True if
            convergence is achieved and False otherwise.
        :param int minrelsteps:
          Fine tunes how convergence criteria is applied.

          * positive: at least ``minrelsteps`` calls to VASP are performed before
            checking for convergence. If ``relaxation`` contains "cellshape",
            then these calls occur during cellshape relaxation. If it does not,
            then the calls occur during the ionic relaxations. The calls do count
            towards ``maxcalls``.
          * negative (default): argument is ignored.
        :param kwargs:
          Other parameters are applied to the input
          :py:class:`~pylada.vasp.functional.Vasp` object.

        :return: At each step, yields an extraction object if the relevant VASP
                 calculation already exists. Otherwise, it yields a
                 :py:class:`~pylada.process.program.ProgramProcess` object
                 detailing the call to the external VASP program.
    """
    from re import sub
    from copy import deepcopy
    from os import getcwd
    from os.path import join
    from shutil import rmtree
    from ..misc import RelativePath
    from ..error import ExternalRunFailed

    logger.debug("vasp/relax: iter_training: entry.  type(vasp): %s" % (type(vasp)))
    logger.debug('vasp/relax: iter_training: entry. === start vasp:\n%s' % repr(vasp))
    logger.debug('===== end vasp')
    logger.debug('vasp/relax: iter_training: entry. structure:\n%s' % structure)
    logger.debug('vasp/relax: iter_training: type(structure): %s' % type(structure))
    logger.debug('vasp/relax: iter_training: entry.  outdir: %s' % outdir)
    logger.debug('vasp/relax: iter_training: entry.  maxcalls: %s' % maxcalls)
    logger.debug('vasp/relax: iter_training: entry.  nofail: %s' % nofail)
    logger.debug('vasp/relax: iter_training: entry.  convergence: %s' % convergence)
    logger.debug('vasp/relax: iter_relax: entry.  minrelsteps: %s' % minrelsteps)
    logger.debug('vasp/relax: iter_training: entry.  kwargs: %s' % kwargs)

    # make this function stateless.
    vasp = deepcopy(vasp)
    relaxed_structure = structure.copy()
    if first_trial is None:
        first_trial = {}
    outdir = getcwd() if outdir is None else RelativePath(outdir).path
    logger.debug("vasp/relax: iter_training: final outdir: %s\n" % outdir)

    # convergence criteria and behavior.
    is_converged = _get_is_converged(
        vasp, relaxed_structure, convergence=convergence,
        **kwargs)

    # number of restarts.
    nb_steps, output = 0, None

    # defaults to vasp.relaxation
    relaxation = kwargs.pop('relaxation', vasp.relaxation)
    # could be that relaxation comes from vasp.relaxation which is a tuple.
    if isinstance(relaxation, tuple):
        vasp = deepcopy(vasp)
        vasp.relaxation = relaxation
        relaxation = relaxation[0]

    # performs cellshape relaxation calculations.
    while (maxcalls <= 0 or nb_steps < maxcalls):
        # sets parameter dictionary for cellshape relaxations
        # using existing first_trial dictionary attribute
        if first_trial is not None:
            params = kwargs.copy()
            params.update(first_trial)
        else:
            params = kwargs
        # Invokes vasp/functional.Vasp.__init__
        # and vasp/functional: iter, which calls bringup,
        # which calls write_incar, write_kpoints, etc.
        fulldir = join(outdir, "relax_cellshape", str(nb_steps))
        for u in vasp.iter\
                (
                    relaxed_structure,
                    outdir=fulldir,
                    restart=output,
                    relaxation=relaxation,
                    **params
                ):
            yield u

        output = vasp.Extract(join(outdir, "relax_cellshape", str(nb_steps)))
        if not output.success:
            ExternalRunFailed("VASP calculations did not complete.")
        relaxed_structure = output.structure

        nb_steps += 1
        
                
        # check for cellshape convergence.
        # will return False if nb_steps < min_rel_steps.
        isConv = is_converged(output)
        
        # performs ionic calculation.
        if len(first_trial) != 0:
            params = kwargs
        fulldir = join(outdir, "relax_ions", str(nb_steps))
        for u in vasp.iter\
                (
                    relaxed_structure,
                    outdir=fulldir,
                    relaxation="ionic",
                    restart=output,
                    **params
                ):
            yield u

        output = vasp.Extract(join(outdir, "relax_ions", str(nb_steps)))
        if not output.success:
            ExternalRunFailed("VASP calculations did not complete.")
        relaxed_structure = output.structure
        
        nb_steps += 1
        
        if isConv:
            break



    # Raise error if convergence not reached.
    if nofail == False and is_converged(output) == False:
        raise ExternalRunFailed("Could not converge cell-shape in {0} iterations.".format(maxcalls))

    # xxxxxxxxxxxxxxxxx start here
    # xxx set INCAR parameters by:
    #  vasp._input['xxxxxfoobar'] = 'xxxxxFOOBAREDxxxxx'
    # Similarly, in the files test/highthroughput/input*.py,
    # one can use the same assignment.

    
    # Does not perform static calculation if convergence not reached.
    if nofail == False and is_converged(output) == False:
        raise ExternalRunFailed("Could not converge ions in {0} iterations.".format(maxcalls))

    # performs final calculation outside relaxation directory.

    # xxx skip if gwmod:
    # gwmod: if relaxation.find("relgw") == -1 ...

    for u in vasp.iter\
            (
                relaxed_structure,
                outdir=outdir,
                relaxation="static",
                restart=output,
                **kwargs
            ):
        yield u

    output = vasp.Extract(outdir)
    if not output.success:
        ExternalRunFailed(
            "VASP calculations did not complete.")

    # yields final extraction object.
    yield iter_training.Extract(outdir)


iter_training.Extract = RelaxExtract
""" Extraction method for relaxation runs. """

training = makefunc('training', iter_training, module='pylada.vasp.relax')
Training = makeclass('Training', Vasp, iter_training, None, module='pylada.vasp.relax',
                  doc='Functional form of the :py:class:`pylada.vasp.relax.iter_training` method.')

# colton_mod_end
