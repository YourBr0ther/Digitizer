import os
import tempfile

import pytest


@pytest.fixture
def tmp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def tmp_output_dir(tmp_path):
    out = tmp_path / "output" / "dvd"
    out.mkdir(parents=True)
    return str(out)
