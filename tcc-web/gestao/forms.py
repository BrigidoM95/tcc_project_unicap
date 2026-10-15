from django import forms
from django.utils import timezone
from usuarios.models import Usuario, Instituicao, Curso, MatriculaAnual
from onibus.models import Onibus
from .models import Despesa

class InstituicaoForm(forms.ModelForm):
    class Meta:
        model = Instituicao
        fields = ['nome','ativa']
class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ['instituicao','nome','ativo']
class MatriculaForm(forms.ModelForm):
    class Meta:
        model = MatriculaAnual
        fields = ['associado','ano','ativa','observacoes']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['associado'].queryset = Usuario.objects.filter(tipo='associado').select_related('user')
        self.fields['ano'].initial = timezone.localdate().year
        if self.instance.pk:
            self.fields['associado'].disabled = True
            self.fields['ano'].disabled = True
    def clean_ano(self):
        v = self.cleaned_data['ano']
        if not 2000 <= v <= timezone.localdate().year + 1:
            raise forms.ValidationError('Informe um ano entre 2000 e o próximo ano.')
        return v
class DespesaForm(forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ['onibus','data','categoria','descricao','valor']
        widgets = {'data':forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'})}
    def clean_data(self):
        v = self.cleaned_data['data']
        if v > timezone.localdate(): raise forms.ValidationError('Registre somente despesas já realizadas.')
        return v
class FiltroDespesas(forms.Form):
    inicio = forms.DateField(label='Data inicial',widget=forms.DateInput(attrs={'type':'date'}))
    fim = forms.DateField(label='Data final',widget=forms.DateInput(attrs={'type':'date'}))
    onibus = forms.ModelChoiceField(label='Ônibus',queryset=Onibus.objects.all(),required=False)
    def clean(self):
        d = super().clean()
        if d.get('inicio') and d.get('fim'):
            if d['inicio'] > d['fim']: raise forms.ValidationError('O início deve ser anterior ao fim.')
            if (d['fim'] - d['inicio']).days > 365: raise forms.ValidationError('Consulte até 366 dias por vez.')
        return d
