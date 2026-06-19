#!/usr/bin/env python3
"""Inicializa tabelas PostgreSQL do IA Server Santos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.database.connection import init_db


def main():
    init_db()
    print("OK: tabelas criadas em ia_server_santos (PostgreSQL)")


if __name__ == "__main__":
    main()
