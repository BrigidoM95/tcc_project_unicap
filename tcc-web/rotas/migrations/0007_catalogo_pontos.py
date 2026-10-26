from django.db import migrations


def converter(apps,schema_editor):
    Ponto=apps.get_model('rotas','Ponto');Vinculo=apps.get_model('rotas','PontoEmbarque')
    for v in Vinculo.objects.order_by('pk'):
        nome=v.nome
        p=Ponto.objects.filter(nome=nome).first()
        if p and (p.endereco,p.latitude,p.longitude)!=(v.endereco,v.latitude,v.longitude):
            nome=f'{v.nome[:80]} (ponto {v.pk})'
        p,_=Ponto.objects.get_or_create(nome=nome,defaults={'endereco':v.endereco,'latitude':v.latitude,'longitude':v.longitude})
        Vinculo.objects.filter(pk=v.pk).update(ponto=p)


class Migration(migrations.Migration):
    dependencies=[('rotas','0006_ponto_remove_viagem_viagem_status_fim_coerentes_and_more')]
    operations=[migrations.RunPython(converter,migrations.RunPython.noop)]
