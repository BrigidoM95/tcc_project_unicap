import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from .models import Usuario, Instituicao, Curso
User = get_user_model()

class LoginForm(AuthenticationForm):
    pass

class DadosUsuarioForm(forms.Form):
    nome = forms.CharField(max_length=150,label='Nome')
    email = forms.EmailField(label='E-mail')
    telefone = forms.CharField(max_length=20,label='Telefone')
    tipo = forms.ChoiceField(choices=Usuario.Tipo.choices,label='Tipo de usuário')
    instituicao = forms.ModelChoiceField(
        queryset=Instituicao.objects.none(), required=False, label='Instituição',
        empty_label='Selecione a instituição', help_text='Obrigatória para associados.')
    curso = forms.ModelChoiceField(
        queryset=Curso.objects.none(), required=False, label='Curso',
        empty_label='Selecione o curso', help_text='Selecione um curso da instituição escolhida.')
    def __init__(self,*args,usuario=None,ator=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.usuario = usuario
        self.ator = ator
        qs = Q(ativo=True,instituicao__ativa=True)
        instituicoes = Q(ativa=True)
        if usuario and usuario.curso_id:
            qs |= Q(pk=usuario.curso_id)
            instituicoes |= Q(pk=usuario.curso.instituicao_id)
        self.fields['curso'].queryset = Curso.objects.filter(qs).select_related('instituicao')
        self.fields['instituicao'].queryset = Instituicao.objects.filter(instituicoes)
        self.cursos_disponiveis = list(self.fields['curso'].queryset.values('id', 'nome', 'instituicao_id'))
        if not ator or not ator.is_superuser:
            self.fields['tipo'].choices = [c for c in Usuario.Tipo.choices if c[0] != Usuario.Tipo.ADMINISTRADOR]
            if usuario and usuario.tipo == Usuario.Tipo.ADMINISTRADOR:
                self.fields['tipo'].choices = [(Usuario.Tipo.ADMINISTRADOR,'Administrador')]
                self.fields['tipo'].disabled = True
        if usuario:
            self.initial.update(nome=usuario.user.first_name,email=usuario.user.email,
                telefone=usuario.telefone,tipo=usuario.tipo,curso=usuario.curso_id,
                instituicao=usuario.curso.instituicao_id if usuario.curso_id else None)
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        qs = User.objects.filter(Q(username__iexact=email)|Q(email__iexact=email))
        if self.usuario: qs = qs.exclude(pk=self.usuario.user_id)
        if qs.exists(): raise forms.ValidationError('Já existe um usuário com este e-mail.')
        return email
    def clean_telefone(self):
        v = re.sub(r'[^0-9]','',self.cleaned_data['telefone'])
        if not 10 <= len(v) <= 13: raise forms.ValidationError('Informe telefone com DDD (10 a 13 dígitos).')
        return v
    def clean(self):
        d = super().clean()
        instituicao, curso = d.get('instituicao'), d.get('curso')
        vinculo_academico = d.get('tipo') in (Usuario.Tipo.ASSOCIADO, Usuario.Tipo.FISCAL)
        if vinculo_academico:
            if (d.get('tipo') == Usuario.Tipo.ASSOCIADO or curso) and not instituicao and 'instituicao' not in self.errors:
                self.add_error('instituicao', 'Selecione a instituição do usuário.')
            if (d.get('tipo') == Usuario.Tipo.ASSOCIADO or instituicao) and not curso and 'curso' not in self.errors:
                mensagem = 'Selecione o curso do usuário.'
                if instituicao and not self.fields['curso'].queryset.filter(instituicao=instituicao).exists():
                    mensagem = 'Esta instituição ainda não tem cursos ativos. Cadastre um curso em Gestão > Cursos antes de vincular o usuário.'
                self.add_error('curso', mensagem)
        if instituicao and curso and curso.instituicao_id != instituicao.pk:
            self.add_error('curso', 'Selecione um curso pertencente à instituição escolhida.')
        if self.usuario:
            tipo = d.get('tipo')
            if self.ator and self.ator.pk == self.usuario.user_id and tipo != self.usuario.tipo:
                self.add_error('tipo','Você não pode alterar seu próprio perfil aqui.')
            if self.usuario.tipo == Usuario.Tipo.MOTORISTA and tipo != self.usuario.tipo:
                if self.usuario.onibus.filter(status='ativo').exists() or self.usuario.viagens.filter(status='em_andamento').exists():
                    self.add_error('tipo','Reatribua os ônibus e finalize as viagens antes de alterar o perfil do motorista.')
        return d
    def salvar_perfil(self,user):
        u = self.usuario or Usuario(user=user)
        u.tipo = self.cleaned_data['tipo']; u.telefone = self.cleaned_data['telefone']
        u.curso = self.cleaned_data.get('curso') if u.tipo in (Usuario.Tipo.ASSOCIADO, Usuario.Tipo.FISCAL) else None
        u.save()
        return u

class CadastroUsuarioForm(DadosUsuarioForm):
    @transaction.atomic
    def save(self):
        from .seguranca import gerar_senha_acesso
        self.senha_gerada = gerar_senha_acesso()
        user = User.objects.create_user(username=self.cleaned_data['email'], email=self.cleaned_data['email'],
            first_name=self.cleaned_data['nome'], password=self.senha_gerada)
        p = self.salvar_perfil(user)
        return user

class EdicaoUsuarioForm(DadosUsuarioForm):
    @transaction.atomic
    def save(self):
        user = self.usuario.user
        user.first_name = self.cleaned_data['nome']; user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email'];user.save()
        return self.salvar_perfil(user)
