"""Autenticação comum às APIs de operação."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from gestao.auditoria import AuditJWTAuthentication

class BaseViagemApi(APIView):
    authentication_classes=[AuditJWTAuthentication]
    permission_classes=[IsAuthenticated]
