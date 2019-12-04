#!/usr/bin/env python

import os
import re

import unasync  # requires pip>=10.0 for PEP 518 support
from setuptools import setup


# Get the version (borrowed from SQLAlchemy)
base_path = os.path.dirname(__file__)
with open(os.path.join(base_path, "src", "hip", "__init__.py")) as fp:
    version = re.match(r".*__version__ = \"(.*?)\"", fp.read(), re.S).group(1)

setup(version=version, cmdclass={"build_py": unasync.build_py})
