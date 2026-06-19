"""Pacote de configuração — expõe o módulo settings e helpers."""

import importlib

from config.settings import AppSettings, get_settings, reload_settings

# Módulo config.settings (NÃO a view) — evita shadowing em `import config.settings`
settings = importlib.import_module("config.settings")

__all__ = ["AppSettings", "get_settings", "reload_settings", "settings"]
