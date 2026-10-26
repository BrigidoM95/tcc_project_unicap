from django.db import migrations


def converter(apps, schema_editor):
    Usuario=apps.get_model('usuarios','Usuario')
    ocupadas=set(Usuario.objects.exclude(rua__isnull=True).values_list('rua',flat=True))
    for p in Usuario.objects.order_by('pk'):
        if p.rua and p.rua.startswith('802.'):
            continue
        n=p.pk
        while f'802.{n:03d}' in ocupadas:n+=1
        novo=f'802.{n:03d}'
        Usuario.objects.filter(pk=p.pk).update(rua_anterior=p.rua or '',rua=novo)
        ocupadas.add(novo)


class Migration(migrations.Migration):
    dependencies=[('usuarios','0005_matriculaanual_atualizada_por_and_more')]
    operations=[migrations.RunPython(converter,migrations.RunPython.noop)]
