"""Backup consistente do SQLite e fotos; não restaura nem sobrescreve o banco."""
import os
import sqlite3
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
class Command(BaseCommand):
    help='Gera um .tar.gz do SQLite e media em destino privado.'
    def add_arguments(self,p): p.add_argument('--destino',required=True)
    def handle(self,*args,**opts):
        db=settings.DATABASES['default']
        if db['ENGINE']!='django.db.backends.sqlite3': raise CommandError('Use pg_dump para PostgreSQL; veja deploy/backup.sh.')
        destino=Path(opts['destino']).resolve();destino.mkdir(parents=True,exist_ok=True)
        nome=destino/('unicap-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.tar.gz')
        with tempfile.TemporaryDirectory() as pasta:
            copia=Path(pasta)/'db.sqlite3'
            with sqlite3.connect(db['NAME']) as origem,sqlite3.connect(copia) as saida: origem.backup(saida)
            # Arquivo privado desde a criação.
            fd=os.open(nome,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as f,tarfile.open(fileobj=f,mode='w:gz') as tar:
                tar.add(copia,arcname='db.sqlite3')
                if settings.MEDIA_ROOT.exists(): tar.add(settings.MEDIA_ROOT,arcname='media')
        self.stdout.write(self.style.SUCCESS(str(nome)))
