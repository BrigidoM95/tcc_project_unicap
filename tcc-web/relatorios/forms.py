from datetime import date

from django import forms
from django.db.models import Q

from onibus.models import Onibus
from rotas.models import PontoEmbarque, Rota, Viagem
from usuarios.models import Usuario


class FiltrosRelatorioForm(forms.Form):
    data_inicial = forms.DateField(
        label="Data inicial", input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    data_final = forms.DateField(
        label="Data final", input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    onibus = forms.ModelChoiceField(
        label="Ônibus", queryset=Onibus.objects.none(), required=False,
        empty_label="Todos os ônibus",
    )
    rota = forms.ModelChoiceField(
        label="Rota", queryset=Rota.objects.none(), required=False,
        empty_label="Todas as rotas",
    )
    associado = forms.ModelChoiceField(
        label="Associado", queryset=Usuario.objects.none(), required=False,
        empty_label="Todos os associados",
    )
    sentido = forms.ChoiceField(
        label="Sentido", choices=[("", "Ida e retorno"), *Viagem.Sentido.choices],
        required=False,
    )
    ponto = forms.ModelChoiceField(
        label="Ponto informado", queryset=PontoEmbarque.objects.none(),
        required=False, empty_label="Todos os pontos",
    )
    sem_ponto = forms.BooleanField(label="Somente embarques sem ponto informado", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Inativos continuam disponíveis para consultar o histórico.
        self.fields["onibus"].queryset = Onibus.objects.all()
        self.fields["rota"].queryset = Rota.objects.all()
        self.fields["associado"].queryset = Usuario.objects.filter(
            Q(tipo=Usuario.Tipo.ASSOCIADO) | Q(checkins__isnull=False)
        ).select_related("user").distinct().order_by("user__first_name", "pk")
        self.fields["associado"].label_from_instance = lambda u: f"{u} ({u.rua or 'sem RUA atual'})"
        self.fields["ponto"].queryset = PontoEmbarque.objects.select_related("rota").order_by(
            "rota__nome", "sentido", "ordem", "pk"
        )
        self.fields["ponto"].label_from_instance = lambda p: f"{p.rota.nome} / {p}"

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("data_inicial"), dados.get("data_final")
        if inicio and fim:
            if fim < inicio:
                self.add_error("data_final", "A data final deve ser igual ou posterior à inicial.")
            elif (fim - inicio).days >= 366:
                self.add_error("data_final", "Selecione um período de até 366 dias.")
            if fim == date.max:
                self.add_error("data_final", "Informe uma data final anterior a 31/12/9999.")
        ponto, rota, sentido = dados.get("ponto"), dados.get("rota"), dados.get("sentido")
        if ponto:
            if dados.get("sem_ponto"):
                self.add_error("ponto", "Escolha um ponto ou a opção sem ponto informado.")
            if rota and ponto.rota_id != rota.pk:
                self.add_error("ponto", "O ponto não pertence à rota selecionada.")
            if sentido and ponto.sentido != sentido:
                self.add_error("ponto", "O ponto não pertence ao sentido selecionado.")
        return dados
