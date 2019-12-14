from xml.etree import ElementTree as ET
import os
import re
import shutil
import sys

import nox


def _clean_coverage(coverage_path):
    input_xml = ET.ElementTree(file=coverage_path)
    for class_ in input_xml.findall(".//class"):
        filename = class_.get("filename")
        filename = re.sub("_sync", "_async", filename)
        class_.set("filename", filename)
    input_xml.write(coverage_path, xml_declaration=True)


def tests_impl(session, extras="socks,secure,brotli"):
    # Install deps and the package itself.
    session.install("-r", "dev-requirements.txt")
    session.install(".[{extras}]".format(extras=extras))

    # Show the pip version.
    session.run("pip", "--version")
    # Print the Python version and bytesize.
    session.run("python", "--version")
    session.run("python", "-c", "import struct; print(struct.calcsize('P') * 8)")
    # Print OpenSSL information.
    session.run("python", "-m", "OpenSSL.debug")

    if session.python != "pypy" and session.python != "2.7":
        session.posargs.extend(["--random-order"])

    session.run(
        "pytest",
        "-r",
        "a",
        "--tb=native",
        "--cov=hip",
        "--no-success-flaky-report",
        *(session.posargs or ("test/",)),
        env={"PYTHONWARNINGS": "always::DeprecationWarning"}
    )
    session.run("coverage", "xml")
    _clean_coverage("coverage.xml")


@nox.session(python=["2.7", "3.5", "3.6", "3.7", "3.8", "pypy", "pypy3"])
def test(session):
    tests_impl(session)


@nox.session(python=["2.7", "3.7"])
def google_brotli(session):
    # https://pypi.org/project/Brotli/ is the Google version of brotli, so
    # install it separately and don't install our brotli extra (which installs
    # brotlipy).
    session.install("brotli")
    tests_impl(session, extras="socks,secure")


@nox.session()
def blacken(session):
    """Run black code formatter."""
    session.install("black")
    session.run("black", "src", "dummyserver", "test", "noxfile.py", "setup.py")

    lint(session)


@nox.session
def lint(session):
    session.install("flake8", "black")
    session.run("flake8", "--version")
    session.run("black", "--version")
    session.run(
        "black", "--check", "src", "dummyserver", "test", "noxfile.py", "setup.py"
    )
    session.run("flake8", "setup.py", "docs", "dummyserver", "src", "test")


@nox.session
def docs(session):
    session.install("-r", "docs/requirements.txt")
    session.install(".[socks,secure,brotli]")

    session.chdir("docs")
    if os.path.exists("_build"):
        shutil.rmtree("_build")
    session.run("sphinx-build", "-W", ".", "_build/html")
