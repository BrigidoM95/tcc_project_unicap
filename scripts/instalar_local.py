"""Instala/atualiza o backend local, com backup antes das migrations."""
import os
from pathlib import Path
import subprocess
import sys
import venv

RAIZ = Path(__file__).resolve().parents[1]
WEB = RAIZ / 'tcc-web'
AMBIENTE = RAIZ / '.venv'
PYTHON = AMBIENTE / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def executar(*args, cwd=WEB):
    subprocess.run([str(PYTHON), *args], cwd=cwd, check=True)


def main():
    if sys.version_info < (3, 12):
        raise SystemExit('Instale Python 3.12 ou mais recente antes de continuar.')
    if not PYTHON.exists():
        print('Criando ambiente Python isolado...', flush=True)
        venv.EnvBuilder(with_pip=True).create(AMBIENTE)
    executar('-m', 'pip', 'install', '-r', 'requirements.txt')
    if not (WEB / '.env').exists():
        executar(str(RAIZ / 'scripts/configurar.py'))

    # Usa a mesma configuração do Django para respeitar SQLITE_PATH e DB_ENGINE.
    executar('manage.py', 'backup_antes_atualizacao', '--destino', str(RAIZ / 'backups'))
    executar('manage.py', 'migrate', '--noinput')
    executar('manage.py', 'check')
    print('\nInstalação concluída. Abra LEIA-ME-PRIMEIRO.md para criar o acesso e iniciar.')


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as e:
        raise SystemExit(f'A instalação parou no comando que apresentou erro (código {e.returncode}).')
