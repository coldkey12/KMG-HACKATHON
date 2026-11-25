"""Text normalisation used by quote/number checks. Language-agnostic."""
import hashlib
import re
import unicodedata

_LATEX_DELIMS = re.compile(r"\\\(|\\\)|\\\[|\\\]|\$\$?")
_DASHES = re.compile(r"[‐-―−]")
_QUOTES = re.compile(r"[«»“”„\"']")
_WS = re.compile(r"\s+")


def norm(s: str) -> str:
    """Normalise for substring matching: NFKC, lower, ё→е, no LaTeX delimiters, unified dashes/quotes, collapsed spaces."""
    s = unicodedata.normalize("NFKC", s or "")
    s = _LATEX_DELIMS.sub(" ", s)
    s = s.replace("ё", "е").replace("Ё", "Е").lower()
    s = _DASHES.sub("-", s)
    s = _QUOTES.sub("", s)
    s = s.replace("…", "...")
    s = _WS.sub(" ", s)
    return s.strip()


def hash6(s: str) -> str:
    return hashlib.sha1(norm(s).encode("utf-8")).hexdigest()[:6]


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# Numbers: 0,46 | 1083 | 10³ | 4—8 | 1,2÷1,3 ; we compare canonical numeric strings.
_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")
_NUM = re.compile(r"(?<![\w.,])[-−]?\d+(?:[.,]\d+)?")


def numbers(s: str):
    """Canonical numbers in a text: decimal comma -> dot, superscripts -> digits, leading zeros kept off."""
    s = unicodedata.normalize("NFKC", s or "").translate(_SUP)
    out = []
    for m in _NUM.finditer(s):
        t = m.group(0).replace("−", "-").replace(",", ".")
        try:
            v = float(t)
        except ValueError:
            continue
        out.append(_canon(v))
    return out


def _canon(v: float) -> str:
    if v == int(v):
        return str(int(v))
    return ("%.6f" % v).rstrip("0").rstrip(".")
