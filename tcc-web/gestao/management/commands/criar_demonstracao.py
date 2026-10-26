"""Dados fictícios, apenas em um banco vazio de desenvolvimento."""
import getpass
import os
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from usuarios.models import Usuario, Instituicao, Curso
from onibus.models import Onibus
from rotas.models import Rota, PontoEmbarque,Ponto
from gestao.models import Despesa
class Command(BaseCommand):
    help='Cria quatro perfis fictícios em banco vazio (DEBUG=true). Solicita uma senha.'
    @transaction.atomic
    def handle(self,*args,**opts):
        if not settings.DEBUG: raise CommandError('Demonstração permitida somente com DEBUG=true.')
        User=get_user_model()
        if User.objects.exists(): raise CommandError('Use um banco vazio. Este comando não altera cadastros existentes.')
        senha=os.getenv('UNICAP_DEMO_PASSWORD') or getpass.getpass('Senha dos usuários de demonstração: ')
        try: validate_password(senha)
        except ValidationError as e: raise CommandError(' '.join(e.messages))
        i=Instituicao.objects.create(nome='Universidade de Demonstração')
        c=Curso.objects.create(instituicao=i,nome='Sistemas de Informação')
        perfis={}
        for tipo in ['administrador','motorista','fiscal','associado']:
            user=User.objects.create_user(f'{tipo}@demo.unicap',f'{tipo}@demo.unicap',senha,
                first_name=tipo.capitalize()+' Demonstração',is_staff=tipo=='administrador',is_superuser=tipo=='administrador')
            perfis[tipo]=Usuario.objects.create(user=user,tipo=tipo,telefone='67999990000',curso=c if tipo in ('associado','fiscal') else None)
        bus=Onibus(nome='Veículo de demonstração',placa='DEM1A23',capacidade=46,motorista=perfis['motorista'])
        foto=Path(__file__).resolve().parents[4]/'assets/onibusAzul.png'
        if foto.exists(): bus.foto.save('demonstracao.png',ContentFile(foto.read_bytes()),save=False)
        bus.save()
        r=Rota.objects.create(nome='Rota de demonstração',destino='Campus',onibus=bus,horario_ida='18:00',horario_retorno='22:30',fiscal=perfis['fiscal'])
        r.instituicoes.add(i)
        for sentido in ['ida','retorno']:
            for ordem,nome in enumerate(['Ponto demonstrativo A','Ponto demonstrativo B'],1):
                p,_=Ponto.objects.get_or_create(nome=nome,defaults={'endereco':'Endereço de demonstração'})
                PontoEmbarque.objects.create(rota=r,ponto=p,nome=nome,endereco='Endereço de demonstração',sentido=sentido,ordem=ordem)
        Despesa.objects.create(onibus=bus,data=timezone.localdate(),categoria='combustivel',descricao='Despesa fictícia de demonstração',valor='250.00')
        self.stdout.write(self.style.SUCCESS('Demonstração criada. Nenhum embarque ou GPS real foi gerado.'))
        for tipo in perfis:self.stdout.write(f'{tipo}@demo.unicap')
