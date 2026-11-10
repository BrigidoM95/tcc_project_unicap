from django.db import migrations


def exigir_codigos_vazios(apps, schema_editor):
    sessao = apps.get_model("embarques", "SessaoEmbarque")
    preenchidas = sessao.objects.using(schema_editor.connection.alias).exclude(
        codigo_curto__isnull=True
    ).exclude(codigo_curto="")
    if preenchidas.exists():
        raise RuntimeError(
            "Há sessões com codigo_curto preenchido. "
            "Revise e preserve esses dados antes de remover o campo sem uso."
        )


class Migration(migrations.Migration):
    dependencies = [("embarques", "0006_reservaassento_ponto_reservaassento_trajeto")]

    operations = [
        migrations.RunPython(exigir_codigos_vazios, migrations.RunPython.noop),
        migrations.RemoveField(model_name="sessaoembarque", name="codigo_curto"),
    ]
