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
# CLASS R IN A COMMITTED TABLE (owner decision, 2026-10-29)
#   The owner allowed real Yahoo, Cboe and FRED values in the committed tables
#   the app or the docs need. A table names such columns in keep_restricted;
#   store.write_derived keeps exactly those and still drops every other class-R
#   column. Milestone 2 keeps one: timing_check.gap_verdict_yf, for the sample
#   funnel's share of gap contradictions by move tercile.
#
# THE RULE THE TESTS ENFORCE
#   Over value columns (keys excluded), a column is class R exactly when its
#   name ends in _yf or _cboe. A forgotten suffix and a stray suffix both fail.
#
# MILESTONE 3
#   event_window_obs, event_measures and results. The market-adjusted
#   per-row values (e_abn_cboe, aliv_cboe, the *_cboe measures, s_abn_cboe and
#   beta_vix_cboe) are class R and stay local: no view needs them per row
#   (owner preference of 2026-10-29: VIX-derived per-row values stay local
#   unless the app needs them). Their aggregates in `results` are class S and
#   committed (data model §2.1). A table may carry an `invariant`: a function
#   of the whole DataFrame that returns the rules it breaks; store.validate
#   runs it on every write and read (results: invariants.results_reference).
# =============================================================================

from dataclasses import dataclass, field
from typing import Callable

from earnings_vol.invariants import results_reference

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
# Milestone 2 (data model §3.5, §3.6): the values measures/chain.py and
# measures/termstructure.py may write.
ATM_METHODS = ("bracket_linear", "quadratic", "none")
CHAIN_STATUS = ("ok", "no_atm", "no_forward", "stale")
CM30_METHODS = ("interp_clean", "interp_spanning", "extrap_clean", "extrap_spanning", "two_component",
                "flat_sigma", "none")
IMPLIED_MOVE_STATUS = ("ok", "nonpositive_event_variance", "not_identified")
# Milestone 3 (data model §3.10, §3.11, §3.13).
BASELINE_EXCLUDED = ("other_event_zone", "orphan_zone", "not_observed", "null_iv", "outside")
VIX_REGIME = ("low", "mid", "high")
RESULT_FAMILY = ("event_test", "regression", "validation", "descriptive")
HYPOTHESES = ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
ROLES = ("primary", "robustness", "exploratory")
ESTIMANDS = ("equal_weighted", "precision_weighted")
RESULT_SAMPLES = ("daily", "mixed", "coarse", "cboe5")
ADJUSTMENTS = ("market", "mean")


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
    keep_restricted: tuple[str, ...] = ()  # class-R columns the committed copy keeps (see the header)
    invariant: Callable | None = None      # f(df) -> [broken rule, ...], run by store.validate

    def __post_init__(self):
        bad = [n for n in self.keep_restricted if n not in self.names or self.column(n).licence != "R"]
        if bad:
            raise ValueError(f"{self.name}: keep_restricted names {bad}, which are not class-R columns")
        if self.keep_restricted and not self.committed:
            raise ValueError(f"{self.name}: keep_restricted needs a committed table")

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
        """Names of the class-R columns: they leave this machine only if named in keep_restricted."""
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
), committed=True, keep_restricted=("gap_verdict_yf",))   # milestone 2: the verdict only (owner, 2026-10-29)

# --- milestone 1: the first columns of iv_daily (data model §3.6), built early ---
SESSION_SNAPSHOT = Table("session_snapshot", (
    C("security_id", "string", key=True),
    C("session_date", "date32", key=True),
    C("snapshot_date", "date32", nullable=True),
    C("snapshot_status", "enum", enum=SNAPSHOT_STATUS),
), committed=True)

