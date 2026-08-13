from django.db import models
from django.conf import settings


class Usuario(models.Model):

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

        super().save(*args, **kwargs)

        if self.tipo == self.Tipo.ASSOCIADO and not self.rua:
            self.rua = f"RUA{self.pk:06d}"
            super().save(update_fields=["rua"])