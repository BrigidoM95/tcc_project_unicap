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
    else
        echo "Falha no backup: $stamp" >&2
        rm -f "/backups/$stamp.dump.tmp"
    fi
    sleep 86400
done
