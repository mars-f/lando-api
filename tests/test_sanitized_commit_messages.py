# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import pytest


@pytest.fixture(autouse=True)
def preamble(app, monkeypatch):
    # All API acceptance tests need the 'app' fixture to function.

    # Mock a valid API token.
    monkeypatch.setattr(
        "landoapi.decorators.PhabricatorClient.verify_api_token",
        lambda *args, **kwargs: True,
    )


def test_submit_sanitized_commt_message(client, auth0_mock):
    headers = auth0_mock.mock_headers.copy()
    headers.append(("X-Phabricator-API-Key", "custom-key"))
    response = client.post(
        "/submitSanitizedCommitMessage",
        json={"revision_phid": "PHID-DREV-foo", "sanitized_message": "obscure"},
        headers=headers,
    )

    assert 200 == response.status_code


def test_submitting_a_public_revision_fails(client, auth0_mock):
    headers = auth0_mock.mock_headers.copy()
    headers.append(("X-Phabricator-API-Key", "custom-key"))
    response = client.post(
        "/submitSanitizedCommitMessage",
        json={"revision_phid": "PHID-DREV-foo", "sanitized_message": "oops"},
        headers=headers,
    )

    assert 400 == response.status_code
