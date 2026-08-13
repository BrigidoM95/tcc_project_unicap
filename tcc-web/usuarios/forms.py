from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth import get_user_model
from .models import Usuario

User = get_user_model()

class LoginForm(AuthenticationForm):
    pass

class CadastroUsuarioForm(forms.Form):
    nome = forms.CharField(
        max_length=150,
        label="Nome"
    )

    email = forms.EmailField(
    label="E-mail"
    )

    tipo = forms.ChoiceField(
    choices=[
        (Usuario.Tipo.ASSOCIADO, "Associado"),
        (Usuario.Tipo.FISCAL, "Fiscal"),
        (Usuario.Tipo.MOTORISTA, "Motorista"),
    ],
    label="Tipo de usuário",
    )

    senha1 = forms.CharField(
    label="Senha",
    widget=forms.PasswordInput,
    )

    senha2 = forms.CharField(
    label="Confirmar senha",
    widget=forms.PasswordInput,
    )

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("Já existe um usuário cadastrado com este e-mail.")
        return email

    def clean(self): 
        cleaned_data = super().clean()
        senha1 = cleaned_data.get("senha1")
        senha2 = cleaned_data.get("senha2")
        if senha1 and senha2 and senha1 != senha2:
            self.add_error("senha2", "As senhas não coincidem.")
        return cleaned_data

    def save(self):
        nome = self.cleaned_data["nome"]
        email = self.cleaned_data["email"]
        tipo = self.cleaned_data["tipo"]
        senha = self.cleaned_data["senha1"]

        user = User.objects.create_user(
            username=email,
            email=email,
            password=senha,
            first_name=nome,
        )

        Usuario.objects.create(
            user=user,
            tipo=tipo,
        )

        return user