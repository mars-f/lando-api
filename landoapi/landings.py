# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import hashlib
import json
from typing import NamedTuple

from connexion import ProblemException
from flask import g

from landoapi.validation import revision_id_to_int


class LandingAssessment:
    """Represents an assessment of issues that may block a revision landing.

    Attributes:
        warnings: List of warning dictionaries. Each dict must have an 'id'
            key holding the warning ID. e.g. {'id': 'W201', ...}
        problems: List of problem dictionaries Each dict must have an 'id'
            key holding the problem ID. e.g. {'id': 'E406', ...}
    """

    def __init__(self, warnings, problems):
        self.warnings = warnings
        self.problems = problems

    def to_dict(self):
        """Return the assessment as a dict.

        Includes the appropriate confirmation_token for any warnings present.
        """
        return {
            'confirmation_token': self.hash_warning_list(),
            'warnings': self.warnings,
            'problems': self.problems,
        }

    def hash_warning_list(self):
        """Return a hash of our warning dictionaries.

        Hashes are generated in a cross-machine comparable way.

        This function takes a list of warning dictionaries.  Each dictionary
        must have an 'id' key that holds the unique warning ID.

        E.g.:
        [
            {'id': 'W201', ...},
            {'id': 'W500', ...},
            ...
        ]

        This function generates a hash of warnings dictionaries that can be
        passed to a client across the network, then returned by that client
        and compared to the warnings in a new landing process.  That landing
        process could be happening on a completely different machine than the
        one that generated the original hash.  This function goes to pains to
        ensure that a hash of the same set of warning list dictionaries on
        separate machines will match.

        Args:
            warning_list: A list of warning dictionaries.  The 'id' key and
                value must be JSON-serializable.

        Returns: String.  Returns None if given an empty list.
        """
        if not self.warnings:
            return None

        # The warning ID and message should be stable across machines.

        # First de-duplicate the list of dicts using the ID field.  If there
        # is more than one warning with the same ID and different fields then
        # the last entry in the warning list wins.
        warnings_dict = dict((w['id'], w) for w in self.warnings)

        # Assume we are trying to encode a JSON-serializable warning_list
        # structure - keys and values are only simple types, not objects.  A
        # TypeError will be thrown if the caller accidentally tries to
        # serialize something funky. Also sort the warning dict items and
        # nested dict items so the same hash can be generated on different
        # machines. See https://stackoverflow.com/a/10288255 and
        # https://stackoverflow.com/questions/5884066/hashing-a-dictionary
        # for a discussion of why this is tricky!
        warnings_json = json.dumps(
            warnings_dict, sort_keys=True
        ).encode('UTF-8')
        return hashlib.sha256(warnings_json).hexdigest()


LandingRequestData = NamedTuple(
    'LandingRequestData', [
        ('revision_id', int),
        ('diff_id', int),
        ('overriding_diff_id', int),
        ('active_diff_id', int),
    ]
)


def collect_landing_request_data(post_data):
    # FIXME instead of pre-fetching, could we cache the phabricator responses?
    revision_id = revision_id_to_int(post_data['revision_id'])
    revision = g.phabricator.get_revision(id=revision_id)
    # FIXME add empty revison check
    #     if not revision:
    #         raise RevisionNotFoundException(revision_id)
    active_diff_id = g.phabricator.diff_phid_to_id(revision['activeDiffPHID'])
    return LandingRequestData(
        revision_id=revision_id,
        diff_id=post_data['diff_id'],
        overriding_diff_id=post_data.get('force_override_of_diff_id'),
        active_diff_id=active_diff_id
    )


def has_valid_email():
    return g.auth0_user.email


def has_sufficient_scm_level():
    return g.auth0_user.can_land_changes()


def is_requested_diff_active(landing_data):
    return bool(landing_data.diff_id == landing_data.active_diff_id)


def is_overriding_diff_active(landing_data):
    return bool(landing_data.overriding_diff_id == landing_data.active_diff_id)


LandingProblem = NamedTuple(
    'LandingProblem',
    [
        ('status_code', int),
        ('error_id', str),
        ('title', str),
        ('detail', str),
        ('error_type', str),  # FIXME docstring to explain contents
    ]
)

