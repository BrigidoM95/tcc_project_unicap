from django.db import migrations
from django.utils import timezone

def iniciar(apps,schema_editor):
    Usuario=apps.get_model('usuarios','Usuario')
    Matricula=apps.get_model('usuarios','MatriculaAnual')
    for usuario in Usuario.objects.filter(tipo='associado').select_related('user').iterator():
        Matricula.objects.get_or_create(associado_id=usuario.pk,ano=timezone.localdate().year,
            defaults={'ativa':usuario.user.is_active,'origem':'migracao',
                      'observacoes':'Registro inicial na atualização do sistema; não reconstrói anos anteriores.'})

class Migration(migrations.Migration):
    dependencies=[('usuarios','0003_curso_instituicao_usuario_telefone_usuario_curso_and_more')]
    operations=[migrations.RunPython(iniciar,migrations.RunPython.noop)]
