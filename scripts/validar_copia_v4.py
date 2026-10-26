"""Migra uma cópia nova do backup e confere cada valor das colunas preservadas."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

raiz=Path(__file__).resolve().parents[1]
origem=Path(sys.argv[1]).resolve()
destino=Path(sys.argv[2]).resolve()
if raiz not in destino.parents or destino.exists():
    raise SystemExit('Use um destino novo dentro do projeto.')
destino.parent.mkdir(parents=True,exist_ok=True)
shutil.copy2(origem,destino)
ambiente={**os.environ,'DB_ENGINE':'sqlite','SQLITE_PATH':str(destino),'DJANGO_DEBUG':'true'}
subprocess.run([sys.executable,'manage.py','migrate','--noinput','--settings=config.test_settings'],
    cwd=raiz/'tcc-web',env=ambiente,check=True)
antes=sqlite3.connect(origem);depois=sqlite3.connect(destino)
def tabelas(c):return {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
def colunas(c,t):return [x[1] for x in c.execute(f'PRAGMA table_info("{t}")')]
def digest(c,t,cols):
    campos=','.join('"'+x+'"' for x in cols)
    linhas=c.execute(f'SELECT {campos} FROM "{t}" ORDER BY "id"').fetchall()
    return len(linhas),hashlib.sha256(json.dumps(linhas,ensure_ascii=False,default=str).encode()).hexdigest()
removidas=tabelas(antes)-tabelas(depois)
assert removidas=={'usuarios_matriculaanual','gestao_fechamentomensal'},removidas
resultados={}
for tabela in sorted(tabelas(antes)&tabelas(depois)):
    if tabela.startswith('sqlite_') or tabela in ('django_migrations','auth_permission','django_content_type'):continue
    cols=[c for c in colunas(antes,tabela) if c in colunas(depois,tabela)]
    if tabela=='embarques_reservaassento':cols.remove('expira_em')  # Migração estende reservas ativas até 03:00.
    a=digest(antes,tabela,cols);b=digest(depois,tabela,cols)
    assert a==b,(tabela,a,b)
    resultados[tabela]={'registros':a[0],'sha256_colunas_preservadas':a[1]}
assert depois.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert depois.execute('PRAGMA foreign_key_check').fetchall()==[]
relatorio={'backup':str(origem),'copia_migrada':str(destino),'tabelas_removidas':sorted(removidas),
    'dados_preservados':resultados,'integridade':'ok','chaves_estrangeiras':'ok'}
arquivo=destino.with_suffix('.validacao.json');arquivo.write_text(json.dumps(relatorio,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Validação concluída: {len(resultados)} tabelas comparadas; relatório em {arquivo}')
