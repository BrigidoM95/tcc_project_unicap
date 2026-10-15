from django.db import models
from django.conf import settings


class Usuario(models.Model):
    def __str__(self):
        nome = self.user.get_full_name().strip()

        if nome:
            return nome

        if self.user.email:
            return self.user.email

        return self.user.username

    class Tipo(models.TextChoices):
        ADMINISTRADOR = "administrador", "Administrador"
        ASSOCIADO = "associado", "Associado"
        FISCAL = "fiscal", "Fiscal"
        MOTORISTA = "motorista", "Motorista"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )

    telefone = models.CharField(max_length=20, blank=True)
    curso = models.ForeignKey('Curso', null=True, blank=True, on_delete=models.PROTECT)

    rua = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )


    def save(self, *args, **kwargs):
        if self.tipo != self.Tipo.ASSOCIADO:
            self.rua = None

        novo = self._state.adding
        super().save(*args, **kwargs)

        if self.tipo == self.Tipo.ASSOCIADO and not self.rua:
            self.rua = f"RUA{self.pk:06d}"
            super().save(update_fields=["rua"])
        if novo and self.tipo == self.Tipo.ASSOCIADO:
            from django.utils import timezone
            MatriculaAnual.objects.get_or_create(associado=self, ano=timezone.localdate().year,
                defaults={'ativa':self.user.is_active, 'origem':'cadastro'})

class Instituicao(models.Model):
    nome = models.CharField('Nome', max_length=150, unique=True)
    ativa = models.BooleanField(default=True)
    class Meta: ordering = ['nome']
    def __str__(self): return self.nome

class Curso(models.Model):
    instituicao = models.ForeignKey(Instituicao, on_delete=models.PROTECT, verbose_name='Instituição')
    nome = models.CharField(max_length=150)
    ativo = models.BooleanField(default=True)
    class Meta:
        ordering = ['instituicao__nome','nome']
        constraints = [models.UniqueConstraint(fields=['instituicao','nome'],name='curso_instituicao_unico')]
    def __str__(self): return f'{self.instituicao.nome} — {self.nome}'

class MatriculaAnual(models.Model):
    associado = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='matriculas')
    ano = models.PositiveSmallIntegerField()
    ativa = models.BooleanField(default=True)
    instituicao_registrada = models.CharField(max_length=150, blank=True)
    curso_registrado = models.CharField(max_length=150, blank=True)
    observacoes = models.CharField('Observações',max_length=300,blank=True)
    origem = models.CharField(max_length=20,default='renovacao',editable=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-ano','associado_id']
        constraints = [models.UniqueConstraint(fields=['associado','ano'],name='matricula_associado_ano_unica'),
            models.CheckConstraint(condition=models.Q(ano__gte=2000,ano__lte=2200),name='matricula_ano_valido')]
    def save(self,*args,**kwargs):
        if self._state.adding and self.associado.curso_id:
            self.curso_registrado = self.associado.curso.nome
            self.instituicao_registrada = self.associado.curso.instituicao.nome
        super().save(*args,**kwargs)
    def __str__(self): return f'{self.ano} — {self.associado}'
