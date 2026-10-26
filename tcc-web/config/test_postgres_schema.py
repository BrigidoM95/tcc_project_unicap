"""Testes em schema PostgreSQL temporário, sem exigir CREATEDB.

Uso: manage.py test --settings=config.test_postgres_schema
O schema contém apenas dados de teste e é removido ao término. search_path não
inclui public, portanto flush e migrations não alcançam as tabelas da aplicação.
"""
from .test_settings import *
from uuid import uuid4
from django.core.management import call_command
from django.db import connections
from django.test.runner import DiscoverRunner

DEBUG = True
SECURE_SSL_REDIRECT = False
TEST_RUNNER = 'config.test_postgres_schema.SchemaRunner'


class SchemaRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        if self.parallel > 1 or self.keepdb:
            raise RuntimeError('Use este runner sem --parallel e sem --keepdb.')
        db = connections['default']
        if db.vendor != 'postgresql':
            raise RuntimeError('Este runner exige DB_ENGINE=postgres.')
        self.schema = 'unicap_test_' + uuid4().hex
        self.opcoes_antes = dict(db.settings_dict['OPTIONS'])
        with db.cursor() as cursor:
            cursor.execute('CREATE SCHEMA ' + db.ops.quote_name(self.schema))
        self.criado = True
        try:
            db.close()
            db.settings_dict['OPTIONS'] = {
                **self.opcoes_antes, 'options': '-csearch_path=' + self.schema,
            }
            with db.cursor() as cursor:
                cursor.execute('SELECT current_schema(), current_schemas(false)')
                atual, esquemas = cursor.fetchone()
                if atual != self.schema or esquemas != [self.schema]:
                    raise RuntimeError('Isolamento do schema de teste não confirmado.')
            call_command('migrate', verbosity=0, interactive=False)
            return []
        except Exception:
            self.teardown_databases([])
            raise

    def teardown_databases(self, old_config, **kwargs):
        if not getattr(self, 'criado', False):
            return
        db = connections['default']
        db.close()
        db.settings_dict['OPTIONS'] = self.opcoes_antes
        # Somente o nome aleatório que esta execução criou, nunca um nome externo.
        with db.cursor() as cursor:
            cursor.execute('DROP SCHEMA ' + db.ops.quote_name(self.schema) + ' CASCADE')
        self.criado = False
        db.close()
