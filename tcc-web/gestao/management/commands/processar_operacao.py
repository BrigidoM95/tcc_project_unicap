import time
from django.core.management.base import BaseCommand
from rotas.operacao import encerrar_antigas, gerar_viagens
from django.utils import timezone


class Command(BaseCommand):
    help='Gera viagens do dia e encerra as esquecidas às 03:00. Use --continuo no serviço de operação.'
    def add_arguments(self,parser):parser.add_argument('--continuo',action='store_true')
    def handle(self,*args,**options):
        while True:
            encerradas=encerrar_antigas();criadas=gerar_viagens()
            if encerradas or criadas or not options['continuo']:
                self.stdout.write(f'{criadas} viagens criadas; {encerradas} encerradas para revisão.')
            if not options['continuo']:break
            time.sleep(30)
