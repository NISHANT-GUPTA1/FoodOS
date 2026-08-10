"""A minimal QR encoder — batch code in, SVG out.

**Why this is written rather than installed.** `backend/README.md` requires a
justification before a dependency is added, and the honest one here was thin:
the payload is a forty-character URL, always the same shape, rendered once per
batch. That is the narrowest corner of the QR specification — byte mode, a
single small version, one error-correction level — and it is about three
hundred lines. `qrcode` would also pull in Pillow for image output, which is a
large surface for a product whose only use of it would be to draw black
squares. SVG needs no imaging library at all: it scales on a phone screen and
on a printed crate label without a resolution decision.

**Scope.** Byte mode, versions 1-6, error correction level M. Version 6 holds
106 bytes, roughly twice the longest URL this system can produce, and stopping
below version 7 means the format-only header — versions 7 and up carry an extra
eighteen-bit version block that would be dead code here. Anything longer raises
rather than silently truncating.

Level M (about 15% recovery) rather than L: these labels get stapled to a crate
that then travels a thousand kilometres on an open truck. The extra codewords
cost nothing and a scuffed label still scans.

Implements ISO/IEC 18004. The structure is standard and deliberately written to
be read against the spec: encode -> error correct -> interleave -> place ->
mask -> format.
"""

from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------
# GF(256) — the field Reed-Solomon works in.
#
# Primitive polynomial x^8 + x^4 + x^3 + x^2 + 1 (0x11D), generator 2. Both are
# fixed by the QR specification; they are not tuning knobs.
# --------------------------------------------------------------------------

_PRIMITIVE = 0x11D

_EXP: list[int] = [0] * 512
_LOG: list[int] = [0] * 256


def _build_tables() -> None:
    x = 1
    for i in range(255):
        _EXP[i] = x
        _LOG[x] = i
        x <<= 1
        if x & 0x100:
            x ^= _PRIMITIVE
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_build_tables()


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _generator_poly(degree: int) -> list[int]:
    """(x - 2^0)(x - 2^1)...(x - 2^(degree-1)), coefficients high to low."""
    poly = [1]
    for i in range(degree):
        poly = _poly_mul(poly, [1, _EXP[i]])
    return poly


def _poly_mul(a: list[int], b: list[int]) -> list[int]:
    out = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        if ai == 0:
            continue
        for j, bj in enumerate(b):
            out[i + j] ^= _mul(ai, bj)
    return out


def reed_solomon(data: list[int], ec_count: int) -> list[int]:
    """The `ec_count` error-correction codewords for `data`.

    Polynomial long division of the message (shifted left by `ec_count`) by the
    generator polynomial; the remainder is the check codewords. The invariant
    worth remembering — and the one the tests assert — is that the concatenated
    message-plus-remainder is exactly divisible by the generator.
    """
    gen = _generator_poly(ec_count)
    remainder = list(data) + [0] * ec_count

    for i in range(len(data)):
        coef = remainder[i]
        if coef == 0:
            continue
        for j, g in enumerate(gen):
            remainder[i + j] ^= _mul(g, coef)

    return remainder[len(data) :]


# --------------------------------------------------------------------------
# Version tables (level M only)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Version:
    number: int
    #: EC codewords per block.
    ec_per_block: int
    #: (block count, data codewords per block) groups.
    groups: tuple[tuple[int, int], ...]
    #: Row/column centres of the alignment patterns.
    alignment: tuple[int, ...]

    @property
    def size(self) -> int:
        return self.number * 4 + 17

    @property
    def data_codewords(self) -> int:
        return sum(count * size for count, size in self.groups)

    @property
    def capacity_bytes(self) -> int:
        """Payload bytes that fit, after the 4-bit mode and 8-bit length."""
        return self.data_codewords - 2


#: Level M, versions 1-6. Straight from ISO/IEC 18004 table 9; the invariant
#: `data + blocks * ec == total codewords for the version` is asserted in the
#: tests so a typo here cannot ship.
_VERSIONS: tuple[_Version, ...] = (
    _Version(1, 10, ((1, 16),), ()),
    _Version(2, 16, ((1, 28),), (6, 18)),
    _Version(3, 26, ((1, 44),), (6, 22)),
    _Version(4, 18, ((2, 32),), (6, 26)),
    _Version(5, 24, ((2, 43),), (6, 30)),
    _Version(6, 16, ((4, 27),), (6, 34)),
)

#: Level M as it appears in the format information. Not the same as the "M" in
#: any sensible ordering — the spec's bit assignment is L=01, M=00, Q=11, H=10.
_EC_LEVEL_BITS = 0b00

_FORMAT_GENERATOR = 0b101_0011_0111
_FORMAT_MASK = 0b101_0100_0001_0010


class QrError(ValueError):
    """The payload does not fit, or is not encodable."""


def _pick_version(length: int) -> _Version:
    for version in _VERSIONS:
        if length <= version.capacity_bytes:
            return version
    raise QrError(
        f"{length} bytes exceeds {_VERSIONS[-1].capacity_bytes} — the largest "
        "version this encoder supports. A batch URL should never be this long."
    )


