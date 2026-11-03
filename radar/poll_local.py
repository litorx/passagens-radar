"""Comandos do Telegram lidos pelo SEU PC (a cada 2 min), para resposta quase imediata.

O GitHub so roda o bot da nuvem a cada 6-8 h na pratica (medido em 03/11/2026). Este leitor local usa o
mesmo codigo (`radar.poll`), grava a config no repositorio e, se a nuvem for a unica ligada, ela continua
funcionando como reserva (mais lenta).
"""
from __future__ import annotations

import subprocess
import sys

from . import config, poll


def g(*a):
    return subprocess.run(["git", *a], cwd=config.ROOT, capture_output=True, text=True, timeout=120)


def main() -> int:
    config.load_env()
    g("pull", "--rebase", "--autostash", "-q")
    rc = poll.main()
    g("add", "data/config.json", "data/bot_offset.json")
    if g("diff", "--cached", "--quiet").returncode != 0:
        g("-c", "user.name=radar-pc", "-c", "user.email=radar-pc@users.noreply.github.com",
          "commit", "-q", "-m", "config [skip ci]")
        for _ in range(3):
            if g("pull", "--rebase", "--autostash", "-q").returncode == 0 and g("push", "-q").returncode == 0:
                break
    return rc


if __name__ == "__main__":
    sys.exit(main())
