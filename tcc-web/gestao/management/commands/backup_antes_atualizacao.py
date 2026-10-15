"""Verifica o banco antes da instalação; nunca migra PostgreSQL sem orientar backup."""
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Backup automático antes da atualização local de SQLite.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', required=True)

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Este instalador é para SQLite local. Para PostgreSQL, use o roteiro em docs/IMPLANTACAO.md, com pg_dump antes de migrate.')
        if not Path(db['NAME']).is_file():
            self.stdout.write('Banco novo: nenhuma base anterior para copiar.')
            return
        call_command('backup_local', destino=options['destino'])
