"""Configuração apenas para atualizar bases que ainda contêm o app vazio associados.

Após backup: python manage.py migrate --settings=config.migracao_legada
O servidor usa config.settings normalmente, sem o app removido.
"""
from .settings import *  # noqa: F403

if 'associados' not in INSTALLED_APPS:  # noqa: F405
    INSTALLED_APPS = [*INSTALLED_APPS, 'associados']  # noqa: F405