# --- milestone 2: data model §3.5, the atom (local only) ------------------------
# A column that depends on day 0 (through the next event or the clean/spanning
# split) is class F, like events.day0_session: it is committable exactly when
# the timing label is (data model §2.1).
CHAIN_EXPIRY = Table("chain_expiry", (
    C("security_id", "string", key=True),
    C("session_date", "date32", key=True),
    C("expiration", "date32", key=True),
    C("snapshot_date", "date32"),
    C("tau_sessions", "int16"),
    C("tau_cal_days", "int16"),
    C("df", "float64"),                                # from FRED DTB3: local only
    C("forward", "float64", nullable=True),            # null iff status no_forward or stale
    C("forward_n_strikes", "int16"),
    C("forward_dispersion", "float64", nullable=True),
    C("n_strikes_valid", "int16"),
    C("strike_lo", "float64", nullable=True),
    C("strike_hi", "float64", nullable=True),
    C("k_lo", "float64", nullable=True),
    C("k_hi", "float64", nullable=True),
    C("rel_spread_lo", "float64", nullable=True),
    C("rel_spread_hi", "float64", nullable=True),
    C("w_atm", "float64", nullable=True),              # null unless status ok
    C("iv_atm", "float64", nullable=True),
    C("atm_method", "enum", enum=ATM_METHODS),
    C("vendor_iv_atm", "float64", nullable=True),
    C("straddle_atm", "float64", nullable=True),
    C("iv_straddle", "float64", nullable=True),
    C("next_event_id", "string", nullable=True, licence="F"),
    C("spans_next_event", "bool", nullable=True, licence="F"),
    C("status", "enum", enum=CHAIN_STATUS),
    C("flags", "string"),
), committed=False)

# --- milestone 2: data model §3.6 ------------------------------------------------
IV_DAILY = Table("iv_daily", (
    C("security_id", "string", key=True),
    C("session_date", "date32", key=True),
    C("snapshot_date", "date32", nullable=True),
    C("snapshot_status", "enum", enum=SNAPSHOT_STATUS),
    C("next_event_id", "string", nullable=True, licence="F"),
    C("sessions_to_next_event", "int16", nullable=True, licence="F"),
    C("prev_event_id", "string", nullable=True, licence="F"),
    C("sessions_since_prev_event", "int16", nullable=True, licence="F"),
    C("front_expiry", "date32", nullable=True),
    C("front_tau", "int16", nullable=True),
    C("front_atm_iv", "float64", nullable=True),
    C("cm30_iv", "float64", nullable=True, licence="F"),
    C("cm30_method", "enum", licence="F", enum=CM30_METHODS),
    C("cm30_exp_lo", "date32", nullable=True, licence="F"),
    C("cm30_exp_hi", "date32", nullable=True, licence="F"),
    C("cm30_blind_iv", "float64", nullable=True),
    C("sigma_d_iv", "float64", nullable=True, licence="F"),
    C("event_var", "float64", nullable=True, licence="F"),
    C("ev_exp1", "date32", nullable=True, licence="F"),
    C("ev_exp2", "date32", nullable=True, licence="F"),
    C("ev_tau1", "int16", nullable=True, licence="F"),
    C("ev_tau2", "int16", nullable=True, licence="F"),
    C("ev_w1", "float64", nullable=True, licence="F"),
    C("ev_w2", "float64", nullable=True, licence="F"),
    C("implied_move", "float64", nullable=True, licence="F"),
    C("implied_abs_move", "float64", nullable=True, licence="F"),
    C("implied_abs_move_total", "float64", nullable=True, licence="F"),
    C("implied_move_status", "enum", licence="F", enum=IMPLIED_MOVE_STATUS),
    C("ts_slope", "float64", nullable=True),
    C("forward_front", "float64", nullable=True),      # display only (data model §3.6)
    C("vendor_iv_current", "float64", nullable=True),
    C("flags", "string", licence="F"),
), committed=True)