# --------------------------------------------------------------------------
# Stage 1: bitstream
# --------------------------------------------------------------------------


def _encode_data(payload: bytes, version: _Version) -> list[int]:
    bits: list[int] = []

    def put(value: int, width: int) -> None:
        for i in range(width - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)          # byte mode
    put(len(payload), 8)    # count indicator is 8 bits for versions 1-9
    for byte in payload:
        put(byte, 8)

    capacity_bits = version.data_codewords * 8

    # Terminator: up to four zero bits, truncated if the stream is nearly full.
    put(0, min(4, capacity_bits - len(bits)))
    # Pad to a byte boundary.
    while len(bits) % 8:
        bits.append(0)

    codewords = [
        int("".join(str(b) for b in bits[i : i + 8]), 2) for i in range(0, len(bits), 8)
    ]
    # The specification's alternating pad bytes. Not arbitrary filler: the
    # pattern is chosen so padding cannot imitate a finder pattern.
    pad = (0xEC, 0x11)
    pads_added = 0
    while len(codewords) < version.data_codewords:
        codewords.append(pad[pads_added % 2])
        pads_added += 1
    return codewords


# --------------------------------------------------------------------------
# Stage 2: blocks and interleaving
# --------------------------------------------------------------------------


def _interleave(codewords: list[int], version: _Version) -> list[int]:
    """Split into blocks, error-correct each, then interleave.

    Interleaving is what makes the format robust to a scuff rather than a
    speck: a physical smudge takes out consecutive modules, and spreading each
    block's codewords across the symbol turns one long burst into a few
    recoverable errors in every block.
    """
    blocks: list[list[int]] = []
    offset = 0
    for count, size in version.groups:
        for _ in range(count):
            blocks.append(codewords[offset : offset + size])
            offset += size

    ec_blocks = [reed_solomon(b, version.ec_per_block) for b in blocks]

    out: list[int] = []
    longest = max(len(b) for b in blocks)
    for i in range(longest):
        for block in blocks:
            if i < len(block):
                out.append(block[i])
    for i in range(version.ec_per_block):
        for block in ec_blocks:
            out.append(block[i])
    return out


# --------------------------------------------------------------------------
# Stage 3: the matrix
# --------------------------------------------------------------------------

_FINDER = [
    [1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 1],
    [1, 0, 1, 1, 1, 0, 1],
    [1, 0, 1, 1, 1, 0, 1],
    [1, 0, 1, 1, 1, 0, 1],
    [1, 0, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1],
]


