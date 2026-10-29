# =============================================================================
# schema.py — The schema registry: every stored table, column by column.
#
# WHY A REGISTRY
#   docs/architecture/data-model.md §3 describes the tables in prose. This file
#   says the same thing in code, so the writer can check a table before it is
#   stored (store.py) and a test can check the rules below. If this file and
#   the data model disagree, one of them is a bug.
#
# EACH COLUMN HAS
#   dtype     one of DTYPES (the Arrow type the column is stored as)
#   nullable  may it hold a real null?
#   licence   U, R, S or F (data model §2.1):
#               U  DoltHub, FRED DTB3, Wikipedia, exchange_calendars or our own
#                  parameters only. Committed.
#               R  a Yahoo or CBOE value for one date or event, or anything that
#                  gives one back. Never committed. Must end in _yf or _cboe.
#               S  a statistic over many restricted values. Committed only under
#                  the export rules.
#               F  a categorical label made with restricted data, from which no
#                  number can be computed (the timing label, a one-time rank).
#                  Committed by default (owner decision, data model §6 item 3).
#   enum      the allowed values of an "enum" column. Never a NULL member.
#
# THE RULE THE TESTS ENFORCE
#   Over value columns (keys excluded), a column is class R exactly when its
#   name ends in _yf or _cboe. A forgotten suffix and a stray suffix both fail.
# =============================================================================

from dataclasses import dataclass, field

DTYPES = ("string", "date32", "int16", "int32", "float64", "bool", "enum")
LICENCES = ("U", "R", "S", "F")
RESTRICTED_SUFFIXES = ("_yf", "_cboe")

GICS_SECTORS = (
    "Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy",
    "Financials", "Health Care", "Industrials", "Information Technology", "Materials",
    "Real Estate", "Utilities",
)
VX_INDICES = ("VXAPL", "VXAZN", "VXGOG", "VXGS", "VXIBM")
TIMING = ("BMO", "AMC")
TIMING_STATUS = (
    "confirmed", "corrected", "inferred", "date_corrected", "no_document", "not_checked", "ambiguous",
)
TIMING_SOURCE = ("edgar", "press_release", "calendar")
SAMPLES = ("daily", "mixed", "coarse", "none")
ERAS = ("none", "weekly", "mwf", "daily")
MATCH_STATUS = ("matched", "orphan", "pre_calendar", "ticker_conflict")
GAP_VERDICT = ("supports", "contradicts", "quiet")
SNAPSHOT_STATUS = ("ok", "stale_repeat", "missing")


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str
    nullable: bool = False
    licence: str = "U"
    key: bool = False          # part of the primary key (keys are never "value columns")
    enum: tuple[str, ...] = ()

    def __post_init__(self):
        if self.dtype not in DTYPES:
            raise ValueError(f"{self.name}: unknown dtype {self.dtype!r}")
        if self.licence not in LICENCES:
            raise ValueError(f"{self.name}: unknown licence class {self.licence!r}")
        if (self.dtype == "enum") != bool(self.enum):
            raise ValueError(f"{self.name}: an enum column needs its values, and only an enum has them")


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    committed: bool                      # does a copy go to data/derived/?
    unique: tuple[tuple[str, ...], ...] = field(default=())   # extra unique keys

    @property
    def primary_key(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.key)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def column(self, name: str) -> Column:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(f"{self.name} has no column {name!r}")

    def value_columns(self) -> tuple[Column, ...]:
        return tuple(c for c in self.columns if not c.key)

    def restricted(self) -> tuple[str, ...]:
        """Names of the class-R columns: they never leave this machine."""
        return tuple(c.name for c in self.columns if c.licence == "R")


def C(name, dtype, nullable=False, licence="U", key=False, enum=()):
    return Column(name, dtype, nullable, licence, key, tuple(enum))


# --- data model §3.1 -----------------------------------------------------------
SECURITY = Table("security", (
    C("security_id", "string", key=True),
    C("name", "string"),
    C("gics_sector", "enum", enum=GICS_SECTORS),
    C("gics_sub_industry", "string"),
    C("cik", "string", nullable=True),               # SEC Central Index Key, from the same Wikipedia table
    C("in_universe", "bool", licence="F"),           # ranked by Yahoo market cap (§2.1)
    # No universe_rank: a Yahoo market-cap rank of ~500 firms is a per-row
    # Yahoo-derived number (milestone-1 review, claim 10). It stays in the
    # local cache/universe.parquet only; nothing downstream reads it.
    C("cboe_vx_index", "enum", nullable=True, enum=VX_INDICES),
), committed=True)

