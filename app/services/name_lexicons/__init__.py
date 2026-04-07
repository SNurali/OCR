from .central_asia import FIRST_NAMES as CENTRAL_ASIA_FIRST_NAMES
from .central_asia import SURNAMES as CENTRAL_ASIA_SURNAMES
from .cis import FIRST_NAMES as CIS_FIRST_NAMES
from .cis import SURNAMES as CIS_SURNAMES
from .europe_latam import FIRST_NAMES as EUROPE_LATAM_FIRST_NAMES
from .europe_latam import SURNAMES as EUROPE_LATAM_SURNAMES
from .mena_asia import FIRST_NAMES as MENA_ASIA_FIRST_NAMES
from .mena_asia import SURNAMES as MENA_ASIA_SURNAMES


COMMON_FIRST_NAMES = (
    CENTRAL_ASIA_FIRST_NAMES
    | CIS_FIRST_NAMES
    | EUROPE_LATAM_FIRST_NAMES
    | MENA_ASIA_FIRST_NAMES
)

COMMON_SURNAME_WORDS = (
    CENTRAL_ASIA_SURNAMES | CIS_SURNAMES | EUROPE_LATAM_SURNAMES | MENA_ASIA_SURNAMES
)


REGIONAL_NAME_LEXICONS = {
    "central_asia": {
        "first_names": CENTRAL_ASIA_FIRST_NAMES,
        "surnames": CENTRAL_ASIA_SURNAMES,
    },
    "cis": {
        "first_names": CIS_FIRST_NAMES,
        "surnames": CIS_SURNAMES,
    },
    "europe_latam": {
        "first_names": EUROPE_LATAM_FIRST_NAMES,
        "surnames": EUROPE_LATAM_SURNAMES,
    },
    "mena_asia": {
        "first_names": MENA_ASIA_FIRST_NAMES,
        "surnames": MENA_ASIA_SURNAMES,
    },
}
