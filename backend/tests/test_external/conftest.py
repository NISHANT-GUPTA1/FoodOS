"""Aeroplane mode, enforced.

The H34 rehearsal runs with the wifi off. These fixtures reproduce that at every
test run rather than once, on the night, in front of judges — every test in this
package executes with the network opt-in cleared AND with `urllib.request.urlopen`
replaced by something that fails the test if anything reaches it.

That second half is the one that matters. Clearing the flag proves the connectors
behave when told not to use the network; poisoning the socket proves they never
try, which is the claim the demo actually rests on.
"""

from __future__ import annotations

import urllib.request

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.delenv("FOODOS_ALLOW_NETWORK", raising=False)

    def _forbidden(*args, **kwargs):
        raise AssertionError(
            "a connector opened a socket during a test — the offline demo is broken"
        )

    monkeypatch.setattr(urllib.request, "urlopen", _forbidden)
    yield
