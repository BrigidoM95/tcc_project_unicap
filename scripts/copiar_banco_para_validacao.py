"""Cópia consistente dos dados Django para SQLite, sem modificar a origem.

Usa o estado das migrações já aplicadas (não os modelos novos), conserva PKs,
vínculos, hashes de senha, sessões e registros históricos. Destino deve ser novo.
Não substitui o pg_dump completo configurado para produção.
"""
import os,sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone

RAIZ=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RAIZ/'tcc-web'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.db import connections,transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

destino=Path(sys.argv[1]).resolve()
if destino.exists():raise SystemExit('O destino já existe; nenhuma cópia foi sobrescrita.')
if RAIZ not in destino.parents:raise SystemExit('Use um destino dentro do projeto.')
destino.parent.mkdir(parents=True,exist_ok=True)
origem=connections['default'];executor=MigrationExecutor(origem)
aplicadas=set(executor.loader.applied_migrations)
alvos=[n for n in aplicadas if n in executor.loader.graph.node_map and not any(x.key in aplicadas for x in executor.loader.graph.node_map[n].children)]
apps=executor.loader.project_state(alvos).apps
connections.databases['copia']={'ENGINE':'django.db.backends.sqlite3','NAME':str(destino),'TIME_ZONE':None,'CONN_MAX_AGE':0,'CONN_HEALTH_CHECKS':False,'AUTOCOMMIT':True,'ATOMIC_REQUESTS':False,'OPTIONS':{},'USER':'','PASSWORD':'','HOST':'','PORT':'','TEST':{}}
copia=connections['copia']
# Materializa o estado final sem executar RunPython históricos. Migrações antigas
# podem usar implicitamente o alias default e nunca devem agir sobre a origem.
with copia.schema_editor() as editor:
    for modelo in apps.get_models():
        if modelo._meta.managed and not modelo._meta.proxy:
            editor.create_model(modelo)
recorder=MigrationRecorder(copia)
recorder.ensure_schema()
for app,nome in sorted(aplicadas):
    recorder.record_applied(app,nome)
contagens={}
with transaction.atomic(using='default'):
    if origem.vendor=='postgresql':
        with origem.cursor() as cursor:cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
    copia.disable_constraint_checking()
    with transaction.atomic(using='copia'):
        for modelo in apps.get_models(include_auto_created=True):
            if not modelo._meta.managed or modelo._meta.proxy:continue
            tabela=modelo._meta.db_table
            # Migrações podem ter semeado permissões ou cache; a origem é soberana.
            with copia.cursor() as cursor:cursor.execute('DELETE FROM '+copia.ops.quote_name(tabela))
            objetos=list(modelo._base_manager.using('default').all())
            # bulk_create também chama Field.pre_save: desative datas automáticas
            # no modelo histórico para conservar o instante original de cada linha.
            for campo in modelo._meta.local_fields:
                if getattr(campo,'auto_now',False):campo.auto_now=False
                if getattr(campo,'auto_now_add',False):campo.auto_now_add=False
            modelo._base_manager.using('copia').bulk_create(objetos,batch_size=300)
            contagens[tabela]=len(objetos)
    copia.check_constraints();copia.enable_constraint_checking()
copia.close()
manifesto={'criado_em':datetime.now(timezone.utc).isoformat(),'origem':origem.vendor,'tabelas':contagens,'migracoes':sorted([list(x) for x in aplicadas]),'sha256':hashlib.sha256(destino.read_bytes()).hexdigest()}
destino.with_suffix('.manifesto.json').write_text(json.dumps(manifesto,indent=2),encoding='utf-8')
print(json.dumps({'copia':str(destino),'tabelas':len(contagens),'registros':sum(contagens.values())}))
