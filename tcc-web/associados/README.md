# Histórico do app removido

O cadastro utilizado pelo sistema é `usuarios.Usuario`. O antigo modelo
`associados.Associado` não tinha campos nem funcionalidades.

Para atualizar uma base anterior à limpeza:

1. Faça backup da base antes da atualização.
2. Execute `python manage.py migrate --settings=config.migracao_legada`.
3. A migração `0002_remove_associado_vazio` recusa a remoção se houver registros.
   Nesse caso, preserve e revise os dados antes de prosseguir; não use `--fake`.
4. Execute o servidor com a configuração normal `config.settings`, que já
   mantém `associados` fora de `INSTALLED_APPS`.

Esta pasta mantém apenas o histórico necessário para atualizar outra base antiga
ou reverter a migração, usando essa configuração temporária. Em instalações novas,
com o app fora de `INSTALLED_APPS`, nenhuma tabela de associados é criada.
