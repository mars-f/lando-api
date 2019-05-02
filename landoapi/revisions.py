# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import inspect
import logging
from collections import Counter

from landoapi.phabricator import PhabricatorClient, RevisionStatus, EditOperation
from landoapi.projects import get_secure_project_phid

# The PHID of the Phabricator project containing members of the Secure
# Bug Approval Process.
# See https://wiki.mozilla.org/Security/Bug_Approval_Process.
SEC_APPROVAL_PROJECT_PHID = "PHID-PROJECT-7777"

logger = logging.getLogger(__name__)
dedent = inspect.cleandoc


def gather_involved_phids(revision):
    """Return the set of Phobject phids involved in a revision.

    At the time of writing Users and Projects are the type of Phobjects
    which may author or review a revision.
    """
    attachments = PhabricatorClient.expect(revision, "attachments")

    entities = {PhabricatorClient.expect(revision, "fields", "authorPHID")}
    entities.update(
        {
            PhabricatorClient.expect(r, "reviewerPHID")
            for r in PhabricatorClient.expect(attachments, "reviewers", "reviewers")
        }
    )
    entities.update(
        {
            PhabricatorClient.expect(r, "reviewerPHID")
            for r in PhabricatorClient.expect(
                attachments, "reviewers-extra", "reviewers-extra"
            )
        }
    )
    return entities


def serialize_author(phid, user_search_data):
    out = {"phid": phid, "username": None, "real_name": None}
    author = user_search_data.get(phid)
    if author is not None:
        out["username"] = PhabricatorClient.expect(author, "fields", "username")
        out["real_name"] = PhabricatorClient.expect(author, "fields", "realName")

    return out


def serialize_diff(diff):
    author_name, author_email = select_diff_author(diff)
    fields = PhabricatorClient.expect(diff, "fields")

    return {
        "id": PhabricatorClient.expect(diff, "id"),
        "phid": PhabricatorClient.expect(diff, "phid"),
        "date_created": PhabricatorClient.to_datetime(
            PhabricatorClient.expect(fields, "dateCreated")
        ).isoformat(),
        "date_modified": PhabricatorClient.to_datetime(
            PhabricatorClient.expect(fields, "dateModified")
        ).isoformat(),
        "author": {"name": author_name or "", "email": author_email or ""},
    }


def serialize_status(revision):
    status_value = PhabricatorClient.expect(revision, "fields", "status", "value")
    status = RevisionStatus.from_status(status_value)

    if status is RevisionStatus.UNEXPECTED_STATUS:
        logger.warning(
            "Revision had unexpected status",
            extra={
                "id": PhabricatorClient.expection(revision, "id"),
                "value": status_value,
            },
        )
        return {"closed": False, "value": None, "display": "Unknown"}

    return {
        "closed": status.closed,
        "value": status.value,
        "display": status.output_name,
    }


def select_diff_author(diff):
    commits = PhabricatorClient.expect(diff, "attachments", "commits", "commits")
    if not commits:
        return None, None

    authors = [c.get("author", {}) for c in commits]
    authors = Counter((a.get("name"), a.get("email")) for a in authors)
    authors = authors.most_common(1)
    return authors[0][0] if authors else (None, None)


def get_bugzilla_bug(revision):
    bug = PhabricatorClient.expect(revision, "fields").get("bugzilla.bug-id")
    return int(bug) if bug else None


def check_diff_author_is_known(*, diff, **kwargs):
    author_name, author_email = select_diff_author(diff)
    if author_name and author_email:
        return None

    return (
        "Diff does not have proper author information in Phabricator. "
        "See the Lando FAQ for help with this error."
    )


def check_author_planned_changes(*, revision, **kwargs):
    status = RevisionStatus.from_status(
        PhabricatorClient.expect(revision, "fields", "status", "value")
    )
    if status is not RevisionStatus.CHANGES_PLANNED:
        return None

    return "The author has indicated they are planning changes to this revision."


def revision_is_secure(revision, phabclient):
    """Does the given revision contain security-sensitive data?

    Such revisions should be handled according to the Security Bug Approval Process.
    See https://wiki.mozilla.org/Security/Bug_Approval_Process.

    Args:
        revision: The 'data' element from a Phabricator API response containing
            revision data.
        phabclient: A PhabricatorClient instance.
    """
    secure_project_phid = get_secure_project_phid(phabclient)
    revision_project_tags = phabclient.expect(
        revision, "attachments", "projects", "projectPHIDs"
    )
    is_secure = secure_project_phid in revision_project_tags
    logger.debug(
        "revision is security-sensitive?",
        extra={"value": is_secure, "revision": revision["id"]},
    )
    return is_secure


def send_sanitized_commit_message_for_review(revision_phid, message, phabclient):
    """Send a sanitized commit message for review by the sec-approval team.

    See https://wiki.mozilla.org/Security/Bug_Approval_Process.

    Args:
        revision_phid: The PHID of the revision to edit.
        message: The sanitized commit message string we want to be reviewed.
        phabclient: A PhabClient instance.
    """
    comment = format_sanitized_message_comment_for_review(message)
    edit = EditOperation("differential.revision.edit", revision_phid)
    # The caller's alternative commit message is published as a comment.
    edit.add_transaction("comment", comment)
    # We must get one of the sec-approval project members to approve the alternate
    # commit message for the review to proceed. NOTE: the 'blocking(PHID)' syntax is
    # undocumented at the time of writing.
    blocking_reviewer = f"blocking({SEC_APPROVAL_PROJECT_PHID})"
    edit.add_transaction("reviewers.add", [blocking_reviewer])
    edit.send_edit(phabclient)


def format_sanitized_message_comment_for_review(message):
    """Turn a commit message into a formatted Phabricator comment.

    The message is formatted to guide the next steps in the Security
    Bug Approval Process.  People reading the revision and this comment
    in the discussion thread should understand the steps necessary to move
    the approval process forward.

    See https://wiki.mozilla.org/Security/Bug_Approval_Process.

    Args:
        message: The commit message to be reviewed.
    """
    # The message is written in first-person form because it is being authored by the
    # user in Lando and posted under their username.
    #
    # The message is formatted as Remarkup.
    # See https://phabricator.services.mozilla.com/book/phabricator/article/remarkup/
    return dedent(
        f"""
        I have written a sanitized comment message for this revision. It should 
        follow the [Security Bug Approval Guidelines](https://wiki.mozilla.org/Security/Bug_Approval_Process).
        
        ````
        {message}
        ````
        
        Could a member of the `sec-approval` team please review this message?
        If the message is suitable for landing in mozilla-central please mark
        this code review as `Accepted`.
    """ # noqa
    )
