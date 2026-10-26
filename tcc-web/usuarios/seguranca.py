import hashlib
import secrets
import string
from django.core.cache import cache


def gerar_senha_acesso():
    return ''.join(secrets.choice(string.ascii_letters) for _ in range(3))+''.join(secrets.choice(string.digits) for _ in range(3))


def limite_login_web(request):
    ip=request.META.get('REMOTE_ADDR','')
    usuario=request.POST.get('username','').strip().casefold()
    bloqueado=False
    for valor,limite in [(ip,30),(usuario,10)]:
        chave='login-web:'+hashlib.sha256(valor.encode()).hexdigest()
        cache.add(chave,0,timeout=900)
        try: n=cache.incr(chave)
        except ValueError:
            cache.set(chave,1,timeout=900);n=1
        bloqueado |= n>limite
    return bloqueado
