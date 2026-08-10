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

import math
from dataclasses import dataclass
from enum import StrEnum

# Universal gas constant, J/(mol.K).
R_GAS = 8.314462618

CELSIUS_TO_KELVIN = 273.15


class MechSusceptibility(StrEnum):
    """How readily a commodity bruises, splits or crushes under handling.

    Introduced because its absence was a real defect, not for completeness.
    The mechanical channel used to be commodity-blind — `PACK_INSULT`,
    `HARVEST_DAMAGE` and the vibration constants applied identically to a
    potato and a spinach leaf — so farm-side loss came out near 8.2% for every
    crop regardless of its biophysics, against a published spread of 5.1% to
    11.6%. Swapping only the thermal constants therefore could not reproduce
    another commodity's farm loss, and the held-out check in `calibrate` failed
    worse than predicting a constant.

    Three levels rather than a per-commodity float, deliberately. A float fitted
    per commodity would need that commodity's own loss target, which is exactly
    what a held-out prediction does not have. A level read from the literature
    is a *measured* property, so a new crop can be predicted rather than fitted.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


#: Multiplier on accumulated mechanical damage. Tomato is MEDIUM and sits at
#: 1.0, so the existing tomato calibration is the reference point and does not
#: move when this is introduced.
MECH_FACTOR: dict[MechSusceptibility, float] = {
    MechSusceptibility.LOW: 0.55,
    MechSusceptibility.MEDIUM: 1.00,
    MechSusceptibility.HIGH: 1.70,
}


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

    # --- MEASURED: mechanical susceptibility --------------------------------
    #: Fraction of life lost per unit of accumulated mechanical damage. Bruised
    #: and punctured fruit respire faster and admit pathogens, so damage does
    #: not just destroy fruit directly — it shortens what survives.
    damage_life_penalty: float

    #: Whether this crop suffers membrane chilling injury at all. Potato does
    #: not above its freezing point, and Indian seed stores run it at 2-4 C on
    #: purpose — so a chilling penalty would be actively wrong there.
    chilling_sensitive: bool = True

    # --- Quality scoring -----------------------------------------------------
    #: Spoilage fraction at which the batch stops meeting fresh-retail standards.
    #: Used as Q_crit for the RUL calculation.
    critical_spoilage_fraction: float = 0.10

    # --- MEASURED: handling and cosmetic rejection ---------------------------
    mech_susceptibility: MechSusceptibility = MechSusceptibility.MEDIUM

    #: Share of the lot rejected at farm-gate sorting on **appearance alone** —
    #: misshapen, undersized, blemished but entirely edible. Published
    #: separately by NABCONS, and the third channel the model was missing.
    #:
    #: This is not senescence and no Arrhenius model can produce it: a perfectly
    #: fresh, perfectly cold guava is still rejected for being lopsided. It is
    #: also the single largest farm-side line for fruit. Leaving it inside the
    #: calibration target forced the thermal and mechanical channels to absorb
    #: it, which is what broke prediction on every commodity except the one that
    #: had been fitted.
    #:
    #: MEASURED, never fitted — it comes straight off the survey.
    cosmetic_gradeout_pct: float = 0.0

    def kelvin_ref(self) -> float:
        return self.ref_temp_c + CELSIUS_TO_KELVIN

    @property
    def mech_factor(self) -> float:
        return MECH_FACTOR[MechSusceptibility(self.mech_susceptibility)]

    @property
    def chilling_penalty_per_deg(self) -> float:
        """Penalty putting the rate minimum exactly on the chilling threshold.

        **Derived, not chosen.** Setting d(rate)/dT = 0 at T = T_c for
        `rate(T) = A(T) + p*(T_c - T)` gives

            p = A(T_c) * (Ea/R) / T_c^2

        which is the smallest penalty that makes the declared threshold the
        actual optimum.

        This replaces a hand-set constant that was wrong. Tomato shipped 0.020
        where the derivation requires 0.0485, so the model's rate minimum sat at
        **3.6 C** while the field next to it declared 12.5 C — meaning the engine
        would have recommended storing tomatoes at 4 C, the precise error the
        chilling term exists to prevent. Deriving it means the two can never
        drift apart again, and removes a free parameter rather than adding one.

        Applied to chilling-insensitive crops too, where the threshold is the
        **freezing point** rather than a chilling one. The mechanism differs —
        ice crystals rupturing cells rather than membrane dysfunction — but the
        modelling consequence is identical: below that line the commodity
        deteriorates faster, and without the term the optimiser walks straight
        past it. Gating this on `chilling_sensitive` put potato's optimum at
        -3 C, which would have frozen the crop to recover a few hours of life.
        """
        tc_kelvin = self.chilling_threshold_c + CELSIUS_TO_KELVIN
        at_threshold = math.exp(
            (self.ea_j_per_mol / R_GAS) * (1.0 / self.kelvin_ref() - 1.0 / tc_kelvin)
        )
        return at_threshold * (self.ea_j_per_mol / R_GAS) / (tc_kelvin * tc_kelvin)


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
    chilling_sensitive=True,
    damage_life_penalty=1.30,
    critical_spoilage_fraction=0.10,
    mech_susceptibility=MechSusceptibility.MEDIUM,
    cosmetic_gradeout_pct=3.10,
)

#: Soft, thin-skinned, and the highest farm-side loss in the NABCONS table —
#: most of which is cosmetic rejection rather than decay.
GUAVA = Commodity(
    key="guava",
    name="Guava",
    botanical_name="Psidium guajava",
    ea_j_per_mol=65_000.0,
    ref_temp_c=20.0,
    ref_life_days=6.0,
    life_spread_sigma=0.45,
    chilling_threshold_c=8.0,
    chilling_sensitive=True,
    damage_life_penalty=1.55,
    critical_spoilage_fraction=0.10,
    mech_susceptibility=MechSusceptibility.HIGH,
    cosmetic_gradeout_pct=4.59,
)

#: The opposite corner: firm, long-lived, and — contrary to the engine's
#: original assumption — **not** chilling sensitive. Potato suffers no membrane
#: injury above its -0.8 C freezing point, and Indian table and seed stores run
#: it at 2-4 C deliberately. Applying a chilling penalty here would have made
#: the model condemn standard commercial practice.
POTATO = Commodity(
    key="potato",
    name="Potato",
    botanical_name="Solanum tuberosum",
    ea_j_per_mol=51_200.0,
    ref_temp_c=20.0,
    ref_life_days=60.0,
    life_spread_sigma=0.35,
    chilling_threshold_c=-0.8,
    chilling_sensitive=False,
    damage_life_penalty=0.90,
    critical_spoilage_fraction=0.10,
    mech_susceptibility=MechSusceptibility.LOW,
    cosmetic_gradeout_pct=1.60,
)

NABCONS_TOMATO = NabconsBaseline(
    commodity_key="tomato",
    farm_operations_pct=8.37,
    market_level_pct=3.25,
)
NABCONS_GUAVA = NabconsBaseline(
    commodity_key="guava", farm_operations_pct=11.59, market_level_pct=3.46
)
NABCONS_POTATO = NabconsBaseline(
    commodity_key="potato", farm_operations_pct=5.10, market_level_pct=0.86
)

#: Three crops, chosen for spread rather than count: a soft fruit with the
#: highest published farm loss, a firm tuber with the lowest, and tomato in the
#: middle. Every one has a *published* cosmetic grade-out figure, which is what
#: makes held-out prediction testable at all — see `calibrate.holdout_report()`.
#:
#: Extending this is now a data change rather than a code change. It is
#: deliberately not done in bulk: a wide table of unverified constants would
#: read as coverage while quietly making the engine wrong on every row, which
#: is precisely the failure the held-out check exists to expose.
COMMODITIES: dict[str, Commodity] = {c.key: c for c in (TOMATO, GUAVA, POTATO)}
NABCONS: dict[str, NabconsBaseline] = {
    b.commodity_key: b for b in (NABCONS_TOMATO, NABCONS_GUAVA, NABCONS_POTATO)
}


def get(key: str) -> Commodity:
    try:
        return COMMODITIES[key]
    except KeyError:
        raise KeyError(
            f"unknown commodity {key!r}; MVP ships {sorted(COMMODITIES)}"
        ) from None