# --- milestone 2: the IV columns of event_measures (data model §3.11a) -----------
EVENT_IV = Table("event_iv", (
    C("event_id", "string", key=True),
    C("pre_session", "date32", nullable=True, licence="F"),
    C("post_session", "date32", nullable=True, licence="F"),
    C("crush_span_sessions", "int16", nullable=True, licence="F"),
    C("evar_m1", "float64", nullable=True, licence="F"),
    C("evar_m2", "float64", nullable=True, licence="F"),
    C("implied_move_m1", "float64", nullable=True, licence="F"),
    C("implied_abs_move_total_m1", "float64", nullable=True, licence="F"),
    C("implied_move_status", "enum", nullable=True, licence="F", enum=IMPLIED_MOVE_STATUS),
    C("sigma_d_m1", "float64", nullable=True, licence="F"),
    C("cm30_m1", "float64", nullable=True, licence="F"),
    C("cm30_0", "float64", nullable=True, licence="F"),
    C("ts_slope_m1", "float64", nullable=True, licence="F"),
    C("crush_mean_adj", "float64", nullable=True, licence="F"),
    C("dsigma_d_mean_adj", "float64", nullable=True, licence="F"),
    C("front_fixed_expiry", "date32", nullable=True, licence="F"),
    C("front_fixed_iv_m1", "float64", nullable=True, licence="F"),
    C("front_fixed_iv_0", "float64", nullable=True, licence="F"),
    C("front_fixed_interpolated", "bool", licence="F"),
    C("crush_front_fixed", "float64", nullable=True, licence="F"),
    C("realized_ret_0", "float64", nullable=True, licence="F"),
    C("abs_ret_over_implied", "float64", nullable=True, licence="F"),
    C("abs_move_cand_max", "float64", nullable=True),   # label-free: class U (data model §3.11)
    C("flags", "string", licence="F"),
), committed=True)

# --- milestone 3: data model §3.10 ---------------------------------------------
# Every column depends on day 0, so the value columns are class F like
# iv_daily's; the market-adjusted ones are class R (local only).
EVENT_WINDOW_OBS = Table("event_window_obs", (
    C("event_id", "string", key=True),
    C("rel_day", "int16", key=True),
    C("session_date", "date32", licence="F"),
    C("observed", "bool", licence="F"),
    C("in_window", "bool"),
    C("in_baseline", "bool", licence="F"),
    C("baseline_excluded_reason", "enum", nullable=True, licence="F", enum=BASELINE_EXCLUDED),
    C("cm30_iv", "float64", nullable=True, licence="F"),
    C("ln_cm30", "float64", nullable=True, licence="F"),
    C("d_ln_cm30", "float64", nullable=True, licence="F"),
    C("e_abn_cboe", "float64", nullable=True, licence="R"),
    C("aliv_cboe", "float64", nullable=True, licence="R"),
    C("aliv_mean_adj", "float64", nullable=True, licence="F"),
    C("aiv_level", "float64", nullable=True, licence="F"),
    C("front_fixed_iv", "float64", nullable=True, licence="F"),
    C("front_fixed_interpolated", "bool", licence="F"),
    C("sigma_d_iv", "float64", nullable=True, licence="F"),
    C("event_var", "float64", nullable=True, licence="F"),
    C("ln_vx_cboe", "float64", nullable=True, licence="R"),
    C("e_abn_vx_cboe", "float64", nullable=True, licence="R"),
), committed=True)

