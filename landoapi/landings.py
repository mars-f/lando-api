# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import hashlib
import json


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
