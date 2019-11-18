import sys

# We support Python 3.6+ for async code
if sys.version_info[:2] < (3, 6):
    collect_ignore_glob = ["*/async/*.py", "with_dummyserver/async/*.py"]