# --- data model §3.2 -----------------------------------------------------------
TICKER_ALIAS = Table("ticker_alias", (
    C("ticker", "string", key=True),
    C("valid_from", "date32", key=True),
    C("valid_to", "date32", nullable=True),
    C("security_id", "string"),
), committed=True)

# --- data model §3.3 -----------------------------------------------------------
SESSION = Table("session", (
    C("session_date", "date32", key=True),
    C("session_index", "int32"),
    C("is_half_day", "bool"),
    C("close_time_et", "string"),
    C("era", "enum", enum=ERAS),
), committed=True, unique=(("session_index",),))

# --- data model §3.4 -----------------------------------------------------------
MARKET_DAILY = Table("market_daily", (
    C("session_date", "date32", key=True),
    C("r_dtb3", "float64"),
    C("r_cont", "float64"),
    C("vix_close_cboe", "float64", nullable=True, licence="R"),
    C("ln_vix_cboe", "float64", nullable=True, licence="R"),
), committed=False)

# --- data model §3.7 -----------------------------------------------------------
EVENTS = Table("events", (
    C("event_id", "string", key=True),
    C("security_id", "string"),
    C("ticker_at_event", "string"),
    C("announce_date", "date32"),
    C("announce_date_used", "date32", licence="F"),  # the documents' date for date_corrected, else announce_date
    C("timing_raw", "enum", nullable=True, enum=TIMING),
    C("timing_used", "enum", nullable=True, licence="F", enum=TIMING),
    C("timing_status", "enum", licence="F", enum=TIMING_STATUS),
    C("timing_source", "enum", nullable=True, licence="F", enum=TIMING_SOURCE),
    C("gap_check_changed", "bool", licence="F"),
    C("edgar_accession", "string", nullable=True),
    C("edgar_accepted_utc", "string", nullable=True),
    C("day0_session", "date32", nullable=True, licence="F"),
    C("day_m1_session", "date32", nullable=True, licence="F"),
    C("fiscal_period_end", "date32", nullable=True),
    C("prev_event_id", "string", nullable=True),
    C("next_event_id", "string", nullable=True),
    C("gap_sessions_prev", "int16", nullable=True, licence="F"),
    C("orphan_nearby", "bool", licence="F"),
    C("season", "string", licence="F"),
    C("sample", "enum", licence="F", enum=SAMPLES),
    C("exclusion_reason", "string", nullable=True, licence="F"),
    C("calendar_commit", "string"),
), committed=True)

# --- data model §3.8 -----------------------------------------------------------
EPS = Table("eps", (
    C("security_id", "string", key=True),
    C("fiscal_period_end", "date32", key=True),
    C("event_id", "string", nullable=True),
    C("match_status", "enum", enum=MATCH_STATUS),
    C("lag_days", "int16", nullable=True),
    C("reported", "float64", nullable=True),
    C("estimate", "float64", nullable=True),
    C("surprise", "float64", nullable=True),
    C("consensus", "float64", nullable=True),
    C("consensus_high", "float64", nullable=True),
    C("consensus_low", "float64", nullable=True),
    C("consensus_count", "int16", nullable=True),
    C("consensus_date", "date32", nullable=True),
    C("surprise_disp", "float64", nullable=True),
), committed=True)

# --- data model §3.9 (local only) ----------------------------------------------
TIMING_CHECK = Table("timing_check", (
    C("event_id", "string", key=True),
    C("gap_bmo_yf", "float64", nullable=True, licence="R"),
    C("gap_amc_yf", "float64", nullable=True, licence="R"),
    C("gap_scale_yf", "float64", nullable=True, licence="R"),
    C("z_bmo_yf", "float64", nullable=True, licence="R"),
    C("z_amc_yf", "float64", nullable=True, licence="R"),
    C("z_max_outside_yf", "float64", nullable=True, licence="R"),
    C("rel_day_max_outside_yf", "int16", nullable=True, licence="R"),
    C("gap_verdict_yf", "enum", nullable=True, licence="R", enum=GAP_VERDICT),
    C("outside_flag_yf", "bool", nullable=True, licence="R"),
), committed=False)

# --- milestone 1: the first columns of iv_daily (data model §3.6), built early ---
SESSION_SNAPSHOT = Table("session_snapshot", (
    C("security_id", "string", key=True),
    C("session_date", "date32", key=True),
    C("snapshot_date", "date32", nullable=True),
    C("snapshot_status", "enum", enum=SNAPSHOT_STATUS),
), committed=True)

REGISTRY: dict[str, Table] = {t.name: t for t in (
    SECURITY, TICKER_ALIAS, SESSION, MARKET_DAILY, EVENTS, EPS, TIMING_CHECK, SESSION_SNAPSHOT,
)}


def has_restricted_suffix(name: str) -> bool:
    return name.endswith(RESTRICTED_SUFFIXES)
