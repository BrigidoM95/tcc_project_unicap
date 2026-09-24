from django import forms
from django.db.models import Q

from onibus.models import Onibus
from usuarios.models import Usuario

from .models import Rota, PontoEmbarque


class RotaForm(forms.ModelForm):
    class Meta:
        model = Rota
        fields = [
            "nome",
            "origem",
            "destino",
            "onibus",
            "horario_ida",
            "horario_retorno",
            "observacoes",
        ]
        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Ex.: UNIGRAN — Noturno"}
            ),
            "origem": forms.TextInput(
                attrs={"placeholder": "Ex.: Caarapó"}
            ),
            "destino": forms.TextInput(
                attrs={"placeholder": "Ex.: UNIGRAN — Dourados"}
            ),
            "horario_ida": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time"},
            ),
            "horario_retorno": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time"},
            ),
            "observacoes": forms.Textarea(
                attrs={"rows": 4, "maxlength": "500"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        disponiveis = Q(
            status=Onibus.Status.ATIVO,
            motorista__tipo=Usuario.Tipo.MOTORISTA,
            motorista__user__is_active=True,
        )

        if self.instance.pk and self.instance.onibus_id:
            disponiveis |= Q(pk=self.instance.onibus_id)

        self.fields["onibus"].queryset = (
            Onibus.objects
            .filter(disponiveis)
            .select_related("motorista__user")
            .order_by("codigo")
        )
        self.fields["onibus"].empty_label = "Selecione um ônibus"
        self.fields["onibus"].label_from_instance = (
            lambda obj: f"{obj} — Motorista: {obj.motorista}"
        )
        self.fields["onibus"].help_text = (
            "O motorista responsável acompanha o cadastro do ônibus."
        )

        for nome in ("horario_ida", "horario_retorno"):
            self.fields[nome].input_formats = ["%H:%M", "%H:%M:%S"]

        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo-formulario"

class PontoEmbarqueForm(forms.ModelForm):

    class Meta:
        model = PontoEmbarque

        fields = [
            "nome",
            "endereco",
            "sentido",
            "ordem",
            "latitude",
            "longitude",
        ]

        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Ex.: Praça central"}
            ),
            "endereco": forms.TextInput(
                attrs={"placeholder": "Rua, número ou referência"}
            ),
            "ordem": forms.NumberInput(
                attrs={"min": "1"}
            ),
            "latitude": forms.NumberInput(
                attrs={
                    "step": "0.000001",
                    "min": "-90",
                    "max": "90",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "step": "0.000001",
                    "min": "-180",
                    "max": "180",
                }
            ),
        }

    def __init__(self, *args, rota, **kwargs):
        super().__init__(*args, **kwargs)

        self.instance.rota = rota

        self.fields["ordem"].help_text = (
            "Sequência neste sentido: 1, 2, 3..."
        )

        self.fields["latitude"].help_text = (
            "Opcional. Preencha latitude e longitude juntas."
        )

        for campo in self.fields.values():
            campo.widget.attrs["class"] = "campo-formulario"

    def clean(self):
        dados = super().clean()

        sentido = dados.get("sentido")
        ordem = dados.get("ordem")

        if sentido and ordem is not None:
            existentes = PontoEmbarque.objects.filter(
                rota=self.instance.rota,
                sentido=sentido,
                ordem=ordem,
            )

            if self.instance.pk:
                existentes = existentes.exclude(
                    pk=self.instance.pk
                )

            if existentes.exists():
                self.add_error(
                    "ordem",
                    "Já existe um ponto nessa posição "
                    "para este sentido da rota.",
                )

        return dados