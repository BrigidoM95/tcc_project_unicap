from django.contrib.auth.forms import AuthenticationForm


class LoginForm(AuthenticationForm):
    username_label = 'E-mail'

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields['username'].label = self.username_label
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'placeholder': 'Email',
        })
        self.fields['password'].widget.attrs.update({
            'autocomplete': 'current-password',
            'placeholder': 'Senha',
        })
