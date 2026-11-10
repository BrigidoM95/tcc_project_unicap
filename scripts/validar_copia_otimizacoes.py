"""Ensaiar a limpeza de outubro em uma cópia e comparar todos os dados preservados."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

raiz = Path(__file__).resolve().parents[1]
origem = Path(sys.argv[1]).resolve()
destino = Path(sys.argv[2]).resolve()
if raiz not in destino.parents or destino.exists() or not origem.is_file():
    raise SystemExit('Informe um backup existente e um destino novo dentro do projeto.')
destino.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(origem, destino)
ambiente = {**os.environ, 'DB_ENGINE': 'sqlite', 'SQLITE_PATH': str(destino), 'DJANGO_DEBUG': 'true'}
subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput',
                '--settings=config.migracao_legada'], cwd=raiz/'tcc-web', env=ambiente, check=True)

antes = sqlite3.connect(origem)
depois = sqlite3.connect(destino)


def tabelas(conexao):
    return {x[0] for x in conexao.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def colunas(conexao, tabela):
    return [x[1] for x in conexao.execute(f'PRAGMA table_info("{tabela}")')]


def digest(conexao, tabela, campos):
    nomes = ','.join('"'+x+'"' for x in campos)
    # Ordena pela chave real, inclusive o cache cuja chave não se chama id.
    ordem = 'id' if 'id' in campos else campos[0]
    linhas = conexao.execute(f'SELECT {nomes} FROM "{tabela}" ORDER BY "{ordem}"').fetchall()
    return len(linhas), hashlib.sha256(json.dumps(linhas, default=str).encode()).hexdigest()


removidas = tabelas(antes)-tabelas(depois)
assert removidas == {'associados_associado', 'paginas_pagina'}, removidas
for tabela in removidas:
    assert antes.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0] == 0
resultados = {}
for tabela in sorted(tabelas(antes)&tabelas(depois)):
    if tabela.startswith('sqlite_') or tabela == 'django_migrations':
        continue
    antigas, novas = colunas(antes, tabela), colunas(depois, tabela)
    excluidas = set(antigas)-set(novas)
    assert excluidas == ({'codigo_curto'} if tabela == 'embarques_sessaoembarque' else set()), (tabela, excluidas)
    if excluidas:
        assert antes.execute('SELECT COUNT(*) FROM embarques_sessaoembarque '
                             "WHERE codigo_curto IS NOT NULL AND codigo_curto <> ''").fetchone()[0] == 0
    campos = [campo for campo in antigas if campo in novas]
    a, b = digest(antes, tabela, campos), digest(depois, tabela, campos)
    assert a == b, (tabela, 'Dados alterados inesperadamente')
    resultados[tabela] = {'registros': a[0], 'sha256_colunas_preservadas': a[1]}
assert depois.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
assert depois.execute('PRAGMA foreign_key_check').fetchall() == []
relatorio = {'backup': str(origem), 'copia_migrada': str(destino),
             'tabelas_vazias_removidas': sorted(removidas), 'dados_preservados': resultados,
             'integridade': 'ok', 'chaves_estrangeiras': 'ok'}
arquivo = destino.with_suffix('.validacao.json')
arquivo.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Validação concluída: {len(resultados)} tabelas preservadas comparadas; relatório em {arquivo}')
