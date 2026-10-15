import uuid
from django.db import models

class SessaoEmbarque(models.Model):
    viagem = models.OneToOneField('rotas.Viagem', on_delete=models.PROTECT, related_name='sessao_embarque')
    fiscal = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    codigo_curto = models.CharField(max_length=6, unique=True, null=True, blank=True, editable=False)
    expira_em = models.DateTimeField()
    ponto = models.ForeignKey('rotas.PontoEmbarque', null=True, blank=True,
                              on_delete=models.PROTECT, related_name='+')
    nome_ponto = models.CharField(max_length=100, blank=True)

class CheckIn(models.Model):
    viagem = models.ForeignKey('rotas.Viagem', on_delete=models.PROTECT, related_name='checkins')
    associado = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT, related_name='checkins')
    fiscal = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT, related_name='embarques_validados')
    registrado_em = models.DateTimeField(auto_now_add=True)
    vaga = models.PositiveSmallIntegerField()
    ponto = models.ForeignKey('rotas.PontoEmbarque', null=True, blank=True,
                              on_delete=models.PROTECT, related_name='checkins')
    nome_ponto = models.CharField(max_length=100, blank=True)
    nome_associado = models.CharField(max_length=150)
    rua_associado = models.CharField(max_length=20)
    placa_onibus = models.CharField(max_length=7)
    codigo_onibus = models.CharField(max_length=20)

    class Meta:
        ordering = ['-registrado_em', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['viagem', 'associado'], name='embarque_associado_viagem_unico'),
            models.UniqueConstraint(fields=['viagem', 'vaga'], name='embarque_vaga_viagem_unica'),
            models.CheckConstraint(condition=models.Q(vaga__gte=1), name='embarque_vaga_positiva'),
        ]
