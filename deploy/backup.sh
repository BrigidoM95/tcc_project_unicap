#!/bin/sh
set -eu
umask 077
mkdir -p /backups
while true; do
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    if pg_dump --format=custom --file="/backups/$stamp.dump.tmp"; then
        mv "/backups/$stamp.dump.tmp" "/backups/$stamp.dump"
        tar -czf "/backups/$stamp-media.tar.gz" -C /media .
        echo "Backup concluído: $stamp"
        # Somente backups completos com mais de 30 dias, neste diretório dedicado.
        find /backups -maxdepth 1 -type f \( -name '*.dump' -o -name '*-media.tar.gz' \) -mtime +30 -delete
        month=$(date -u +%Y-%m)
        if [ ! -f "/backups/restauracao-$month.ok" ]; then
            restore_db="unicap_restore_$(date -u +%Y%m%d%H%M%S)"
            if createdb "$restore_db"; then
                if pg_restore --exit-on-error --no-owner --no-privileges -d "$restore_db" "/backups/$stamp.dump"; then
                    if psql -v ON_ERROR_STOP=1 -d "$restore_db" -Atc 'SELECT count(*) FROM django_migrations' > "/backups/restauracao-$month.tmp"; then
                        mv "/backups/restauracao-$month.tmp" "/backups/restauracao-$month.ok"
                        echo "Restauração mensal verificada em banco separado: $restore_db"
                    else
                        rm -f "/backups/restauracao-$month.tmp"
                        echo "Falha na verificação do banco restaurado: $restore_db" >&2
                    fi
                else
                    echo "Falha na restauração mensal; verificar backup $stamp" >&2
                fi
                dropdb "$restore_db"
            else
                echo "Sem permissão para criar banco temporário de restauração." >&2
            fi
        fi
    else
        echo "Falha no backup: $stamp" >&2
        rm -f "/backups/$stamp.dump.tmp"
    fi
    sleep 86400
done
