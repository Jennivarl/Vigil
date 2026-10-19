"""
The pure part of VIGIL. No chain, no network, no model.

Everything that turns a fetched document into "this person is still here"
lives in this file, where it can be tested directly and read by anyone
checking what a handover will eventually turn on.

The three outcomes matter more here than anywhere else:

    alive        the document was fetched and the marker was in it
    silent       the document was fetched and the marker was gone
    unreachable  the document could not be fetched at all

Everything VIGIL does is triggered by absence, and absence is the one signal
that looks identical to a broken network. Counting an outage as silence
would hand somebody's estate to their successor because a server had a bad
afternoon. So `unreachable` advances nothing: it is not a miss, it is the
absence of an observation, and the run of silence is left exactly where it
was.
"""

ALIVE = "alive"
SILENT = "silent"
UNREACHABLE = "unreachable"

# How many consecutive observations must find the marker gone before a
# handover is even eligible. Time passing is not evidence: a pulse nobody
# ever looked at must never become claimable just because it is old. Only
# an agreed `silent` advances this count, an `alive` resets it to zero, and
# an `unreachable` leaves it exactly where it was.
MIN_SILENT_RUNS = 3

# And they must be spread out. Three fetches ten seconds apart are three
# consensus rounds, but they can all catch the same transient glitch: a
# cached error page, a brief deploy, a moment of nonsense from a CDN. A
# confirmation only counts if it is this far from the last one, so three of
# them mean the marker was gone across hours rather than across one bad
# instant. An `alive` observation is never delayed by this, because letting
# somebody prove they are here is always the safe direction.
MIN_OBSERVATION_GAP = 3600

# And the most recent of those must be recent. Eligibility that rests on an
# observation from last year is not a fresh confirmation of anything, so a
# successor has to show the marker is gone now, not that it once was.
SILENCE_FRESH_SECONDS = 7 * 24 * 3600

_MAX_HOST = 100
_MAX_PATH = 200
_MAX_MARKER = 200
_MAX_NAME = 40


def valid_host(host: str) -> bool:
    """
    A bare hostname: letters, digits, dots and hyphens.

    No scheme, no slash, no port. The contract builds the URL itself, so
    anything that could smuggle a second host out of this value is refused
    when the pulse is registered.
    """
    h = (host or "").strip().lower()
    if not h or len(h) > _MAX_HOST or h.startswith(".") or h.endswith(".") or ".." in h:
        return False
    for ch in h:
        if not (("0" <= ch <= "9") or ("a" <= ch <= "z") or ch in "-."):
            return False
    return "." in h


def valid_path(path: str) -> bool:
    """A path that cannot leave itself: no traversal, no scheme, no query."""
    p = (path or "").strip()
    if not p.startswith("/") or len(p) > _MAX_PATH:
        return False
    if ".." in p or "://" in p or "?" in p or "#" in p or "//" in p:
        return False
    return True


def valid_name(name: str) -> bool:
    n = (name or "").strip().lower()
    if not n or len(n) > _MAX_NAME:
        return False
    for ch in n:
        if not (("0" <= ch <= "9") or ("a" <= ch <= "z") or ch in "-_"):
            return False
    return True


def valid_marker(marker: str) -> bool:
    """
    The text that must be present while the owner is around.

    A marker is required rather than optional. Treating "the page loaded" as
    proof of life would mean a parked domain, a hosting placeholder or a
    404 page styled as a 200 could all keep somebody legally alive.
    """
    m = (marker or "").strip()
    if not m or len(m) > _MAX_MARKER:
        return False
    return "\n" not in m and "\r" not in m


def marker_present(body: str, marker: str) -> bool:
    """
    Whether the fetched document still carries the marker.

    A plain substring, deliberately, which is the opposite of the choice
    ATTEST makes about proof tokens. There the risk is a page echoing an
    attacker's text into a proof, so matching is line exact. Here the risk
    runs the other way: a false negative costs somebody their estate, so
    the test is as forgiving as it can be while still meaning something.
    """
    if not marker:
        return False
    return marker.strip() in (body or "")


def url_for(host: str, path: str) -> str:
    return "https://" + host.strip().lower() + path.strip()


def days_between(earlier_seconds, later_seconds):
    """
    Whole days from one instant to another, or None if either is unreadable.

    Days rather than seconds because a threshold is written in days by the
    person who set it, and because nobody should lose an estate over an
    hour's rounding.
    """
    if earlier_seconds is None or later_seconds is None:
        return None
    if later_seconds < earlier_seconds:
        return 0
    return (later_seconds - earlier_seconds) // 86400


def epoch_seconds(stamp: str):
    """
    An ISO-8601 UTC timestamp as a whole number of seconds, or None.

    Only the fixed "YYYY-MM-DDTHH:MM:SS" prefix is read, so a stamp carrying
    fractional seconds is accepted and truncated rather than refused: the
    network writes "2026-10-11T14:42:50.790497Z" and a test writes
    "2026-10-11T14:42:50Z", and those have to mean the same instant.

    Returns None for anything it cannot read, which callers must treat as
    "cannot decide" rather than as zero. Comparing timestamps as text very
    nearly works and then does not, because "Z" sorts after ".".
    """
    s = (stamp or "").strip()
    if len(s) < 19 or s[4] != "-" or s[7] != "-" or s[10] != "T" or s[13] != ":" or s[16] != ":":
        return None
    for i in (0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18):
        if not ("0" <= s[i] <= "9"):
            return None
    year, month, day = int(s[0:4]), int(s[5:7]), int(s[8:10])
    hour, minute, second = int(s[11:13]), int(s[14:16]), int(s[17:19])
    if not (1 <= month <= 12) or day < 1 or day > _days_in_month(year, month):
        return None
    # 60 is allowed because an ISO-8601 stamp may carry a leap second.
    if hour > 23 or minute > 59 or second > 60:
        return None
    return _days_from_civil(year, month, day) * 86400 + hour * 3600 + minute * 60 + second


def _days_in_month(year: int, month: int) -> int:
    """So an impossible date is refused rather than rolling into the next month."""
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return 30 if month in (4, 6, 9, 11) else 31


def _days_from_civil(year: int, month: int, day: int) -> int:
    """
    Days since 1970-01-01, by the usual era arithmetic.

    Integer only and no library, because the same number has to come out on
    every validator. The calendar is the proleptic Gregorian one, which is
    what an ISO-8601 stamp means.
    """
    y = year - (1 if month <= 2 else 0)
    era = (y if y >= 0 else y - 399) // 400
    year_of_era = y - era * 400
    day_of_year = (153 * (month + (-3 if month > 2 else 9)) + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - 719468
