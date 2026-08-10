"""The QR encoder.

Written rather than installed, so it is tested rather than trusted. The three
layers are checked independently — the field arithmetic, the format header, and
the finished symbol — plus a round trip, which is the only check that proves a
scanner would actually read it.
"""

from __future__ import annotations

import random

import pytest

from foodos import qr

#: Total codewords per version, ISO/IEC 18004 table 1. The version table in the
#: encoder must agree with this or the symbol is malformed in a way that no
#: unit test of the parts would catch.
TOTAL_CODEWORDS = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172}

#: Published format strings for level M, masks 0-7.
FORMAT_M = {
    0: 0x5412, 1: 0x5125, 2: 0x5E7C, 3: 0x5B4B,
    4: 0x45F9, 5: 0x40CE, 6: 0x4F97, 7: 0x4AA0,
}


# ---------------------------------------------------------------- tables


def test_version_tables_account_for_every_codeword():
    for version in qr._VERSIONS:
        blocks = sum(count for count, _ in version.groups)
        total = version.data_codewords + blocks * version.ec_per_block
        assert total == TOTAL_CODEWORDS[version.number], version.number


def test_symbol_size_follows_the_version():
    for version in qr._VERSIONS:
        assert version.size == version.number * 4 + 17


# ---------------------------------------------------------------- GF(256)


def test_log_and_exp_are_inverses():
    for x in range(1, 256):
        assert qr._EXP[qr._LOG[x]] == x


def test_multiplication_is_commutative_and_has_an_identity():
    for _ in range(200):
        a, b = random.randrange(256), random.randrange(256)
        assert qr._mul(a, b) == qr._mul(b, a)
        assert qr._mul(a, 1) == a
        assert qr._mul(a, 0) == 0


def test_reed_solomon_matches_the_specs_worked_example():
    """ISO/IEC 18004 annex I: "01234567" as a version 1-M symbol."""
    message = [0x10, 0x20, 0x0C, 0x56, 0x61, 0x80] + [0xEC, 0x11] * 5
    assert qr.reed_solomon(message, 10) == [
        165, 36, 212, 193, 237, 54, 199, 135, 44, 85
    ]


def test_message_plus_check_is_divisible_by_the_generator():
    """The defining property of a Reed-Solomon codeword."""
    random.seed(20260810)
    for _ in range(40):
        n = random.randint(1, 60)
        ec = random.choice([7, 10, 15, 16, 18, 20, 24, 26])
        message = [random.randrange(256) for _ in range(n)]
        remainder = list(message) + qr.reed_solomon(message, ec)
        gen = qr._generator_poly(ec)
        for i in range(len(message)):
            coef = remainder[i]
            if coef:
                for j, g in enumerate(gen):
                    remainder[i + j] ^= qr._mul(g, coef)
        assert all(x == 0 for x in remainder)


# ---------------------------------------------------------------- format


def test_format_information_matches_the_published_table():
    for mask, expected in FORMAT_M.items():
        assert qr._format_bits(mask) == expected, mask


# ---------------------------------------------------------------- symbol


def _decode(modules: list[list[int]]) -> str:
    """Read a symbol back. Deliberately independent of the encoder's own
    placement pass, except for the reservation map and the mask rules."""
    size = len(modules)
    version = next(v for v in qr._VERSIONS if v.size == size)

    fmt = 0
    for i in range(6):
        fmt |= modules[8][i] << i
    fmt |= modules[8][7] << 6
    fmt |= modules[8][8] << 7
    fmt |= modules[7][8] << 8
    for i in range(9, 15):
        fmt |= modules[14 - i][8] << i
    fmt ^= qr._FORMAT_MASK
    assert fmt >> 13 == qr._EC_LEVEL_BITS
    mask = (fmt >> 10) & 0b111

    base = qr._Matrix(size)
    qr._place_function_patterns(base, version)
    rule = qr._MASKS[mask]

    bits: list[int] = []
    upward, col = True, size - 1
    while col > 0:
        if col == 6:
            col -= 1
        for row in (range(size - 1, -1, -1) if upward else range(size)):
            for c in (col, col - 1):
                if base.reserved[row][c]:
                    continue
                value = modules[row][c]
                if rule(row, c):
                    value ^= 1
                bits.append(value)
        upward = not upward
        col -= 2

    codes = [
        int("".join(map(str, bits[i : i + 8])), 2)
        for i in range(0, len(bits) // 8 * 8, 8)
    ]
    blocks = [[0] * size_ for count, size_ in version.groups for _ in range(count)]
    k = 0
    for i in range(max(len(b) for b in blocks)):
        for block in blocks:
            if i < len(block):
                block[i] = codes[k]
                k += 1

    stream = "".join(f"{c:08b}" for b in blocks for c in b)
    assert stream[:4] == "0100", "byte mode indicator"
    length = int(stream[4:12], 2)
    return bytes(
        int(stream[12 + 8 * i : 20 + 8 * i], 2) for i in range(length)
    ).decode()


@pytest.mark.parametrize(
    "payload",
    [
        "https://foodos.app/batch/TOM-KLR-00124",
        "https://foodos.app/batch/TOM-KLR-00124-A",
        "https://foodos.app/b/T1",
        "https://foodos.app/batch/" + "X" * 70,
    ],
)
def test_round_trip(payload):
    """The only test that proves a scanner would read it."""
    assert _decode(qr.encode(payload)) == payload


def test_finder_patterns_sit_in_three_corners():
    modules = qr.encode("https://foodos.app/batch/TOM-KLR-00124")
    size = len(modules)
    for base_row, base_col in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(7):
            for c in range(7):
                assert modules[base_row + r][base_col + c] == qr._FINDER[r][c]


def test_timing_patterns_alternate():
    modules = qr.encode("https://foodos.app/batch/TOM-KLR-00124")
    size = len(modules)
    for i in range(8, size - 8):
        assert modules[6][i] == 1 - (i % 2)
        assert modules[i][6] == 1 - (i % 2)


def test_the_dark_module_is_always_set():
    modules = qr.encode("https://foodos.app/batch/TOM-KLR-00124")
    assert modules[len(modules) - 8][8] == 1


def test_the_version_is_the_smallest_that_fits():
    assert len(qr.encode("x" * 26)) == qr._VERSIONS[1].size   # v2 holds 26
    assert len(qr.encode("x" * 27)) == qr._VERSIONS[2].size   # v3 for one more


def test_an_oversized_payload_raises_rather_than_truncating():
    with pytest.raises(qr.QrError, match="exceeds"):
        qr.encode("x" * 200)


# ---------------------------------------------------------------- svg


def test_svg_is_self_contained_and_sized():
    svg = qr.svg("https://foodos.app/batch/TOM-KLR-00124", scale=6)
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert "http://www.w3.org/2000/svg" in svg
    # A version 3 symbol plus two quiet zones, at six pixels a module.
    assert 'width="222"' in svg
    # No external references — it goes into an <img> on a page with a CSP.
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")


def test_svg_quiet_zone_is_present():
    scale = 4
    svg = qr.svg("https://foodos.app/batch/TOM-KLR-00124", scale=scale)
    size = len(qr.encode("https://foodos.app/batch/TOM-KLR-00124"))
    expected = (size + qr.QUIET_ZONE * 2) * scale
    assert f'width="{expected}"' in svg
