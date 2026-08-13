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