import sys
from pathlib import Path

# pythonw (tarefas sem janela) nao tem console: grava em data_local/log.txt para voce poder ver erros.
if sys.stdout is None or sys.stderr is None:
    _d = Path(__file__).resolve().parent.parent / "data_local"
    _d.mkdir(exist_ok=True)
    _f = open(_d / "log.txt", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _f
    sys.stderr = sys.stderr or _f

# Console do Windows (cp1252) quebra com emoji no print; forca UTF-8 sem erro.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
