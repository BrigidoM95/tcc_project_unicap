from django.contrib import admin
from .models import Despesa, LogAuditoria
@admin.register(LogAuditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('criado_em','usuario','acao','modelo','objeto_id')
    list_filter = ('acao','modelo')
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
