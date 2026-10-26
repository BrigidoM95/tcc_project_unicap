from django import forms
from django.utils import timezone
from usuarios.models import Usuario, Instituicao, Curso
from onibus.models import Onibus
from .models import Despesa
from rotas.models import Ponto

def normalizar_nome(nome):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD',nome.strip().casefold()) if not unicodedata.combining(c))

class CadastroForm(forms.ModelForm):
    def clean(self):
        dados=super().clean()
        nome=dados.get('nome')
        if nome:
            qs=self._meta.model.objects.exclude(pk=self.instance.pk)
            if isinstance(self.instance,Curso) and dados.get('instituicao'):qs=qs.filter(instituicao=dados['instituicao'])
            if any(normalizar_nome(x)==normalizar_nome(nome) for x in qs.values_list('nome',flat=True)):
                self.add_error('nome','Já existe um cadastro com este nome, inclusive sem acentos ou com outras maiúsculas.')
        if self.instance.pk:
            if isinstance(self.instance,Ponto) and self.changed_data and self.instance.vinculos.filter(rota__viagens__status='em_andamento').exists():
                raise forms.ValidationError('Há uma viagem usando este ponto. Aguarde o encerramento para editar.')
            campo='ativa' if isinstance(self.instance,Instituicao) else 'ativo'
            if dados.get(campo) is False:
                from rotas.models import Rota,PontoEmbarque
                em_uso=(Rota.objects.filter(instituicoes=self.instance,status='ativa').exists() if isinstance(self.instance,Instituicao) else PontoEmbarque.objects.filter(ponto=self.instance,ativo=True,rota__status='ativa').exists() if isinstance(self.instance,Ponto) else False)
                if em_uso:self.add_error(campo,'Este cadastro está vinculado a uma rota ativa.')
        return dados

class InstituicaoForm(CadastroForm):
    class Meta:
        model = Instituicao
        fields = ['nome','ativa']
class CursoForm(CadastroForm):
    class Meta:
        model = Curso
        fields = ['instituicao','nome','ativo']
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


class PontoForm(CadastroForm):
    class Meta:
        model = Ponto
        fields = ['nome','endereco','ativo']
