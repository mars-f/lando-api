# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from werkzeug.exceptions import abort

from landoapi import auth
from landoapi.decorators import require_phabricator_api_key

logger = logging.getLogger(__name__)


@auth.require_auth0(())
@require_phabricator_api_key(optional=False)
def submit_sanitized_commit_message(revision_phid=None, sanitized_message=None):
    """Update a Revision with a sanitized commit message.

    Args:
        revision_phid: The PHID of the revision that will have a sanitized commit
            message.
        sanitized_message: The sanitized commit message.
    """
    logger.debug(
        "Got request to update revision with a sanitized message",
        extra=dict(revision_phid=revision_phid, sanitized_message=sanitized_message),
    )

    # Only secure revisions are allowed to follow the sec-approval process.
    # abort(400, )
    return "OK", 200
