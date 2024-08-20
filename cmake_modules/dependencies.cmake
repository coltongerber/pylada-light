include(PackageLookup)
set(PYLADA_WITH_EIGEN3 1)
lookup_package(Eigen3 REQUIRED)

find_package(CoherentPython REQUIRED)
include(PythonPackage)
include(PythonPackageLookup)

# Create local python environment
# If it exists, most cookoff functions will use LOCAL_PYTHON_EXECUTABLE rather
# than PYTHON_EXECUTABLE. In practice, this means that packages installed in
# the build tree can be found.
include(EnvironmentScript)
add_to_python_path("${PROJECT_BINARY_DIR}/python")
add_to_python_path("${EXTERNAL_ROOT}/python")
set(LOCAL_PYTHON_EXECUTABLE "${PROJECT_BINARY_DIR}/localpython.sh")
create_environment_script(
    PYTHON
    EXECUTABLE "${PYTHON_EXECUTABLE}"
    PATH "${LOCAL_PYTHON_EXECUTABLE}"
)

if(tests)
    lookup_python_package(pytest)
    find_python_package(nbconvert)
    find_python_package(nbformat)
    lookup_python_package(pytest_bdd PIPNAME pytest-bdd)
    # Not required per se but usefull for testing process
    find_python_package(mpi4py)
    find_program(MPIEXEC NAMES mpiexec mpirun)
endif()

find_python_package(IPython)
find_python_package(numpy)

include(FetchContent)
FetchContent_Declare(
  quantities
  GIT_REPOSITORY https://github.com/python-quantities/python-quantities.git@refs/pull/235/head
  GIT_TAG        b6efa33bb86d2c4a1dcfa4ca81927564a4b2f055 # commit "full separate numpy > 2.0 array wrap" on Jul 24 2024 from PR 235 
  OVERRIDE_FIND_PACKAGE
)
find_python_package(quantities)

find_python_package(f90nml)
find_python_package(six)
find_python_package(traitlets)
# only needed for build. So can install it locally in build dir.
lookup_python_package(cython)
# Finds additional info, like libraries, include dirs...
# no need check numpy features, it's all handled by cython.
set(no_numpy_feature_tests TRUE)
find_package(Numpy REQUIRED)
