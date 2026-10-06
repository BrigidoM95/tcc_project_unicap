import re

from django import forms

from usuarios.models import Usuario

from .models import Onibus


class OnibusForm(forms.ModelForm):

    class Meta:
        model = Onibus

        fields = [
            "nome",
            "placa",
            "capacidade",
            "motorista",
            "foto",
            "observacoes",
        ]

        widgets = {
            "nome": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: Ônibus 01",
                }
            ),

            "placa": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: ABC1D23",
                    "maxlength": "8",
                }
            ),

            "capacidade": forms.NumberInput(
                attrs={
                    "min": "1",
                    "max": "46",
                    "placeholder": "Ex.: 46",
                }
            ),

            "observacoes": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": "500",
                    "placeholder": (
                        "Informações adicionais sobre o veículo..."
                    ),
                }
            ),

            "foto": forms.ClearableFileInput(
                attrs={
                    "accept": (
                        ".jpg,.jpeg,.png,.webp,"
                        "image/jpeg,image/png,image/webp"
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        motoristas = Usuario.objects.filter(
            tipo=Usuario.Tipo.MOTORISTA,
            user__is_active=True,
        ).select_related(
            "user"
        ).order_by(
            "user__first_name"
        )

        self.fields["motorista"].queryset = motoristas

        self.fields["motorista"].empty_label = (
            "Selecione um motorista"
        )

        self.fields["nome"].label = "Nome/Identificação"
        self.fields["placa"].label = "Placa"
        self.fields["capacidade"].label = "Capacidade de passageiros"
        self.fields["motorista"].label = "Motorista"
        self.fields["foto"].label = "Foto do ônibus"
        self.fields["observacoes"].label = "Observações"

        for campo in self.fields.values():

            classes = campo.widget.attrs.get(
                "class",
                "",
            )

            campo.widget.attrs["class"] = (
                f"{classes} campo-formulario".strip()
            )

    def clean_placa(self):

        placa = self.cleaned_data.get(
            "placa",
            "",
        )

        placa = re.sub(
            r"[^A-Za-z0-9]",
            "",
            placa,
        ).upper()

        if not re.fullmatch(
            r"[A-Z]{3}[0-9][A-Z0-9][0-9]{2}",
            placa,
        ):
            raise forms.ValidationError(
                "Informe uma placa válida. "
                "Exemplos: ABC1234 ou ABC1D23."
            )

        existentes = Onibus.objects.filter(
            placa=placa
        )

        if self.instance.pk:

            existentes = existentes.exclude(
                pk=self.instance.pk
            )

        if existentes.exists():

            raise forms.ValidationError(
                "Já existe um ônibus cadastrado com esta placa."
            )

        return placa

    def clean_motorista(self):

        motorista = self.cleaned_data.get(
            "motorista"
        )

        if not motorista:
            return motorista

        if motorista.tipo != Usuario.Tipo.MOTORISTA:

            raise forms.ValidationError(
                "O usuário selecionado não é um motorista."
            )

        if not motorista.user.is_active:

            raise forms.ValidationError(
                "O motorista selecionado está inativo."
            )

        return motorista

    def clean_capacidade(self):

        capacidade = self.cleaned_data.get(
            "capacidade"
        )

        if capacidade is None:
            return capacidade

        if capacidade < 1 or capacidade > 46:

            raise forms.ValidationError(
                "A capacidade deve estar entre 1 e 46 passageiros."
            )

        return capacidade

    def clean_foto(self):

        foto = self.cleaned_data.get(
            "foto"
        )

        if not foto:
            return foto

        if hasattr(foto, "size"):

            limite = 5 * 1024 * 1024

            if foto.size > limite:

                raise forms.ValidationError(
                    "A foto deve possuir no máximo 5 MB."
                )

        nome = getattr(
            foto,
            "name",
            "",
        ).lower()

        extensoes = (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
        )

        if nome and not nome.endswith(
            extensoes
        ):

            raise forms.ValidationError(
                "Formato inválido. "
                "Utilize JPG, JPEG, PNG ou WEBP."
            )

        return foto