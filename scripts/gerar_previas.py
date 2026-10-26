"""Galeria local das capturas de widgets (fixtures, sem dados da base real).

Execute primeiro flutter test --dart-define=CAPTURAR_TELAS=true.
"""
from html import escape
from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont

raiz = Path(__file__).resolve().parents[1]
origem = raiz/'tmp/telas'
destino = raiz/'docs/previas-mobile'
destino.mkdir(parents=True, exist_ok=True)
grupos = {
    'Acesso': ['01-login','15-menu-conta'],
    'Associado': ['02-associado-onibus','03-associado-detalhe','04-associado-poltronas',
        '05-associado-confirmar','06-associado-comprovante','07-associado-lotado',
        '08b-associado-pendente','08-associado-historico','v4-antes-abertura',
        'v4-poltronas-16','v4-poltronas-46','correcao-escolha-salva',
        'correcao-embarque-aberto','correcao-checkin-confirmado','correcao-volta-ida-lotada'],
    'Fiscal': ['09-fiscal-onibus','10-fiscal-painel','11-fiscal-contador','12-fiscal-qr',
        '13b-fiscal-busca','13c-fiscal-manual','13d-fiscal-proprio','13-fiscal-conferencia'],
    'Motorista': ['14-motorista-viagens','motorista-agendada','motorista-embarque_ida',
        'motorista-transito_ida','motorista-confirmacao','motorista-no_destino',
        'motorista-transito_volta','motorista-encerrada'],
}
font=ImageFont.truetype(str(raiz/'assets/fonts/DejaVuSans.ttf'),14)
html=['''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UNICAP — telas implementadas</title><style>
body{font:16px system-ui,sans-serif;background:#f4f6f9;color:#1b396d;margin:0;padding:32px;max-width:1500px;margin:auto}
h1{margin-bottom:8px}p{max-width:900px;line-height:1.6}nav{display:flex;gap:12px;flex-wrap:wrap}nav a{background:#1b396d;color:white;padding:10px 18px;border-radius:9px;text-decoration:none}
.grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:20px}figure{margin:0}img{width:100%;max-width:390px;border:1px solid #cdd5e3;border-radius:16px;box-shadow:0 5px 16px #1b396d15;background:white}figcaption{margin:10px 0 24px;font-size:13px}a{color:inherit}section{scroll-margin-top:20px}
</style><h1>UNICAP — telas implementadas</h1><p>Correções de 26/10/2026. Capturas do Flutter com dados fictícios, feitas nos testes de widgets. Clique para ampliar. O mapa mostra o estado sem localização nesta amostra; na operação usa posições reais. A câmera é simulada pelos testes. A barra de status do aparelho não é simulada.</p><nav>''']
for grupo in grupos:
    html.append(f'<a href="#{grupo}">{grupo}</a>')
html.append('</nav>')
for grupo,nomes in grupos.items():
    html.append(f'<section id="{grupo}"><h2>{grupo}</h2><div class="grade">')
    contato=Image.new('RGB',(3*280,((len(nomes)+2)//3)*650),'#e7ecf3')
    draw=ImageDraw.Draw(contato)
    for i,nome in enumerate(nomes):
        arquivo=origem/(nome+'.png')
        if not arquivo.is_file():
            raise SystemExit(f'Falta captura: {arquivo}')
        shutil.copy2(arquivo,destino/arquivo.name)
        titulo=nome.replace('-',' ').replace('_',' ')
        html.append(f'<figure><a href="{arquivo.name}"><img loading="lazy" src="{arquivo.name}" alt="{escape(titulo)}"></a><figcaption>{escape(titulo)}</figcaption></figure>')
        im=Image.open(arquivo).convert('RGB');im.thumbnail((260,605))
        x=(i%3)*280+10;y=(i//3)*650
        draw.text((x,y+8),titulo,font=font,fill='#1b396d')
        contato.paste(im,(x+(260-im.width)//2,y+35))
    contato.save(destino/(grupo.lower()+'.png'))
    html.append('</div></section>')
html.append('<p>Os nomes e horários são exemplos de teste. As correções, testes e limitações estão descritos em <a href="../CORRECOES_2026-10-26.md">CORRECOES_2026-10-26.md</a>.</p></html>')
(destino/'index.html').write_text(''.join(html),encoding='utf-8')
print(f'Galeria com {sum(map(len,grupos.values()))} capturas: {destino}')
