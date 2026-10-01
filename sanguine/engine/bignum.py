"""Big-number formatting.

Plain floats cover 1e308, far beyond anything the economy reaches; the risk is
display, not range.  Values are abbreviated (K, M, B ...), then named tiers,
then scientific notation.
"""
import math

SUFFIXES = [
    "", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc",
    "Ud", "Dd", "Td", "Qad", "Qid", "Sxd", "Spd", "Ocd", "Nod", "Vg",
]  # up to 1e63


def fmt(x: float, places: int = 2) -> str:
    """Format a non-negative-ish number compactly: 1.23K, 4.5Qa, 6.7e80."""
    if x != x:
        return "NaN"
    if math.isinf(x):
        return "∞"
    sign = "-" if x < 0 else ""
    x = abs(x)
    if x < 1000:
        if x == int(x):
            return f"{sign}{int(x)}"
        return f"{sign}{x:.{places}f}".rstrip("0").rstrip(".") if x < 100 else f"{sign}{x:.1f}"
    exp3 = int(math.floor(math.log10(x) / 3))
    if exp3 >= len(SUFFIXES):
        e = int(math.floor(math.log10(x)))
        return f"{sign}{x / 10 ** e:.{places}f}e{e}"
    mant = x / 1000 ** exp3
    if round(mant, places) >= 1000:  # 999.999K -> 1.00M
        exp3 += 1
        mant /= 1000
        if exp3 >= len(SUFFIXES):
            e = int(math.floor(math.log10(x)))
            return f"{sign}{x / 10 ** e:.{places}f}e{e}"
    return f"{sign}{mant:.{places}f}{SUFFIXES[exp3]}"


def money(x: float) -> str:
    return "†" + fmt(x)


def duration(seconds: float) -> str:
    """Compact cycle/time display: 0:03, 2:00, 1h00, 3d04h."""
    s = int(max(0, seconds))
    if s < 3600:
        return f"{s // 60}:{s % 60:02d}"
    if s < 86400:
        return f"{s // 3600}h{(s % 3600) // 60:02d}"
    return f"{s // 86400}d{(s % 86400) // 3600:02d}h"
