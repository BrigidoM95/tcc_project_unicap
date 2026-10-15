from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from usuarios.models import MatriculaAnual
class Command(BaseCommand):
    help='Encerra matrículas de anos anteriores, preservando o histórico.'
    @transaction.atomic
    def handle(self,*args,**opts):
        n=0
        for m in MatriculaAnual.objects.filter(ano__lt=timezone.localdate().year,ativa=True):
            m.ativa=False;m.save(update_fields=['ativa','atualizada_em']);n+=1
        self.stdout.write(f'{n} matrícula(s) encerrada(s).')