# def validate_diff_id(phab, revision_id, diff_to_land, overriding_diff_id):
#     revision = phab.get_revision(id=revision_id)
#
#     if not revision:
#         raise RevisionNotFoundException(revision_id)
#
#     # Validate overriding of the diff id.
#     active_id = phab.diff_phid_to_id(revision['activeDiffPHID'])
#     # If diff used to land revision is not the active one Lando API will
#     # fail with a 409 error. The client will then inform the user that
#     # Lando API might be forced to land that diff if that's what the user
#     # wants.
#     # In such case the client will request a new landing with a
#     # force_override_of_diff_id parameter equal to the active diff id.
#     # API will proceed with the landing.
#     if overriding_diff_id:
#         if overriding_diff_id != active_id:
#             raise OverrideDiffException(
#                 diff_to_land, active_id, overriding_diff_id
#             )
#         logger.warning(
#             {
#                 'revision_id': revision_id,
#                 'diff_id': diff_to_land,
#                 'active_diff_id': active_id,
#                 'overriding_diff_id': overriding_diff_id,
#                 'msg': 'Forced to override the active Diff'
#             }, 'landing.warning'
#         )
#     elif diff_id != active_id:
#         raise InactiveDiffException(diff_id, active_id)

# def get_ui_diff_id_warning(phab, revision_id, diff_to_land, overriding_diff_id):
#     # FIXME this can be lifted
#     revision = phab.get_revision(id=revision_id)
#
#     if not revision:
#         raise RevisionNotFoundException(revision_id)
#
#
#     # Check if a newer diff is available to land.
#     # if revision['diff']['id'] < revision['latest_diff_id']:
#     active_id = phab.diff_phid_to_id(revision['activeDiffPHID'])
#     if revision['diff']['id'] < active_id:
#         # add_warning(
#         #     id='warning-not-latest-diff',
#         #     text='You are viewing Diff {old_diff_id}, but, Diff {new_diff_id} '
#         #     'is now the latest diff of this revision.'.format(
#         #         old_diff_id=revision['diff']['id'],
#         #         new_diff_id=revision['latest_diff_id']
#         #     )
#         # )
#         return warning_for_problem(DiffInactive)

HTTPNotAuthorized = LandingProblem(
    status_code=403,
    error_id='E1',
    title='Not Authorized',
    detail='You\'re not authorized to proceed.',
    error_type='https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403',
)
UnverifiedEmail = LandingProblem(
    status_code=403,
    error_id='E2',
    title='Unverified email',
    detail='You do not have a Mozilla verified email address.',
    # FIXME: type URL should point to the API documentation
    error_type='https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403',
)
InsufficientSCMLevel = LandingProblem(
    status_code=403,
    error_id='E3',
    title='Insufficient SCM level',
    detail='You do not have the required permissions to request landing.',
    # FIXME: type URL should point to the API documentation
    error_type='https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403',
)
InactiveDiff = LandingProblem(
    status_code=403,
    error_id='E4',
    title='Inactive diff FOO',  # FIXME
    detail='Inactive diff BAR',  # FIXME
    # FIXME: type URL should point to the API documentation
    error_type='https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403',
)
InactiveOverridingDiff = LandingProblem(
    status_code=403,
    error_id='E5',
    title='Inactive overriding diff FOO',  # FIXME
    detail='Inactive overriding diff BAR',  # FIXME
    # FIXME: type URL should point to the API documentation
    error_type='https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403',
)


def validate_any(predicate, problem_details):
    def _validate(*args, warn_only=False, **kwargs):
        if not predicate(*args, **kwargs):
            if warn_only:
                return warning_for_problem(problem_details)
            else:
                raise_problem(problem_details)

    return _validate


def warning_for_problem(problem_details):
    return {'id': problem_details.error_id}


def raise_problem(problem_details):
    raise ProblemException(
        status=problem_details.status_code,
        title=problem_details.title,
        detail=problem_details.detail,
        type=problem_details.error_type
    )


def validate_diff_ids(landing_data, warn_only=False):
    if landing_data.overriding_diff_id:
        return validate_overriding_diff(landing_data, warn_only=warn_only)
    else:
        return validate_requested_diff(landing_data, warn_only=warn_only)


validate_email = validate_any(has_valid_email, UnverifiedEmail)
validate_scm_level = validate_any(
    has_sufficient_scm_level, InsufficientSCMLevel
)
validate_requested_diff = validate_any(is_requested_diff_active, InactiveDiff)
validate_overriding_diff = validate_any(is_overriding_diff_active, InactiveOverridingDiff)
