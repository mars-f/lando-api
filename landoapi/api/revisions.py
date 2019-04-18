# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging

from landoapi import auth
from landoapi.decorators import require_phabricator_api_key

logger = logging.getLogger(__name__)


@auth.require_auth0(scopes=("lando", "profile", "email"), userinfo=True)
@require_phabricator_api_key(optional=False)
def patch(revision_id, data):
    """Update a Revision's data.

    NOTE: Updating is only supported for specific attributes.  Those are:
        * commit_message_title
        * commit_message

    Any other attributes will be dropped.
    """
    logger.debug(
        "Got request to update revision via HTTP PATCH",
        extra=dict(revision_id=revision_id, patch_data=data),
    )
    return "OK", 200
