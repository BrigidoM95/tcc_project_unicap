from django.http import JsonResponse
from django.db import connection
from django.views.decorators.http import require_GET
@require_GET
def health(request):
    try:
        with connection.cursor() as c: c.execute('SELECT 1');c.fetchone()
    except Exception:
        return JsonResponse({'status':'indisponivel'},status=503)
    return JsonResponse({'status':'ok'})
