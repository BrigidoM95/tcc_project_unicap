"""Atualiza hashes do código e documentação, excluindo dados privados e artefatos locais."""
import hashlib
import json
import os
from pathlib import Path

raiz = Path(__file__).resolve().parents[1]
destino = raiz/'MANIFESTO_SHA256.json'
pastas_excluidas = {
    '.git', '.venv', 'venv', '__pycache__', '.ruff_cache', '.dart_tool',
    '.gradle', '.kotlin', '.idea', 'build', 'tmp', 'backups', 'media', 'staticfiles',
    'Pods', '.symlinks', 'ephemeral', 'node_modules',
}
arquivos_excluidos = {
    '.env', '.local-secret', 'key.properties', 'local.properties',
    '.flutter-plugins-dependencies', 'dados-migracao.json', destino.name,
}
manifesto = {}
for pasta, subpastas, arquivos in os.walk(raiz, followlinks=False):
    subpastas[:] = [nome for nome in subpastas if nome not in pastas_excluidas]
    for nome in arquivos:
        arquivo = Path(pasta)/nome
        relativo = arquivo.relative_to(raiz)
        if nome in arquivos_excluidos or arquivo.is_symlink():
            continue
        if arquivo.suffix.lower() in {'.pyc', '.sqlite3', '.db', '.jks', '.keystore', '.pem', '.p12'}:
            continue
        if '.sqlite3-' in nome or nome.startswith('.env.') and nome != '.env.example':
            continue
        if arquivo.suffix == '.log' and relativo.parts[0] != 'docs':
            continue
        manifesto[relativo.as_posix()] = hashlib.sha256(arquivo.read_bytes()).hexdigest()
destino.write_text(json.dumps(dict(sorted(manifesto.items())), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(f'Manifesto atualizado: {len(manifesto)} arquivos; sem bancos, segredos, backups ou builds.')
