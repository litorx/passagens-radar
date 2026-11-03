import sys

# Console do Windows (cp1252) quebra com emoji no print; forca UTF-8 sem erro.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
