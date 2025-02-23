##
# Copyright 2009-2025 Ghent University
#
# This file is part of EasyBuild,
# originally created by the HPC team of Ghent University (http://ugent.be/hpc/en),
# with support of Ghent University (http://ugent.be/hpc),
# the Flemish Supercomputer Centre (VSC) (https://www.vscentrum.be),
# Flemish Research Foundation (FWO) (http://www.fwo.be/en)
# and the Department of Economy, Science and Innovation (EWI) (http://www.ewi-vlaanderen.be/en).
#
# https://github.com/easybuilders/easybuild
#
# EasyBuild is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation v2.
#
# EasyBuild is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with EasyBuild.  If not, see <http://www.gnu.org/licenses/>.
##
"""
EasyBuild support for building and installing the libsmm library, implemented as an easyblock

@author: Stijn De Weirdt (Ghent University)
@author: Dries Verdegem (Ghent University)
@author: Kenneth Hoste (Ghent University)
@author: Pieter De Baets (Ghent University)
@author: Jens Timmerman (Ghent University)
"""

import os
from easybuild.tools import LooseVersion

import easybuild.tools.toolchain as toolchain
from easybuild.framework.easyblock import EasyBlock
from easybuild.framework.easyconfig import CUSTOM
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.filetools import copy_dir
from easybuild.tools.modules import get_software_version
from easybuild.tools.run import run_cmd


class EB_libsmm(EasyBlock):
    """
    Support for the CP2K small matrix library
    Notes: - build can take really really long, and no real rebuilding needed for each get_version
           - CP2K can be built without this
    """

    @staticmethod
    def extra_options():
        # default dimensions
        dd = [1, 4, 5, 6, 9, 13, 16, 17, 22]
        extra_vars = {
            'transpose_flavour': [1, "Transpose flavour of routines", CUSTOM],
            'max_tiny_dim': [12, "Maximum tiny dimension", CUSTOM],
            'dims': [dd, "Generate routines for these matrix dims", CUSTOM],
        }
        return EasyBlock.extra_options(extra_vars)

    def configure_step(self):
        """Configure build: change to tools/build_libsmm dir"""
        try:
            dst = 'tools/build_libsmm'
            os.chdir(dst)
            self.log.debug('Change to directory %s' % dst)
        except OSError as err:
            raise EasyBuildError("Failed to change to directory %s: %s", dst, err)

    def build_step(self):
        """Build libsmm
        Possible iterations over precision (single/double) and type (real/complex)
        - also type of transpose matrix
        - all set in the config file

        Make the config.in file (is source afterwards in the build)
        """

        fn = 'config.in'
        cfg_tpl = """# This config file was generated by EasyBuild

# the build script can generate optimized routines packed in a library for
# 1) 'nn' => C=C+MATMUL(A,B)
# 2) 'tn' => C=C+MATMUL(TRANSPOSE(A),B)
# 3) 'nt' => C=C+MATMUL(A,TRANSPOSE(B))
# 4) 'tt' => C=C+MATMUL(TRANPOSE(A),TRANPOSE(B))
#
# select a tranpose_flavor from the list 1 2 3 4
#
transpose_flavor=%(transposeflavour)s

# 1) d => double precision real
# 2) s => single precision real
# 3) z => double precision complex
# 4) c => single precision complex
#
# select a data_type from the list 1 2 3 4
#
data_type=%(datatype)s

# target compiler... this are the options used for building the library.
# They should be aggessive enough to e.g. perform vectorization for the specific CPU
# (e.g. -ftree-vectorize -march=native),
# and allow some flexibility in reordering floating point expressions (-ffast-math).
# Higher level optimisation (in particular loop nest optimization) should not be used.
#
target_compile="%(targetcompile)s"

# target dgemm link options... these are the options needed to link blas (e.g. -lblas)
# blas is used as a fall back option for sizes not included in the library or in those cases where it is faster
# the same blas library should thus also be used when libsmm is linked.
#
OMP_NUM_THREADS=1
blas_linking="%(LIBBLAS)s"

# matrix dimensions for which optimized routines will be generated.
# since all combinations of M,N,K are being generated the size of the library becomes very large
# if too many sizes are being optimized for. Numbers have to be ascending.
#
dims_small="%(dims)s"

# tiny dimensions are used as primitves and generated in an 'exhaustive' search.
# They should be a sequence from 1 to N,
# where N is a number that is large enough to have good cache performance
# (e.g. for modern SSE cpus 8 to 12)
# Too large (>12?) is not beneficial, but increases the time needed to build the library
# Too small (<8)   will lead to a slow library, but the build might proceed quickly
# The minimum number for a successful build is 4
#
dims_tiny="%(tiny_dims)s"

# host compiler... this is used only to compile a few tools needed to build the library.
# The library itself is not compiled this way.
# This compiler needs to be able to deal with some Fortran2003 constructs.
#
host_compile="%(hostcompile)s "

# number of processes to use in parallel for compiling / building and benchmarking the library.
# Should *not* be more than the physical (available) number of cores of the machine
#
tasks=%(tasks)s

        """

        # only GCC is supported for now
        if self.toolchain.comp_family() == toolchain.GCC:  # @UndefinedVariable
            hostcompile = os.getenv('F90')

            # optimizations
            opts = "-O2 -funroll-loops -ffast-math -ftree-vectorize -march=native -fno-inline-functions"

            # Depending on the get_version, we need extra options
            extra = ''
            gccVersion = LooseVersion(get_software_version('GCC'))
            if gccVersion >= LooseVersion('4.6'):
                extra = "-flto"

            targetcompile = "%s %s %s" % (hostcompile, opts, extra)
        else:
            raise EasyBuildError("No supported compiler found (tried GCC)")

        if not os.getenv('LIBBLAS'):
            raise EasyBuildError("No BLAS library specifications found (LIBBLAS not set)!")

        cfgdict = {
            'datatype': None,
            'transposeflavour': self.cfg['transpose_flavour'],
            'targetcompile': targetcompile,
            'hostcompile': hostcompile,
            'dims': ' '.join([str(d) for d in self.cfg['dims']]),
            'tiny_dims': ' '.join([str(d) for d in range(1, self.cfg['max_tiny_dim'] + 1)]),
            'tasks': self.cfg['parallel'],
            'LIBBLAS': "%s %s" % (os.getenv('LDFLAGS'), os.getenv('LIBBLAS'))
        }

        # configure for various iterations
        datatypes = [(1, 'double precision real'), (3, 'double precision complex')]

        for (dt, descr) in datatypes:
            cfgdict['datatype'] = dt
            try:
                txt = cfg_tpl % cfgdict
                f = open(fn, 'w')
                f.write(txt)
                f.close()
                self.log.debug("config file %s for datatype %s ('%s'): %s" % (fn, dt, descr, txt))
            except IOError as err:
                raise EasyBuildError("Failed to write %s: %s", fn, err)

            self.log.info("Building for datatype %s ('%s')..." % (dt, descr))
            run_cmd("./do_clean")
            run_cmd("./do_all")

    def install_step(self):
        """Install CP2K: clean, and copy lib directory to install dir"""

        run_cmd("./do_clean")
        copy_dir('lib', os.path.join(self.installdir, 'lib'))

    def sanity_check_step(self):
        """Custom sanity check for libsmm"""

        custom_paths = {
            'files': ["lib/libsmm_%s.a" % x for x in ["dnn", "znn"]],
            'dirs': [],
        }

        super(EB_libsmm, self).sanity_check_step(custom_paths=custom_paths)
