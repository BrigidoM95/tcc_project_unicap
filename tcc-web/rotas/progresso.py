"""Trajeto observado do ônibus; pontos de embarque não têm coordenadas."""
from math import ceil


def progresso(viagem, pontos=None, sentido=None):
    locais = list(viagem.localizacoes.order_by('capturada_em','pk'))
    amostra = locais[::max(1, ceil(len(locais)/400))]
    if locais and (not amostra or amostra[-1].pk != locais[-1].pk):
        amostra.append(locais[-1])
    return {'proximo_ponto':None, 'previsao_chegada':None, 'previsao_metodo':None,
        'passagens':{}, 'trajeto_percorrido':[{'latitude':float(p.latitude),
        'longitude':float(p.longitude), 'capturada_em':p.capturada_em.isoformat()} for p in amostra]}
