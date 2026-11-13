"""URLs públicas de leitura para as fotos de ônibus usadas pelo painel e pelo app.

Os arquivos continuam armazenados no backend configurado do Django. Este endpoint
apenas os entrega por uma rota estável, inclusive com DEBUG=False no Railway.
"""
from mimetypes import guess_type
from pathlib import PurePosixPath

from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_safe

from .models import Onibus

_EXTENSOES = {'.jpg', '.jpeg', '.png', '.webp'}


def _servir_imagem(onibus_id, campo):
    onibus = get_object_or_404(Onibus.objects.only('foto', 'miniatura'), pk=onibus_id)
    imagem = getattr(onibus, campo)
    if not imagem or PurePosixPath(imagem.name).suffix.lower() not in _EXTENSOES:
        raise Http404('Fotografia indisponível.')
    try:
        arquivo = imagem.storage.open(imagem.name, mode='rb')
    except (FileNotFoundError, OSError, ValueError, SuspiciousFileOperation):
        raise Http404('Fotografia indisponível.')
    resposta = FileResponse(arquivo, content_type=guess_type(imagem.name)[0] or 'application/octet-stream')
    resposta['X-Content-Type-Options'] = 'nosniff'
    resposta['Cache-Control'] = 'public, max-age=300'
    return resposta


@require_safe
def foto_publica(request, onibus_id):
    return _servir_imagem(onibus_id, 'foto')


@require_safe
def miniatura_publica(request, onibus_id):
    return _servir_imagem(onibus_id, 'miniatura')
