from django.db import migrations


def exigir_tabela_vazia(apps, schema_editor):
    pagina = apps.get_model("paginas", "Pagina")
    if pagina.objects.using(schema_editor.connection.alias).exists():
        raise RuntimeError(
            "A tabela legada paginas_pagina contém registros. "
            "Revise e preserve esses dados antes de remover o modelo sem uso."
        )


class Migration(migrations.Migration):
    dependencies = [("paginas", "0001_initial")]

    operations = [
        migrations.RunPython(exigir_tabela_vazia, migrations.RunPython.noop),
        migrations.DeleteModel(name="Pagina"),
    ]
