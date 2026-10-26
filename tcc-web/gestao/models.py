from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


from django.db.models import Q

class Despesa(models.Model):
    class Categoria(models.TextChoices):
        COMBUSTIVEL = 'combustivel', 'Combustível'
        MANUTENCAO = 'manutencao', 'Manutenção'
        SEGURO = 'seguro', 'Seguro'
        OUTRA = 'outra', 'Outra'
    onibus = models.ForeignKey('onibus.Onibus', on_delete=models.PROTECT, related_name='despesas')
    data = models.DateField()
    categoria = models.CharField(max_length=20, choices=Categoria.choices)
    descricao = models.CharField('Descrição', max_length=200)
    valor = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    cancelada = models.BooleanField(default=False, editable=False)
    motivo_cancelamento = models.CharField(max_length=200, blank=True, editable=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-data','-pk']
        constraints = [models.CheckConstraint(condition=Q(valor__gt=0),name='despesa_valor_positivo')]
    def __str__(self): return f'{self.data}: {self.descricao}'

class LogAuditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    acao = models.CharField('Ação', max_length=40)
    modelo = models.CharField(max_length=100, blank=True)
    objeto_id = models.CharField(max_length=40, blank=True)
    detalhes = models.JSONField(default=dict)
    ip = models.GenericIPAddressField(null=True, blank=True)
    descricao = models.CharField(max_length=300, blank=True)
    class Meta:
        ordering = ['-criado_em','-pk']

class CacheEntry(models.Model):
    # Formato utilizado pelo DatabaseCache do Django; criado por migration.
    cache_key = models.CharField(max_length=255, primary_key=True)
    value = models.TextField()
    expires = models.DateTimeField(db_index=True)
    class Meta:
        db_table = 'unicap_cache'
