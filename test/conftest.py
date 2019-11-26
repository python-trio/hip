import platform
import sys

import pytest

# We support Python 3.6+ for async code
if sys.version_info[:2] < (3, 6):
    collect_ignore_glob = ["async/*.py", "with_dummyserver/async/*.py"]

# The Python 3.8+ default loop on Windows breaks Tornado
@pytest.fixture(scope="session", autouse=True)
def configure_windows_event_loop():
    if sys.version_info >= (3, 8) and platform.system() == "Windows":
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
