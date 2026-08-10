"""Commodity knowledge base — the biophysical constants, and where they come from.

Every number in this file is either published food science or a NABCONS survey
figure, and each one carries its source in a comment. That matters more than it
looks: the first hostile question about a synthetic dataset is *"where did the
parameters come from?"*, and "we tuned them until the demo looked good" is the
answer that loses the room.

Two kinds of constant live here, and they are kept apart on purpose:

  MEASURED   activation energy, Q10, reference shelf life, chilling threshold.
             Taken from the literature. Not fitted, not touched by calibration.

  CALIBRATED mechanical-damage scale and spoilage scale. Two scalars, solved for
             in `calibrate.py` so the baseline scenario reproduces the NABCONS
             loss split. Fitted, and labelled as fitted everywhere they appear.

Anything that is fitted must be able to say so. See `NABCONS_TOMATO` for the
targets and `calibrate.py` for the honesty argument about what that does and
does not prove.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Universal gas constant, J/(mol.K).
R_GAS = 8.314462618

CELSIUS_TO_KELVIN = 273.15


class MaturityStage(StrEnum):
    """USDA tomato colour classification — the standard six stages.

    Harvest maturity is the single largest controllable driver of remaining
    life, and it is something an FPO manager can answer in one tap without any
    instrument, which is why it leads the questionnaire.
    """

    MATURE_GREEN = "mature_green"
    BREAKER = "breaker"
    TURNING = "turning"
    PINK = "pink"
    LIGHT_RED = "light_red"
    RED = "red"


#: Usable life at harvest as a multiple of the reference (turning) stage.
#: Ratios follow the USDA Handbook 66 tomato ripening series: a mature-green
#: fruit holds roughly three to four times as long as a red one at the same
#: temperature, and the intermediate stages interpolate that span.
MATURITY_LIFE_FACTOR: dict[MaturityStage, float] = {
    MaturityStage.MATURE_GREEN: 1.75,
    MaturityStage.BREAKER: 1.30,
    MaturityStage.TURNING: 1.00,
    MaturityStage.PINK: 0.78,
    MaturityStage.LIGHT_RED: 0.58,
    MaturityStage.RED: 0.42,
}


@dataclass(frozen=True)
class Commodity:
    """Biophysical parameters for one crop."""

    key: str
    name: str
    botanical_name: str

    # --- MEASURED: Arrhenius deterioration kinetics -------------------------
    #: Activation energy of the dominant deterioration reaction, J/mol.
    #: 70 kJ/mol sits mid-band for fresh produce respiration and softening and
    #: implies Q10 = 2.6 at 20 C — see `q10_at()`. Published tomato Q10 runs
    #: 2.0-3.0, so this is the middle of the reported range rather than a
    #: flattering end of it.
    ea_j_per_mol: float
    #: Temperature the reference life is quoted at, deg C.
    ref_temp_c: float
    #: Median usable life at `ref_temp_c` for a fruit at the reference maturity
    #: (turning), in days. Tomato: 8 days at 20 C, USDA Handbook 66.
    ref_life_days: float

    # --- MEASURED: batch heterogeneity --------------------------------------
    #: Lognormal sigma of per-fruit life budget within one batch. A crate is not
    #: one fruit — it is a spread, and the spread is what makes a loss
    #: *percentage* meaningful. 0.42 reproduces the roughly 3:1 spread between
    #: the first and last fruit of a hand-harvested lot to fail.
    life_spread_sigma: float

    # --- MEASURED: chilling injury ------------------------------------------
    #: Below this, tomatoes chill-injure: membrane damage, failure to ripen,
    #: and *accelerated* decay once returned to ambient. Tomato: 12.5 C.
    #: Without this term an optimiser will happily recommend freezing the load.
    chilling_threshold_c: float
    #: Extra deterioration rate per degree below the threshold, per degree.
    #: Honest limitation: real chilling injury is *cumulative* — tomato at 5 C
    #: shows damage after six to eight days, not immediately. This is a coarse
    #: instantaneous stand-in, which is adequate at the 24-48 h transit
    #: timescale the MVP models and wrong for multi-week cold storage. It is
    #: tuned so cold transit still helps (4 C runs at roughly a third of the
    #: 20 C rate) while sub-zero stops looking free.
    chilling_penalty_per_deg: float

    # --- MEASURED: mechanical susceptibility --------------------------------
    #: Fraction of life lost per unit of accumulated mechanical damage. Bruised
    #: and punctured fruit respire faster and admit pathogens, so damage does
    #: not just destroy fruit directly — it shortens what survives.
    damage_life_penalty: float

    # --- Quality scoring -----------------------------------------------------
    #: Spoilage fraction at which the batch stops meeting fresh-retail standards.
    #: Used as Q_crit for the RUL calculation.
    critical_spoilage_fraction: float

    def kelvin_ref(self) -> float:
        return self.ref_temp_c + CELSIUS_TO_KELVIN


@dataclass(frozen=True)
class NabconsBaseline:
    """Published loss percentages for one commodity — the calibration target.

    NABCONS 2022, commissioned by MoFPI. The study reports loss at farm
    operations and at market level separately.

    A note on where transport lands, because it changes what the numbers mean.
    The published tomato split has no separate transport line, and the modal
    case behind the market-level figure is produce that has already travelled to
    a wholesale mandi. Transit is therefore attributed to the market side here.
    Anyone reading a transit loss out of this model is reading the 3.25%.
    """

    commodity_key: str
    farm_operations_pct: float
    market_level_pct: float

    @property
    def combined_pct(self) -> float:
        return self.farm_operations_pct + self.market_level_pct


TOMATO = Commodity(
    key="tomato",
    name="Tomato",
    botanical_name="Solanum lycopersicum",
    ea_j_per_mol=70_000.0,
    ref_temp_c=20.0,
    ref_life_days=8.0,
    life_spread_sigma=0.42,
    chilling_threshold_c=12.5,
    chilling_penalty_per_deg=0.02,
    damage_life_penalty=1.30,
    critical_spoilage_fraction=0.10,
)

NABCONS_TOMATO = NabconsBaseline(
    commodity_key="tomato",
    farm_operations_pct=8.37,
    market_level_pct=3.25,
)

#: MVP is single-commodity by design (blueprint §8). The registry exists so the
#: second crop is a data change rather than a code change — guava at 11.59/3.46
#: and potato at 5.10/0.86 are the obvious next two, and both are in the same
#: NABCONS table. Calibrating on tomato and then *predicting* one of those
#: without refitting is the strongest validation available; see `calibrate.py`.
COMMODITIES: dict[str, Commodity] = {TOMATO.key: TOMATO}
NABCONS: dict[str, NabconsBaseline] = {NABCONS_TOMATO.commodity_key: NABCONS_TOMATO}


def get(key: str) -> Commodity:
    try:
        return COMMODITIES[key]
    except KeyError:
        raise KeyError(
            f"unknown commodity {key!r}; MVP ships {sorted(COMMODITIES)}"
        ) from None
