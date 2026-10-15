import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from .models import Usuario, Curso
User = get_user_model()

class LoginForm(AuthenticationForm):
    pass

class DadosUsuarioForm(forms.Form):
    nome = forms.CharField(max_length=150,label='Nome')
    email = forms.EmailField(label='E-mail')
    telefone = forms.CharField(max_length=20,label='Telefone')
    tipo = forms.ChoiceField(choices=Usuario.Tipo.choices,label='Tipo de usuário')
    curso = forms.ModelChoiceField(queryset=Curso.objects.none(),required=False,label='Instituição / curso')
    def __init__(self,*args,usuario=None,ator=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.usuario = usuario
        self.ator = ator
        qs = Q(ativo=True,instituicao__ativa=True)
        if usuario and usuario.curso_id: qs |= Q(pk=usuario.curso_id)
        self.fields['curso'].queryset = Curso.objects.filter(qs).select_related('instituicao')
        if not ator or not ator.is_superuser:
            self.fields['tipo'].choices = [c for c in Usuario.Tipo.choices if c[0] != Usuario.Tipo.ADMINISTRADOR]
            if usuario and usuario.tipo == Usuario.Tipo.ADMINISTRADOR:
                self.fields['tipo'].choices = [(Usuario.Tipo.ADMINISTRADOR,'Administrador')]
                self.fields['tipo'].disabled = True
        if usuario:
            self.initial.update(nome=usuario.user.first_name,email=usuario.user.email,
                telefone=usuario.telefone,tipo=usuario.tipo,curso=usuario.curso_id)
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
        u.curso = self.cleaned_data.get('curso') if u.tipo == Usuario.Tipo.ASSOCIADO else None
        u.save()
        return u

class CadastroUsuarioForm(DadosUsuarioForm):
    senha1 = forms.CharField(label='Senha inicial',widget=forms.PasswordInput,help_text='Ao menos 8 caracteres. Não use uma senha comum.')
    senha2 = forms.CharField(label='Confirmar senha',widget=forms.PasswordInput)
    def clean(self):
        d = super().clean()
        if d.get('senha1') != d.get('senha2'): self.add_error('senha2','As senhas não coincidem.')
        if d.get('senha1'):
            user = User(username=d.get('email',''),email=d.get('email',''),first_name=d.get('nome',''))
            try: validate_password(d['senha1'],user=user)
            except forms.ValidationError as e: self.add_error('senha1',e)
        return d
    @transaction.atomic
    def save(self):
        user = User.objects.create_user(username=self.cleaned_data['email'],email=self.cleaned_data['email'],
            first_name=self.cleaned_data['nome'],password=self.cleaned_data['senha1'])
        self.salvar_perfil(user)
        return user

class EdicaoUsuarioForm(DadosUsuarioForm):
    @transaction.atomic
    def save(self):
        user = self.usuario.user
        user.first_name = self.cleaned_data['nome']; user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email'];user.save()
        return self.salvar_perfil(user)
