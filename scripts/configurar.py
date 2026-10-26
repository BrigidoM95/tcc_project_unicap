"""Cria .env somente se não existir. Não imprime segredos."""
import argparse
import secrets
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--producao',action='store_true');args=p.parse_args()
raiz=Path(__file__).resolve().parents[1]
base=raiz/('deploy' if args.producao else 'tcc-web')
dest=base/'.env'
if dest.exists(): raise SystemExit('O .env já existe; mantenha-o ou edite manualmente.')
s=(base/'.env.example').read_text(encoding='utf-8')
if args.producao:
    dominio=input('Domínio do servidor (sem https://): ').strip()
    if not dominio or '/' in dominio or '\n' in dominio or ' ' in dominio: raise SystemExit('Domínio inválido.')
    s=s.replace('transporte.seudominio.com.br',dominio).replace('SUBSTITUA_POR_UMA_CHAVE_ALEATORIA_DE_PELO_MENOS_50_CARACTERES',secrets.token_urlsafe(64)).replace('SUBSTITUA_POR_UMA_SENHA_ALEATORIA',secrets.token_urlsafe(32))
else: s=s.replace('DJANGO_SECRET_KEY=\n','DJANGO_SECRET_KEY='+secrets.token_urlsafe(64)+'\n')
with dest.open('x',encoding='utf-8') as f:f.write(s)
try:dest.chmod(0o600)
except OSError:pass
print('Configuração criada:',dest)
