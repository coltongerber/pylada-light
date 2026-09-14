pylada-crystal
==============

.. image:: https://travis-ci.org/pylada/pylada-light.svg?branch=master
    :align: left
    :target: https://travis-ci.org/pylada/pylada-light

A python computational physics framework.

Minimal version of pylada necessary to just run the crystal,VASP,ewald,jobs,and
database modules

Constructed by Peter Graf from Mayeul d'Avezac's pylada

Usage
-----

There are some IPython notebooks in the notebooks subdirectory. And documentation can be found
[online](http://pylada.github.io/pylada-light/), though somewhat out of date. Notably, it does not
describe the PWSCF wrapper.

For more examples, look at the tests in each subfolder, and at the BDD scenarios in the
espresso/tests/bdd/features folder.

Finally, do join us on [slack](pylada.slack.com). Send one of the authors an email if you need
access.

Installation
------------

The simplest approach is to install via
`pip <https://pip.pypa.io/en/latest/>`__:

- global installation

    .. code:: bash

        pip install git+https://github.com/coltongerber/pylada-light

- local (user) installation

    .. code:: bash

        pip install --user git+https://github.com/coltongerber/pylada-light

- in a `virtual environment <https://virtualenv.pypa.io/en/latest/>`__

    .. code:: bash

        python -m venv pylada
        source pylada/bin/activate
        pip install git+https://github.com/coltongerber/pylada-light

    This last approach is recommended since it keeps the pylada environment
    isolated from the rest of the system. Susbsequently, this environment can
    be accessed by running the second line.

Installation for development
----------------------------

- python setup.py develop

    .. code:: bash

        python -m venv pylada
        source pylada/bin/activate
        git clone https://github.com/coltongerber/pylada-light
        cd pylada-light
        python -m pip install "cython<3.1" setuptools wheel scikit-build "cmake>=3.17,<4" ninja numpy
        python -m pip install -e .[dev]
        python setup.py test
        ln -s src/pylada . # because https://github.com/scikit-build/scikit-build/issues/363

    .. note::

        ``cmake`` and ``cython`` are pinned deliberately, matching
        ``build-system.requires`` in ``pyproject.toml``. Both pins are portable — they
        are not specific to any machine:

        - **cython 3.1+** emits ``__pyx_tp_new_vectorcall_*`` references that do not
          compile, on any platform.
        - **cmake 4** removed support for ``cmake_minimum_required(VERSION < 3.5)``.
          When no system Eigen is found, the build downloads Eigen 3.3.7 (see
          ``cmake_modules/eigen/CMakeLists.txt``) and that copy still declares an old
          minimum, so cmake 4 refuses to configure it. Every machine taking the
          download path hits this identically.

        The Eigen download is only a fallback. ``CHECK_FOR_EIGEN_FIRST`` defaults to
        ``ON``, so if Eigen 3.3+ is installed and discoverable (via ``CMAKE_PREFIX_PATH``
        or ``Eigen3_DIR``) it is used and no download happens — which also sidesteps the
        cmake 4 problem. Point ``EIGEN_TAR_ARCHIVE`` at a different archive to override
        the fallback version.

    The above creates a virtual environment and installs pylada inside it in
    development mode. This means that the virtual environment will know about
    the pylada flavor in development. It is possible to edit a file, do
    :bash:`make`, launch python and debug. One just needs to active the
    virtual environment once per session.

    When modifying files that are built (`.pyx`, `.cc`, `.h`), it may be
    necessary to run `python setup.py develop` again.
