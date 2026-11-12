"""Pure-Python drop-in replacement for `noise.pnoise2` (package `noise` 1.2.2).

Why: the original `noise` package is a C extension last released in 2015 and
has no pre-built wheels for current Python versions on Windows, so
`pip install noise` needs a C compiler. This file reproduces its 2D Perlin
"improved" noise (`pnoise2`) line by line from the original C source
(_perlin.c / _noise.h, (c) 2008 Casey Duncan, MIT licence), including the
permutation and gradient tables, so results match the original up to
float32 rounding.

Only `pnoise2` is provided, because that is the only function
contamination_simulation.py uses. Place this file next to
contamination_simulation.py; `from noise import pnoise2` then finds it.
"""

import math

_GRAD3 = [(1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0), (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1), (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1), (1, 0, -1), (-1, 0, -1), (0, -1, 1), (0, 1, 1)]

_PERM = [
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
    247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
    57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
    74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
    60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
    65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
    200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
    52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
    207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
    119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
    218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
    81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
    184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
    222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
    247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
    57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
    74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
    60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
    65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
    200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
    52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
    207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
    119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
    218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
    81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
    184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
    222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
]


def _lerp(t, a, b):
    return a + t * (b - a)


def _grad2(hash_, x, y):
    gx, gy, _ = _GRAD3[hash_ & 15]
    return x * gx + y * gy


def _noise2(x, y, repeatx, repeaty, base):
    i = int(math.floor(math.fmod(x, repeatx)))
    j = int(math.floor(math.fmod(y, repeaty)))
    ii = int(math.fmod(i + 1, repeatx))
    jj = int(math.fmod(j + 1, repeaty))
    i = (i & 255) + base
    j = (j & 255) + base
    ii = (ii & 255) + base
    jj = (jj & 255) + base

    x -= math.floor(x)
    y -= math.floor(y)
    fx = x * x * x * (x * (x * 6 - 15) + 10)
    fy = y * y * y * (y * (y * 6 - 15) + 10)

    p = _PERM
    a = p[i]
    aa = p[a + j]
    ab = p[a + jj]
    b = p[ii]
    ba = p[b + j]
    bb = p[b + jj]
    return _lerp(
        fy,
        _lerp(fx, _grad2(p[aa], x, y), _grad2(p[ba], x - 1, y)),
        _lerp(fx, _grad2(p[ab], x, y - 1), _grad2(p[bb], x - 1, y - 1)),
    )


def pnoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=1024, repeaty=1024, base=0):
    """Same signature and behaviour as noise.pnoise2."""
    if octaves == 1:
        return _noise2(x, y, repeatx, repeaty, base)
    if octaves < 1:
        raise ValueError("Expected octaves value > 0")
    freq, amp, max_amp, total = 1.0, 1.0, 0.0, 0.0
    for _ in range(octaves):
        total += _noise2(x * freq, y * freq, repeatx * freq, repeaty * freq, base) * amp
        max_amp += amp
        freq *= lacunarity
        amp *= persistence
    return total / max_amp
