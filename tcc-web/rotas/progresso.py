"""Trajeto observado do ônibus; pontos de embarque não têm coordenadas."""
from math import ceil


def progresso(viagem):
    locais = list(viagem.localizacoes.order_by('capturada_em','pk').values_list('latitude','longitude','capturada_em'))
    amostra = locais[::max(1, ceil(len(locais)/400))]
    if locais and (not amostra or amostra[-1] != locais[-1]):
        amostra.append(locais[-1])
    return {'trajeto_percorrido':[{'latitude':float(lat),
        'longitude':float(lon), 'capturada_em':instante.isoformat()} for lat,lon,instante in amostra]}
