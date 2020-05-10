#!/usr/bin/env python

import os
import re

import unasync  # requires pip>=10.0 for PEP 518 support
from setuptools import setup


# Get the version (borrowed from SQLAlchemy)
base_path = os.path.dirname(__file__)
with open(os.path.join(base_path, "src", "ahip", "__init__.py")) as fp:
    version = re.match(r".*__version__ = \"(.*?)\"", fp.read(), re.S).group(1)

setup(
    version=version,
    cmdclass={
        "build_py": unasync.cmdclass_build_py(
            rules=[
                unasync.Rule(
                    "/ahip/",
                    "/hip/",
                    additional_replacements={
                        "anext": "next",
                        "await_if_coro": "return_non_coro",
                    },
                )
            ]
        )
    },
)