class _Matrix:
    """Modules plus a reservation map of which ones the data may not touch."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.modules = [[0] * size for _ in range(size)]
        self.reserved = [[False] * size for _ in range(size)]

    def set(self, row: int, col: int, value: int, *, reserve: bool = True) -> None:
        self.modules[row][col] = value
        if reserve:
            self.reserved[row][col] = True


def _place_function_patterns(m: _Matrix, version: _Version) -> None:
    size = m.size

    for base_row, base_col in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(7):
            for c in range(7):
                m.set(base_row + r, base_col + c, _FINDER[r][c])
        # Separators — the one-module quiet ring around each finder.
        for i in range(8):
            for rr, cc in (
                (base_row + i, base_col - 1),
                (base_row + i, base_col + 7),
                (base_row - 1, base_col + i),
                (base_row + 7, base_col + i),
            ):
                if 0 <= rr < size and 0 <= cc < size:
                    m.set(rr, cc, 0)

    # Timing patterns.
    for i in range(8, size - 8):
        bit = 1 - (i % 2)
        m.set(6, i, bit)
        m.set(i, 6, bit)

    # Alignment patterns, skipping the three that would sit on a finder.
    centres = version.alignment
    for r in centres:
        for c in centres:
            if (r < 9 and c < 9) or (r < 9 and c > size - 10) or (r > size - 10 and c < 9):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    value = 1 if max(abs(dr), abs(dc)) != 1 else 0
                    m.set(r + dr, c + dc, value)

    # The dark module. Always set, always here.
    m.set(size - 8, 8, 1)

    # Reserve the format information areas; the bits go in after masking.
    for i in range(9):
        if not m.reserved[8][i] or i == 6:
            m.reserved[8][i] = True
        if not m.reserved[i][8] or i == 6:
            m.reserved[i][8] = True
    for i in range(8):
        m.reserved[8][size - 1 - i] = True
        m.reserved[size - 1 - i][8] = True


def _place_data(m: _Matrix, bits: list[int]) -> None:
    """The zigzag: two columns at a time, right to left, alternating direction."""
    size = m.size
    index = 0
    upward = True
    col = size - 1

    while col > 0:
        if col == 6:  # the vertical timing column is skipped entirely
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if m.reserved[row][c]:
                    continue
                m.modules[row][c] = bits[index] if index < len(bits) else 0
                index += 1
        upward = not upward
        col -= 2


_MASKS = (
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
)


def _apply_mask(m: _Matrix, mask: int) -> _Matrix:
    out = _Matrix(m.size)
    out.reserved = [row[:] for row in m.reserved]
    rule = _MASKS[mask]
    for r in range(m.size):
        for c in range(m.size):
            value = m.modules[r][c]
            if not m.reserved[r][c] and rule(r, c):
                value ^= 1
            out.modules[r][c] = value
    return out


def _penalty(m: _Matrix) -> int:
    """The four penalty rules. Lower is better; the best-scoring mask wins.

    These exist to keep the symbol scannable — they punish long same-colour
    runs, solid blocks, anything resembling a finder pattern, and a lopsided
    black/white balance. Skipping the evaluation and hardcoding a mask produces
    a symbol that usually scans, which is the worst kind of bug to ship on a
    label nobody will test until the demo.
    """
    size = m.size
    grid = m.modules
    score = 0

    # Rule 1 — runs of five or more.
    for line in list(grid) + [list(col) for col in zip(*grid)]:
        run, previous = 1, line[0]
        for value in line[1:]:
            if value == previous:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, previous = 1, value
        if run >= 5:
            score += 3 + (run - 5)

    # Rule 2 — solid 2x2 blocks.
    for r in range(size - 1):
        for c in range(size - 1):
            block = grid[r][c] + grid[r][c + 1] + grid[r + 1][c] + grid[r + 1][c + 1]
            if block in (0, 4):
                score += 3

    # Rule 3 — the 1:1:3:1:1 finder-like pattern, with four light modules.
    pattern_a = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    pattern_b = list(reversed(pattern_a))
    for line in list(grid) + [list(col) for col in zip(*grid)]:
        for i in range(size - 10):
            window = line[i : i + 11]
            if window == pattern_a or window == pattern_b:
                score += 40

    # Rule 4 — deviation from an even black/white split.
    dark = sum(sum(row) for row in grid)
    ratio = dark * 100 // (size * size)
    score += 10 * (min(abs(ratio - 50) // 5, 10))
    return score


def _format_bits(mask: int) -> int:
    """15-bit BCH format information for level M and the chosen mask."""
    data = (_EC_LEVEL_BITS << 3) | mask
    value = data << 10
    for i in range(4, -1, -1):
        if value & (1 << (i + 10)):
            value ^= _FORMAT_GENERATOR << i
    return ((data << 10) | value) ^ _FORMAT_MASK


def _place_format(m: _Matrix, mask: int) -> None:
    bits = _format_bits(mask)
    size = m.size

    def bit(i: int) -> int:
        return (bits >> i) & 1

    # Copy one — around the top-left finder.
    for i in range(6):
        m.modules[8][i] = bit(i)
    m.modules[8][7] = bit(6)
    m.modules[8][8] = bit(7)
    m.modules[7][8] = bit(8)
    for i in range(9, 15):
        m.modules[14 - i][8] = bit(i)

    # Copy two — split between the other two finders, so a symbol with one
    # corner damaged still yields its format.
    for i in range(8):
        m.modules[8][size - 1 - i] = bit(i)
    for i in range(8, 15):
        m.modules[size - 15 + i][8] = bit(i)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def encode(payload: str) -> list[list[int]]:
    """Encode `payload` and return the module matrix, 1 = dark."""
    data = payload.encode("utf-8")
    version = _pick_version(len(data))

    codewords = _encode_data(data, version)
    final = _interleave(codewords, version)
    bits = [(byte >> i) & 1 for byte in final for i in range(7, -1, -1)]

    base = _Matrix(version.size)
    _place_function_patterns(base, version)
    _place_data(base, bits)

    best, best_score = None, None
    for mask in range(8):
        candidate = _apply_mask(base, mask)
        _place_format(candidate, mask)
        score = _penalty(candidate)
        if best_score is None or score < best_score:
            best, best_score = candidate, score

    assert best is not None
    return best.modules


#: Four modules of quiet zone. The specification's minimum; below it, phone
#: scanners lose the symbol against a busy crate label.
QUIET_ZONE = 4


def svg(payload: str, *, scale: int = 4, dark: str = "#111827", light: str = "#ffffff") -> str:
    """A standalone SVG for `payload`.

    One `<path>` of rectangles rather than one `<rect>` per module: a version 3
    symbol has about a thousand dark modules, and a thousand elements is a
    heavy thing to hand a browser for something that renders at 120 pixels.
    """
    modules = encode(payload)
    size = len(modules)
    total = (size + QUIET_ZONE * 2) * scale

    parts: list[str] = []
    for r, row in enumerate(modules):
        c = 0
        while c < size:
            if not row[c]:
                c += 1
                continue
            run = c
            while run < size and row[run]:
                run += 1
            x = (c + QUIET_ZONE) * scale
            y = (r + QUIET_ZONE) * scale
            parts.append(f"M{x} {y}h{(run - c) * scale}v{scale}h-{(run - c) * scale}z")
            c = run

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="{total}" '
        f'viewBox="0 0 {total} {total}" shape-rendering="crispEdges" '
        f'role="img" aria-label="QR code for {payload}">'
        f'<rect width="{total}" height="{total}" fill="{light}"/>'
        f'<path fill="{dark}" d="{"".join(parts)}"/>'
        f"</svg>"
    )
