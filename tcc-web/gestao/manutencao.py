"""Retenção diária, executada pelo mesmo serviço que mantém a operação."""
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from rotas.models import LocalizacaoViagem
from .models import LogAuditoria


def excluir_em_lotes(consulta):
    """Limita memória e duração das transações mesmo com sinais de auditoria."""
    removidos = 0
    while ids := list(consulta.order_by('pk').values_list('pk', flat=True)[:1000]):
        total, _ = consulta.filter(pk__in=ids).delete()
        removidos += total
    return removidos


def manutencao_diaria(*, agora=None, forcar=False):
    agora = agora or timezone.now()
    dia = timezone.localdate(agora).isoformat()
    concluida = f'manutencao:concluida:{dia}'
    if not forcar and cache.get(concluida):
        return None
    # Impede duas instâncias do serviço de executar a mesma limpeza juntas.
    bloqueio = 'manutencao:executando'
    if not cache.add(bloqueio, True, timeout=3600):
        return None
    try:
        resultado = {
            'gps': excluir_em_lotes(LocalizacaoViagem.objects.filter(
                capturada_em__lt=agora-timedelta(days=settings.RETENCAO_GPS_DIAS))),
            'auditoria': excluir_em_lotes(LogAuditoria.objects.filter(
                criado_em__lt=agora-timedelta(days=settings.RETENCAO_AUDITORIA_DIAS))),
        }
        saida = StringIO()
        call_command('flushexpiredtokens', stdout=saida)
        call_command('clearsessions', stdout=saida)
        cache.set(concluida, True, timeout=48*60*60)
        return resultado
    finally:
        cache.delete(bloqueio)
