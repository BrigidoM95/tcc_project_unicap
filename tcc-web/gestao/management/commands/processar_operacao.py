import time
from django.core.management.base import BaseCommand
from gestao.manutencao import manutencao_diaria
from rotas.operacao import encerrar_antigas, gerar_viagens


class Command(BaseCommand):
    help='Mantém as viagens a cada 30s e executa retenção, limpeza de sessões e tokens diariamente.'
    def add_arguments(self,parser):
        parser.add_argument('--continuo',action='store_true')
        parser.add_argument('--somente-manutencao',action='store_true')
        parser.add_argument('--forcar-manutencao',action='store_true')
    def handle(self,*args,**options):
        while True:
            if not options['somente_manutencao']:
                encerradas=encerrar_antigas();criadas=gerar_viagens()
                if encerradas or criadas or not options['continuo']:
                    self.stdout.write(f'{criadas} viagens criadas; {encerradas} encerradas para revisão.')
            try:
                resultado=manutencao_diaria(forcar=options['forcar_manutencao'])
                if resultado is not None:
                    self.stdout.write(f"Manutenção diária: {resultado['gps']} posições GPS e "
                                      f"{resultado['auditoria']} registros de auditoria expirados removidos; "
                                      'sessões e tokens expirados limpos.')
            except Exception as erro:
                if not options['continuo']:raise
                self.stderr.write(f'Manutenção não concluída; nova tentativa no próximo ciclo: {erro}')
            if not options['continuo'] or options['somente_manutencao']:break
            options['forcar_manutencao']=False
            time.sleep(30)
