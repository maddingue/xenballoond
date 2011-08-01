#!/usr/bin/env python
import sys
sys.path += ["lib"]

import subprocess
from distutils.command.build import build
from distutils.core import setup
from xenballoond import meta


print "generating manual page"
subprocess.call(["doc/xenballoond_8.PY"])

setup(
    name=meta.name,
    version=meta.version,
    license=meta.license,
    description=meta.description,
    long_description=meta.long_description,
    author=meta.authors,
    url=meta.url,
    classifiers=meta.classifiers,
    packages=["xenballoond"],
    package_dir={"":"lib"},
    scripts=["bin/xenballoond"],
)

