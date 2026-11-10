from django import forms
from django.db.models import Q

from onibus.models import Onibus
from usuarios.models import Usuario

from .models import Rota, PontoEmbarque, Ponto


class RotaForm(forms.ModelForm):
    pontos_ida = forms.ModelMultipleChoiceField(queryset=Ponto.objects.filter(ativo=True), label='Pontos de embarque (ida)', widget=forms.CheckboxSelectMultiple)
    pontos_retorno = forms.ModelMultipleChoiceField(queryset=Ponto.objects.filter(ativo=True), label='Pontos de desembarque / embarque da volta', widget=forms.CheckboxSelectMultiple)
    dias_operacao = forms.MultipleChoiceField(choices=[(str(i), n) for i,n in enumerate(['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo'])], widget=forms.CheckboxSelectMultiple)
    class Meta:
        model = Rota
        fields = [
            "nome",
            "destino",
            "onibus",
            "fiscal",
            "instituicoes",
            "dias_operacao",
            "horario_ida",
            "horario_retorno",
            "observacoes",
        ]
        widgets = {
            "nome": forms.TextInput(
                attrs={"placeholder": "Ex.: UNIGRAN — Noturno"}
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
        self.fields['fiscal'].queryset = Usuario.objects.filter(tipo='fiscal',user__is_active=True).select_related('user')
        self.fields['instituicoes'].queryset = self.fields['instituicoes'].queryset.filter(ativa=True)
        self.fields['instituicoes'].required = True
        if self.instance.pk:
            for sentido, nome in [('ida','pontos_ida'),('retorno','pontos_retorno')]:
                self.initial[nome] = list(self.instance.pontos.filter(sentido=sentido,ativo=True).values_list('ponto_id',flat=True))
            self.initial['dias_operacao'] = [str(i) for i in self.instance.dias_operacao or range(7)]
        else:
            self.initial['dias_operacao'] = ['0','1','2','3','4']

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

    def clean_dias_operacao(self):
        return [int(x) for x in self.cleaned_data['dias_operacao']]

    def clean(self):
        d=super().clean()
        if self.instance.pk and self.instance.viagens.filter(status='em_andamento').exists() and self.changed_data:
            raise forms.ValidationError('Finalize a viagem antes de editar a rota. Para substituição, use Operação das viagens.')
        return d

    def save(self, commit=True):
        from django.db import transaction
        if not commit: return super().save(commit=False)
        with transaction.atomic():
            rota=super().save()
            # Mantém identidade e ordem dos vínculos históricos. Remoções podem
            # deixar intervalos na numeração, sem regravar/reordenar outros pontos.
            for sentido,campo in [('ida','pontos_ida'),('retorno','pontos_retorno')]:
                existentes=list(rota.pontos.filter(sentido=sentido).order_by('ordem'))
                selecionados=list(self.cleaned_data[campo])
                por_ponto={}
                for vinculo in existentes:
                    por_ponto.setdefault(vinculo.ponto_id,vinculo)
                escolhidos={por_ponto[p.pk].pk for p in selecionados if p.pk in por_ponto}
                for vinculo in existentes:
                    if vinculo.ativo and vinculo.pk not in escolhidos:
                        vinculo.ativo=False;vinculo.save(update_fields=['ativo'])
                proxima_ordem=max((p.ordem for p in existentes),default=0)+1
                for ponto in selecionados:
                    vinculo=por_ponto.get(ponto.pk)
                    if vinculo is None:
                        PontoEmbarque.objects.create(rota=rota,sentido=sentido,ponto=ponto,
                            nome=ponto.nome,endereco=ponto.endereco,ordem=proxima_ordem)
                        proxima_ordem+=1
                        continue
                    alterados=[]
                    for campo,valor in [('nome',ponto.nome),('endereco',ponto.endereco),('ativo',True)]:
                        if getattr(vinculo,campo)!=valor:
                            setattr(vinculo,campo,valor);alterados.append(campo)
                    if alterados:vinculo.save(update_fields=alterados)
            return rota

class PontoEmbarqueForm(forms.ModelForm):
    class Meta:
        model=PontoEmbarque
        fields=['ponto','sentido','ordem','ativo']
    def __init__(self,*args,rota,**kwargs):
        super().__init__(*args,**kwargs);self.instance.rota=rota
        self.fields['ponto'].queryset=Ponto.objects.filter(ativo=True)
        self.fields['ponto'].required=True
        self.fields['ordem'].help_text='Sequência de visita neste sentido: 1, 2, 3…'
    def clean(self):
        d=super().clean()
        if self.instance.rota.viagens.filter(status='em_andamento').exists():raise forms.ValidationError('Finalize a viagem antes de alterar seus pontos.')
        if d.get('ordem') and d.get('sentido') and PontoEmbarque.objects.filter(rota=self.instance.rota,sentido=d['sentido'],ordem=d['ordem']).exclude(pk=self.instance.pk).exists():
            self.add_error('ordem','Já existe um ponto nesta posição. Use uma posição livre para reordenar.')
        p=d.get('ponto')
        if p:
            for f in ['nome','endereco']:setattr(self.instance,f,getattr(p,f))
        return d
