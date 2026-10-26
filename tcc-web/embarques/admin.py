from django.contrib import admin
from .models import CheckIn

@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ('nome_associado', 'rua_associado', 'viagem', 'codigo_onibus', 'registrado_em')
    list_filter = ('viagem', 'registrado_em')
    search_fields = ('nome_associado', 'rua_associado', 'placa_onibus')
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
