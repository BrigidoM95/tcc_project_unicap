"""Copia a base local configurada antes de aplicar migrações."""
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import subprocess
import sys
import zipfile
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Backup antes da atualização: SQLite ou PostgreSQL, incluindo fotos.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', required=True)

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if connection.vendor == 'sqlite':
            if not Path(db['NAME']).is_file():
                self.stdout.write('Banco novo: nenhuma base anterior para copiar.')
                return
            call_command('backup_local', destino=options['destino'])
            return
        if 'django_migrations' not in connection.introspection.table_names():
            self.stdout.write('Banco novo: nenhuma base Django anterior para copiar.')
            return
        destino = Path(options['destino']).resolve()
        destino.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        pg_dump = shutil.which('pg_dump')
        try:
            if pg_dump:
                env = dict(os.environ, PGHOST=db['HOST'], PGPORT=str(db['PORT']),
                    PGDATABASE=db['NAME'], PGUSER=db['USER'], PGPASSWORD=db['PASSWORD'],
                    PGSSLMODE=db.get('OPTIONS', {}).get('sslmode', 'prefer'))
                arquivo = destino / f'{stamp}.dump'
                subprocess.run([pg_dump, '--format=custom', '--file', str(arquivo)], env=env, check=True)
            else:
                arquivo = destino / f'{stamp}-dados-django.sqlite3'
                script = settings.BASE_DIR.parent / 'scripts' / 'copiar_banco_para_validacao.py'
                subprocess.run([sys.executable, str(script), str(arquivo)], check=True)
                self.stdout.write('pg_dump indisponível: cópia portátil dos dados Django criada. '
                    'Para produção, mantenha também o backup PostgreSQL completo de deploy/backup.sh.')
            media = Path(settings.MEDIA_ROOT)
            if media.is_dir():
                with zipfile.ZipFile(destino / f'{stamp}-media.zip', 'x', zipfile.ZIP_DEFLATED) as pacote:
                    for foto in media.rglob('*'):
                        if foto.is_file():
                            pacote.write(foto, foto.relative_to(media))
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CommandError('Falha no backup; a atualização foi interrompida.') from exc
        self.stdout.write(f'Backup anterior à atualização: {arquivo}')
