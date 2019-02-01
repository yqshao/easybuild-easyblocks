##
# Copyright 2017-2019 Ghent University
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
EasyBuild support for building and installing TensorRT, implemented as an easyblock

@author: Ake Sandgren (Umea University)
"""
import glob
import os

from easybuild.easyblocks.generic.binary import Binary
from easybuild.easyblocks.generic.pythonpackage import PythonPackage
from easybuild.framework.easyblock import EasyBlock
from easybuild.tools.build_log import EasyBuildError
from easybuild.tools.modules import get_software_version
from easybuild.tools.run import run_cmd


class EB_TensorRT(PythonPackage, Binary):
    """Support for building/installing TensorRT."""

    @staticmethod
    def extra_options():
        """Define custom easyconfig parameters for TensorRT."""

        # Combine extra variables from Binary and PythonPackage easyblocks
        extra_vars = Binary.extra_options()
        extra_vars = PythonPackage.extra_options(extra_vars)
        return EasyBlock.extra_options(extra_vars)

    def __init__(self, *args, **kwargs):
        """Initialize TensorRT easyblock."""
        super(EB_TensorRT, self).__init__(*args, **kwargs)

        # Setup for the Binary easyblock
        self.cfg['extract_sources'] = True
        self.cfg['keepsymlinks'] = True

        # Setup for the PythonPackage easyblock
        self.cfg['exts_defaultclass'] = 'PythonPackage'

        self.cfg['exts_default_options'] = {
            'download_dep_fail': True,
            'use_pip': True,
        }

    def configure_step(self):
        """Custom configuration procedure for TensorRT."""
        pass

    def build_step(self):
        """Custom build procedure for TensorRT."""
        pass

    def test_step(self):
        """No (reliable) custom test procedure for TensorRT."""
        pass

    def install_step(self):
        """Custom install procedure for TensorRT."""

        # Make the basic installation of the binaries etc
        Binary.install_step(self)

    def extensions_step(self):
        """Custom extensions procedure for TensorRT."""

        super(EB_TensorRT, self).extensions_step()

        pyver = ''.join(get_software_version('Python').split('.')[:2])
        whls = [
            os.path.join('graphsurgeon', 'graphsurgeon-*-py2.py3-none-any.whl'),
            os.path.join('uff', 'uff-*-py2.py3-none-any.whl'),
            os.path.join('python', 'tensorrt-%s-cp%s-*-linux_x86_64.whl' % (self.version, pyver)),
        ]
        for whl in whls:
            whl_paths = glob.glob(os.path.join(self.installdir, whl))
            if len(whl_paths) == 1:
                # --ignore-installed is required to ensure *this* wheel is installed
                cmd = "pip install --ignore-installed --prefix=%s %s" % (self.installdir, whl_paths[0])

                # if extensions are listed, assume they will provide all required dependencies,
                # so use --no-deps to prevent pip from downloading & installing them
                if self.cfg['exts_list']:
                    cmd += ' --no-deps'

                run_cmd(cmd, log_all=True, simple=True, log_ok=True)
            else:
                raise EasyBuildError("Failed to isolate .whl in %s: %s", whl_paths, self.installdir)

    def sanity_check_step(self):
        """Custom sanity check for TensorRT."""
        custom_paths = {
            'files': ['bin/trtexec', 'lib/libnvinfer.a'],
            'dirs': [self.pylibdir],
        }

        custom_commands = [
            "%s -c 'import tensorrt'" % self.python_cmd,
        ]
        res = super(EB_TensorRT, self).sanity_check_step(custom_paths=custom_paths, custom_commands=custom_commands)

        return res
