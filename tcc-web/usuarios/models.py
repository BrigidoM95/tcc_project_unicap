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

    senha_definida_em = models.DateTimeField(null=True, blank=True)
    rua_anterior = models.CharField(max_length=20, blank=True, editable=False)

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
        super().save(*args, **kwargs)

        if not self.rua:
            numero=self.pk
            while Usuario.objects.filter(rua=f"802.{numero:03d}").exclude(pk=self.pk).exists(): numero+=1
            self.rua = f"802.{numero:03d}"
            super().save(update_fields=["rua"])

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

