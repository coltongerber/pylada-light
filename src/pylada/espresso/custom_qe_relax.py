
######################################
class CustomChain(object):

    # Defining the folder tree structure
    def __init__(self,pwobj=None):

        import os

        self.maxiter = 20
        self.en_conv = 1.e-6
        #self.file_to_copy = '/beegfs/sets/mbd/pylada_chains/vdw_kernel.bindat'
        #assert os.path.exists(self.file_to_copy), "The file %s does not exist" %(self.file_to_copy)
        self.names=['relax_cellshape','relax_ions','./']
        self.pw=pwobj

    # Defining the Extraction object
    def Extract(self, jobdir):
        from pylada.espresso import extract
        extracted = extract.Extract(jobdir,prefix=self.pw.control.prefix)
        return extracted

    # Creating the workflow
    def __call__(self, structure, outdir=None, **kwargs ):

        import os
        from copy import deepcopy
        from os import getcwd
        from os.path import join
        from pylada.misc import RelativePath
        from pylada.error import ExternalRunFailed
        from pylada.espresso import extract
        from pylada.espresso import Pwscf
        from pylada.crystal import Structure
        import numpy as np
        #from pylada.vasp.specie import U

        # make this function stateless.
        structure_ = structure.copy()
        outdir = getcwd() if outdir is None else RelativePath(outdir).path

        ############ Relax cellshape ###############

        iterator = 0

        if "cellshape" in self.pw.relaxation:

            while iterator < self.maxiter:

                name  = self.names[0]+'/%s' %(iterator)

                ## functional
                relaxer = deepcopy(self.pw)
                #relaxer.add_keyword('GGA',"MK")
                #relaxer.add_keyword('PARAM1',0.1234)
                #relaxer.add_keyword('PARAM2',1.0000)
                #relaxer.add_keyword('LUSE_VDW',True)
                #relaxer.add_keyword('AGGAC',0)
                #relaxer.nsw        = 100
                relaxer.control.calculation = 'vc-relax'
                #relaxer.system.ecutwfc = 60
                
                if iterator == 0:
                    relaxer.system.ecutwfc = 0.9*relaxer.system.ecutwfc
                    #relaxer.kpoints  = "\n0\nAuto\n10"

                ## end of the functional

                params = deepcopy(kwargs)
                fulldir = join(outdir, name)
        
                ## if this calculation has not been done run it
                if iterator==0:
                    print('entering iterator=0')
                    if not os.path.exists(fulldir):
                        os.makedirs(fulldir)
                        #os.system('cp %s %s' %(self.file_to_copy,fulldir))
                        with open(fulldir+'/test_output','w') as test_output:
                            test_output.write('Successfully entered iteration = 0')
                    output = relaxer(structure_, outdir=fulldir, **params)
                    #print(ouptut.success)
                    if not output.success: 
                        raise ExternalRunFailed("Quantum Espresso calculation did not succeed.") 

                    energy = float(output.total_energy)
                    iterator=iterator+1
                    print('finished iterator 0')
                elif iterator>0:

                    if not os.path.exists(fulldir):
                        os.makedirs(fulldir)
                        #os.system('cp %s %s' %(self.file_to_copy,fulldir))
                        structure_ = output.structure
                        #structure_tmp = Structure()
                        #structure_tmp.cell(structure_.cell.T)
                        #for atom in structure_._atoms:
                        #    structure_tmp.append(atom)
                        #structure_ = structure_tmp
                        for ii in range(len(structure_)):
                            del structure_[ii].force

                        output = relaxer(structure_, outdir=fulldir, restart=output, **params)



                    elif os.path.exists(fulldir):
                        #os.system('cp %s %s' %(self.file_to_copy,fulldir))
                        output = relaxer(structure_, outdir=fulldir, **params)

                    if not output.success: 
                        raise ExternalRunFailed("Quantum Espresso calculation did not succeed.") 

                    if abs(float(output.total_energy)-energy)<=self.en_conv:
                        energy=float(output.total_energy)
                        iterator=iterator+1
                        break
                    else:
                        energy=float(output.total_energy)
                        iterator=iterator+1

        ############ Relax ions ###############

        if "ionic" in self.pw.relaxation:

            while iterator < self.maxiter:
                
                name  = self.names[1]+'/%s' %(iterator)
                
                ## functional
                relaxer = deepcopy(self.pw)
                #relaxer.add_keyword('GGA',"MK")
                #relaxer.add_keyword('PARAM1',0.1234)
                #relaxer.add_keyword('PARAM2',1.0000)
                #relaxer.add_keyword('LUSE_VDW',True)
                #relaxer.add_keyword('AGGAC',0)
                #relaxer.nsw        = 50
                #relaxer.relaxation = "ionic"
                relaxer.control.calculation = 'relax'
                #relaxer.system.ecutwfc = 60
                ## end of the functional
        
                params = deepcopy(kwargs)
                fulldir = join(outdir, name)
                ## if this calculation has not been done run it
                if not os.path.exists(fulldir):
                    os.makedirs(fulldir)
                    #os.system('cp %s %s' %(self.file_to_copy,fulldir))
                    try:
                        structure_ = output.structure
                        for ii in range(len(structure_)):
                            del structure_[ii].force
                    except:
                        structure_ = structure.copy()
                    #structure_tmp = Structure()
                    #structure_tmp.cell(structure_.cell.T)
                    #for atom in structure_._atoms:
                    #    structure_tmp.append(atom)
                    #structure_ = structure_tmp
                    #for ii in range(len(structure_)): # moved into try-except
                        #del structure_[ii].force


                    output = relaxer(structure_, outdir=fulldir, restart=output, **params)

                elif os.path.exists(fulldir):
                    #os.system('cp %s %s' %(self.file_to_copy,fulldir))
                    output = relaxer(structure_, outdir=fulldir, **params)

                if not output.success: 
                    raise ExternalRunFailed("Quantum Espresso calculation did not succeed.") 
            
                if abs(float(output.total_energy)-energy)<=self.en_conv:
                    energy=float(output.total_energy)
                    break
                else:
                    energy=float(output.total_energy)

                iterator=iterator+1

        ############ SCF ###############

        if iterator == self.maxiter:
            raise ExternalRunFailed("Quantum Espresso calculation did not relax in the given number of iterations.") 
        
        else:

            name  = self.names[2]

            ## functional
            scf = deepcopy(self.pw)
            #scf.add_keyword('GGA',"MK")
            #scf.add_keyword('PARAM1',0.1234)
            #scf.add_keyword('PARAM2',1.0000)
            #scf.add_keyword('LUSE_VDW',True)
            #scf.add_keyword('AGGAC',0)
            #scf.nsw        = 1
            #scf.relaxation = "static"
            scf.control.calculation = 'scf'
            #relaxer.system.ecutwfc = 60

            ## end of the functional
        
            params = deepcopy(kwargs)
            fulldir = join(outdir, name)
        
            ## if this calculation has not been done run it

            #os.system('cp %s %s' %(self.file_to_copy,fulldir))

            if ("cellshape" in self.pw.relaxation) or ("ionic" in self.pw.relaxation):
                structure_ = output.structure
                #structure_tmp = Structure()
                #structure_tmp.cell(structure_.cell.T)
                #for atom in structure_._atoms:
                #    structure_tmp.append(atom)
                #structure_ = structure_tmp
                for ii in range(len(structure_)):
                    del structure_[ii].force

                output = scf(structure_, outdir=fulldir, restart=output, **params)

            elif "static" in self.pw.relaxation:
                output = scf(structure_, outdir=fulldir, **params)

            if not output.success: 
                raise ExternalRunFailed("Quantum Espresso calculation did not succeed.") 

        return self.Extract(fulldir)
##########################################
