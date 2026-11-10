from django.db import migrations


def exigir_tabela_vazia(apps, schema_editor):
    associado = apps.get_model("associados", "Associado")
    if associado.objects.using(schema_editor.connection.alias).exists():
        raise RuntimeError(
            "A tabela legada associados_associado contém registros. "
            "Revise e preserve esses dados antes de remover o modelo sem uso."
        )


class Migration(migrations.Migration):
    dependencies = [("associados", "0001_initial")]

    operations = [
        migrations.RunPython(exigir_tabela_vazia, migrations.RunPython.noop),
        migrations.DeleteModel(name="Associado"),
    ]
