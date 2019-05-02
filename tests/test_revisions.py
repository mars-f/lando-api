# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from unittest.mock import ANY, patch

import landoapi
from landoapi.phabricator import RevisionStatus
from landoapi.revisions import (
    check_author_planned_changes,
    check_diff_author_is_known,
    revision_is_secure,
    format_sanitized_message_comment_for_review,
    send_sanitized_commit_message_for_review,
)

pytestmark = pytest.mark.usefixtures("docker_env_vars")


def test_check_diff_author_is_known_with_author(phabdouble):
    phab = phabdouble.get_phabricator_client()
    # Adds author information by default.
    d = phabdouble.diff()
    phabdouble.revision(diff=d, repo=phabdouble.repo())

    diff = phab.call_conduit(
        "differential.diff.search",
        constraints={"phids": [d["phid"]]},
        attachments={"commits": True},
    )["data"][0]

    assert check_diff_author_is_known(diff=diff) is None


def test_check_diff_author_is_known_with_unknown_author(phabdouble):
    phab = phabdouble.get_phabricator_client()
    # No commits for no author data.
    d = phabdouble.diff(commits=[])
    phabdouble.revision(diff=d, repo=phabdouble.repo())

    diff = phab.call_conduit(
        "differential.diff.search",
        constraints={"phids": [d["phid"]]},
        attachments={"commits": True},
    )["data"][0]

    assert check_diff_author_is_known(diff=diff) is not None


@pytest.mark.parametrize(
    "status", [s for s in RevisionStatus if s is not RevisionStatus.CHANGES_PLANNED]
)
def test_check_author_planned_changes_changes_not_planned(phabdouble, status):
    phab = phabdouble.get_phabricator_client()
    r = phabdouble.revision(status=status)

    revision = phab.call_conduit(
        "differential.revision.search",
        constraints={"phids": [r["phid"]]},
        attachments={"reviewers": True, "reviewers-extra": True, "projects": True},
    )["data"][0]
    assert check_author_planned_changes(revision=revision) is None


def test_check_author_planned_changes_changes_planned(phabdouble):
    phab = phabdouble.get_phabricator_client()
    r = phabdouble.revision(status=RevisionStatus.CHANGES_PLANNED)

    revision = phab.call_conduit(
        "differential.revision.search",
        constraints={"phids": [r["phid"]]},
        attachments={"reviewers": True, "reviewers-extra": True, "projects": True},
    )["data"][0]
    assert check_author_planned_changes(revision=revision) is not None


def test_secure_api_flag_on_public_revision_is_false(client, phabdouble):
    public_project = phabdouble.project("public")
    revision = phabdouble.revision(projects=[public_project])

    response = client.get("/stacks/D{}".format(revision["id"]))

    assert response.status_code == 200
    response_revision = response.json["revisions"].pop()
    assert not response_revision["is_secure"]


def test_secure_api_flag_on_secure_revision_is_true(client, phabdouble, secure_project):
    revision = phabdouble.revision(projects=[secure_project])

    response = client.get("/stacks/D{}".format(revision["id"]))

    assert response.status_code == 200
    response_revision = response.json["revisions"].pop()
    assert response_revision["is_secure"]


def test_public_revision_is_not_secure(app, phabdouble):
    phab = phabdouble.get_phabricator_client()
    r = phabdouble.revision(projects=[])
    revision = phab.call_conduit(
        "differential.revision.search",
        constraints={"phids": [r["phid"]]},
        attachments={"reviewers": True, "reviewers-extra": True, "projects": True},
    )["data"].pop()
    assert not revision_is_secure(revision, phab)


def test_secure_revision_is_secure(app, phabdouble, secure_project):
    phab = phabdouble.get_phabricator_client()
    r = phabdouble.revision(projects=[secure_project])
    revision = phab.call_conduit(
        "differential.revision.search",
        constraints={"phids": [r["phid"]]},
        attachments={"reviewers": True, "reviewers-extra": True, "projects": True},
    )["data"].pop()
    assert revision_is_secure(revision, phab)


def test_send_sanitized_commit_message(phabdouble):
    phab = phabdouble.get_phabricator_client()
    r = phabdouble.revision()

    with patch.object(phab, "call_conduit", wraps=phab.call_conduit) as spy:
        send_sanitized_commit_message_for_review(r["phid"], "my message", phab)
        sec_approval_group = landoapi.revisions.SEC_APPROVAL_PROJECT_PHID
        spy.assert_called_once_with(
            "differential.revision.edit",
            objectIdentifier=r["phid"],
            transactions=[
                {"type": "comment", "value": ANY},
                {"type": "reviewers.add", "value": [f"blocking({sec_approval_group})"]},
            ],
        )