# --- milestone 3: data model §3.11 ---------------------------------------------
EVENT_MEASURES = Table("event_measures", (
    C("event_id", "string", key=True),
    C("eligible_crush", "bool", licence="F"),
    C("eligible_runup", "bool", licence="F"),
    C("eligible_persist_10", "bool", licence="F"),
    C("ineligible_reason", "string", licence="F"),
    C("baseline_n", "int16", licence="F"),
    C("baseline_n_changes", "int16", licence="F"),
    C("baseline_mean_ln_iv", "float64", nullable=True, licence="F"),
    C("baseline_mean_iv", "float64", nullable=True, licence="F"),
    C("beta_vix_cboe", "float64", nullable=True, licence="R"),
    C("beta_n", "int32", licence="F"),
    C("s_abn_cboe", "float64", nullable=True, licence="R"),
    C("runup_cboe", "float64", nullable=True, licence="R"),
    C("crush_cboe", "float64", nullable=True, licence="R"),
    C("persist_1_cboe", "float64", nullable=True, licence="R"),
    C("persist_5_cboe", "float64", nullable=True, licence="R"),
    C("persist_10_cboe", "float64", nullable=True, licence="R"),
    C("dsigma_d_cboe", "float64", nullable=True, licence="R"),
    C("crush_mean_adj", "float64", nullable=True, licence="F"),
    C("dsigma_d_mean_adj", "float64", nullable=True, licence="F"),
    C("crush_two_session_cboe", "float64", nullable=True, licence="R"),
    C("crush_two_session_mean_adj", "float64", nullable=True, licence="F"),
    C("crush_front_fixed", "float64", nullable=True, licence="F"),
    C("crush_span_sessions", "int16", nullable=True, licence="F"),
    C("sa_crush_cboe", "float64", nullable=True, licence="R"),
    C("sa_runup_cboe", "float64", nullable=True, licence="R"),
    C("sa_persist_1_cboe", "float64", nullable=True, licence="R"),
    C("sa_persist_5_cboe", "float64", nullable=True, licence="R"),
    C("sa_persist_10_cboe", "float64", nullable=True, licence="R"),
    C("sa_dsigma_d_cboe", "float64", nullable=True, licence="R"),
    C("evar_m1", "float64", nullable=True, licence="F"),
    C("evar_m2", "float64", nullable=True, licence="F"),
    C("implied_move_m1", "float64", nullable=True, licence="F"),
    C("implied_abs_move_total_m1", "float64", nullable=True, licence="F"),
    C("implied_move_status", "enum", nullable=True, licence="F", enum=IMPLIED_MOVE_STATUS),
    C("sigma_d_m1", "float64", nullable=True, licence="F"),
    C("cm30_m1", "float64", nullable=True, licence="F"),
    C("ts_slope_m1", "float64", nullable=True, licence="F"),
    C("price_ref", "float64", nullable=True, licence="F"),
    C("surprise_scaled", "float64", nullable=True, licence="F"),
    C("abs_surprise_scaled_w", "float64", nullable=True, licence="F"),
    C("sue_hist", "float64", nullable=True, licence="F"),
    C("sue_hist_n", "int16", nullable=True, licence="F"),
    C("realized_ret_0", "float64", nullable=True, licence="F"),
    C("abs_move_cand_max", "float64", nullable=True),
    C("realized_ret_0_yf", "float64", nullable=True, licence="R"),
    C("abs_ret_over_implied", "float64", nullable=True, licence="F"),
    C("vix_regime", "enum", nullable=True, licence="F", enum=VIX_REGIME),
    C("ln_mcap_yf", "float64", nullable=True, licence="R"),
), committed=True)

# --- milestone 3: data model §3.13 ---------------------------------------------
# The numbers of a market-adjusted row are statistics over VIX-derived values:
# class S (committed; data model §2.1, owner decision of 2026-10-29).
RESULTS = Table("results", (
    C("result_id", "string", key=True),
    C("family", "enum", enum=RESULT_FAMILY),
    C("hypothesis", "enum", nullable=True, enum=HYPOTHESES),
    C("role", "enum", enum=ROLES),
    C("measure", "string"),
    C("statistic", "string"),
    C("estimand", "enum", nullable=True, enum=ESTIMANDS),
    C("rel_day", "int16", nullable=True),
    C("sample", "enum", enum=RESULT_SAMPLES),
    C("subgroup_key", "string"),
    C("subgroup_value", "string"),
    C("adjustment", "enum", enum=ADJUSTMENTS),
    C("model_id", "string", nullable=True),
    C("term", "string", nullable=True),
    C("n", "int32"),
    C("n_clusters", "int32", nullable=True),
    C("n_clusters_firm", "int32", nullable=True),
    C("df", "float64", nullable=True),
    C("df_num", "float64", nullable=True),
    C("estimate", "float64", nullable=True, licence="S"),
    C("se", "float64", nullable=True, licence="S"),
    C("stat", "float64", nullable=True, licence="S"),
    C("p_value", "float64", nullable=True, licence="S"),
    C("ci_lo", "float64", nullable=True, licence="S"),
    C("ci_hi", "float64", nullable=True, licence="S"),
    C("p_holm", "float64", nullable=True, licence="S"),
    C("q_bh", "float64", nullable=True, licence="S"),
    C("rbar", "float64", nullable=True, licence="S"),
    C("params_hash", "string"),
    C("code_commit", "string"),
), committed=True, invariant=results_reference)

REGISTRY: dict[str, Table] = {t.name: t for t in (
    SECURITY, TICKER_ALIAS, SESSION, MARKET_DAILY, EVENTS, EPS, TIMING_CHECK, SESSION_SNAPSHOT,
    CHAIN_EXPIRY, IV_DAILY, EVENT_IV, EVENT_WINDOW_OBS, EVENT_MEASURES, RESULTS,
)}


def has_restricted_suffix(name: str) -> bool:
    return name.endswith(RESTRICTED_SUFFIXES)
