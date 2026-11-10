import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rotas", "0008_remove_ponto_latitude_remove_ponto_longitude_and_more")]

    operations = [
        migrations.RemoveIndex(
            model_name="localizacaoviagem", name="loc_viagem_captura_idx"
        ),
        migrations.AlterField(
            model_name="localizacaoviagem",
            name="viagem",
            field=models.ForeignKey(
                db_index=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="localizacoes",
                to="rotas.viagem",
            ),
        ),
    ]
