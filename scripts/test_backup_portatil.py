"""Regressão: copiar a base não executa migrações de dados nem altera datas."""
import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

RAIZ=Path(__file__).resolve().parents[1]


class BackupPortatilTests(unittest.TestCase):
    def test_copia_fiel_sem_escrever_na_origem(self):
        (RAIZ/'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='teste-backup-',dir=RAIZ/'tmp') as pasta:
            origem=Path(pasta)/'origem.sqlite3';destino=Path(pasta)/'copia.sqlite3'
            env={**os.environ,'DB_ENGINE':'sqlite','SQLITE_PATH':str(origem),
                'DJANGO_DEBUG':'true','DJANGO_SETTINGS_MODULE':'config.test_settings'}
            subprocess.run([sys.executable,'manage.py','migrate','--noinput'],
                cwd=RAIZ/'tcc-web',env=env,check=True,capture_output=True)
            # Datas antigas distinguem fielmente o dado original de auto_now_add.
            seed="""from django.contrib.auth import get_user_model
from usuarios.models import Usuario,Instituicao,Curso
from gestao.models import LogAuditoria
u=get_user_model().objects.create_user(username='backup-teste',first_name='Teste')
i=Instituicao.objects.create(nome='Instituição teste')
c=Curso.objects.create(nome='Curso teste',instituicao=i)
Usuario.objects.create(user=u,tipo='associado',curso=c)
log=LogAuditoria.objects.create(acao='teste')
LogAuditoria.objects.filter(pk=log.pk).update(criado_em='2020-01-02T03:04:05Z')
"""
            subprocess.run([sys.executable,'manage.py','shell','-c',seed],
                cwd=RAIZ/'tcc-web',env=env,check=True,capture_output=True)
            hash_antes=hashlib.sha256(origem.read_bytes()).hexdigest()
            subprocess.run([sys.executable,str(RAIZ/'scripts/copiar_banco_para_validacao.py'),str(destino)],
                cwd=RAIZ,env=env,check=True,capture_output=True)
            self.assertEqual(hash_antes,hashlib.sha256(origem.read_bytes()).hexdigest())
            with closing(sqlite3.connect(origem)) as a,closing(sqlite3.connect(destino)) as b:
                tabelas=[r[0] for r in a.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                for tabela in tabelas:
                    cols=[r[1] for r in a.execute(f'PRAGMA table_info("{tabela}")')]
                    # IDs internos dos registros de migração podem ter ordem diferente.
                    if tabela=='django_migrations':cols=['app','name']
                    campos=','.join('"'+c+'"' for c in cols)
                    aa=sorted(a.execute(f'SELECT {campos} FROM "{tabela}"').fetchall(),key=repr)
                    bb=sorted(b.execute(f'SELECT {campos} FROM "{tabela}"').fetchall(),key=repr)
                    self.assertEqual(aa,bb,tabela)
                self.assertEqual(b.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(b.execute('PRAGMA foreign_key_check').fetchall(),[])
            manifesto=json.loads(destino.with_suffix('.manifesto.json').read_text())
            self.assertEqual(manifesto['sha256'],hashlib.sha256(destino.read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
