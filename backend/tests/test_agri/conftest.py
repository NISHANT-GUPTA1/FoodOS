"""Controlled scenarios — one variable moves, everything else is pinned.

The point of this file is `make_controlled`. Almost every claim worth testing in
the simulator is a *ceteris paribus* claim — shade beats sun, crates beat sacks,
reefers beat open decks — and none of them can be checked against a random
sample, because the sampler varies twelve things at once and any one of them can
swamp the effect being measured.

So: build a batch where every field is identical across rows, then move exactly
one. The difference that comes out was caused by the thing that moved.
"""

from __future__ import annotations

import numpy as np
import pytest

from foodos.agri.commodity import TOMATO
from foodos.agri.scenario import (
    FieldHolding,
    HarvestMethod,
    HarvestWindow,
    Packaging,
    ScenarioBatch,
    TransportMode,
)

#: Deliberately unremarkable: a mid-season Karnataka shipment, handled the way
#: most of them are. Effects measured against it are effects on a normal load,
#: not on a contrived worst case.
DEFAULTS = dict(
    quantity_kg=10_000.0,
    harvest_method=HarvestMethod.MANUAL,
    harvest_window=HarvestWindow.MORNING,
    field_holding=FieldHolding.SHADE,
    field_hours=4.0,
    packaging=Packaging.GUNNY_BAG,
    transport_mode=TransportMode.OPEN_TRUCK,
    transit_hours=10.0,
    mandi_holding_hours=6.0,
    maturity_factor=1.0,
    visual_damage_fraction=0.03,
    ambient_mean_c=28.0,
    diurnal_amplitude_c=9.0,
    road_roughness=1.4,
)

_STRING_FIELDS = {
    "harvest_method",
    "harvest_window",
    "field_holding",
    "packaging",
    "transport_mode",
}


def make_controlled(n: int = 1, **overrides) -> ScenarioBatch:
    """A batch of `n` identical shipments, with `overrides` applied.

    An override may be a scalar (broadcast to every row) or a sequence of length
    `n` (the variable being swept).
    """
    values = {**DEFAULTS, **overrides}
    columns = {}
    for name, value in values.items():
        is_string = name in _STRING_FIELDS
        scalar = np.isscalar(value) or isinstance(value, str)
        if scalar:
            columns[name] = (
                np.array([str(value)] * n) if is_string else np.full(n, float(value))
            )
        else:
            columns[name] = (
                np.array([str(v) for v in value])
                if is_string
                else np.asarray(value, dtype=float)
            )

    return ScenarioBatch(n=n, commodity=TOMATO, meta={"sampler": "controlled"}, **columns)


@pytest.fixture
def controlled():
    return make_controlled
