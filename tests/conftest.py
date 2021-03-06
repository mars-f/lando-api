# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import json

import pytest
import requests_mock

from landoapi.app import create_app
from tests.factories import PhabResponseFactory


@pytest.fixture
def docker_env_vars(monkeypatch):
    """Monkeypatch environment variables that we'd get running under docker."""
    monkeypatch.setenv('PHABRICATOR_URL', 'http://phabricator.test')
    monkeypatch.setenv('TRANSPLANT_URL', 'http://autoland.test')
    monkeypatch.setenv('DATABASE_URL', 'sqlite://')


@pytest.fixture
def phabfactory():
    """Mock the Phabricator service and build fake response objects."""
    with requests_mock.mock() as m:
        yield PhabResponseFactory(m)


@pytest.fixture
def versionfile(tmpdir):
    """Provide a temporary version.json on disk."""
    v = tmpdir.mkdir('app').join('version.json')
    v.write(
        json.dumps(
            {
                'source': 'https://github.com/mozilla-conduit/lando-api',
                'version': '0.0.0',
                'commit': '',
                'build': 'test',
            }
        )
    )
    return v


@pytest.fixture
def app(versionfile, docker_env_vars):
    """Needed for pytest-flask."""
    app = create_app(versionfile.strpath)
    return app.app
