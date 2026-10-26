import uuid
from django.db import models
from django.utils import timezone

class SessaoEmbarque(models.Model):
    viagem = models.ForeignKey('rotas.Viagem', on_delete=models.PROTECT, related_name='sessoes_embarque')
    fiscal = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    codigo_curto = models.CharField(max_length=6, unique=True, null=True, blank=True, editable=False)
    sentido = models.CharField(max_length=10, default='ida')
    data_servico = models.DateField(null=True)
    gerado_em = models.DateTimeField(default=timezone.now)
    expira_em = models.DateTimeField()
    ponto = models.ForeignKey('rotas.PontoEmbarque', null=True, blank=True,
                              on_delete=models.PROTECT, related_name='+')
    nome_ponto = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['viagem','fiscal','sentido','data_servico'],name='qr_fiscal_viagem_sentido_dia_unico')]

class CheckIn(models.Model):
    def get_sentido_display(self):
        return 'Volta' if self.sentido=='retorno' else 'Ida'

    legado = models.BooleanField(default=False, editable=False)
    sentido = models.CharField(max_length=10, default='ida')
    data_servico = models.DateField(null=True, db_index=True)
    lido_em = models.DateTimeField(null=True, blank=True)
    origem = models.CharField(max_length=10, default='qr', choices=[('qr','QR'),('manual','Manual'),('fiscal','Fiscal')])
    sincronizado_offline = models.BooleanField(default=False)
    motivo = models.CharField(max_length=300, blank=True)
    cancelado_em = models.DateTimeField(null=True, blank=True)
    motivo_cancelamento = models.CharField(max_length=300, blank=True)

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
            models.UniqueConstraint(fields=['associado', 'sentido', 'data_servico'], condition=models.Q(cancelado_em__isnull=True, legado=False), name='embarque_associado_sentido_dia_unico'),
            models.UniqueConstraint(fields=['viagem', 'sentido', 'vaga'], condition=models.Q(cancelado_em__isnull=True), name='embarque_poltrona_sentido_unico'),
            models.CheckConstraint(condition=models.Q(vaga__gte=1), name='embarque_vaga_positiva'),
        ]


class ReservaAssento(models.Model):
    class Trajeto(models.TextChoices):
        IDA = 'ida', 'Só ida'
        VOLTA = 'volta', 'Só volta'
        IDA_VOLTA = 'ida_volta', 'Ida e volta'

    trajeto = models.CharField(max_length=10, choices=Trajeto.choices, default=Trajeto.IDA)
    ponto = models.ForeignKey('rotas.PontoEmbarque', null=True, blank=True,
                              on_delete=models.PROTECT, related_name='reservas')
    viagem = models.ForeignKey('rotas.Viagem', on_delete=models.PROTECT, related_name='reservas')
    associado = models.ForeignKey('usuarios.Usuario', on_delete=models.PROTECT, related_name='reservas')
    sentido = models.CharField(max_length=10)
    assento = models.PositiveSmallIntegerField()
    criada_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    ativa = models.BooleanField(default=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['viagem','sentido','assento'], condition=models.Q(ativa=True), name='reserva_poltrona_unica'),
            models.UniqueConstraint(fields=['viagem','sentido','associado'], condition=models.Q(ativa=True), name='reserva_associado_unica'),
            models.CheckConstraint(condition=models.Q(assento__gte=1,assento__lte=46), name='reserva_poltrona_valida'),
        ]
