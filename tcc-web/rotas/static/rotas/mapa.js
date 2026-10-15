/* Leaflet 1.9.4; nenhum token é persistido no navegador. */
(() => {
  'use strict';
  const select = document.getElementById('selecao'), status = document.getElementById('status-mapa');
  const map = L.map('mapa').setView([-22.63, -54.82], 12);
  const layer = L.featureGroup().addTo(map);
  let dados, tiles, ocupado = false, primeira = true, geracao = 0;
  const aviso = txt => { status.textContent = txt; };
  const texto = txt => { const el = document.createElement('span'); el.textContent = txt; return el; };
  async function json(url) {
    const c = new AbortController(), t = setTimeout(() => c.abort(), 15000);
    try { const r = await fetch(url, {credentials:'same-origin',signal:c.signal,headers:{Accept:'application/json'}});
      if (!r.ok) throw new Error(r.status === 403 || r.status === 401 ? 'Sessão expirada. Entre novamente.' : 'Falha ao atualizar. Tente novamente.');
      return await r.json();
    } finally { clearTimeout(t); }
  }
  function enquadrar() { if (layer.getLayers().length) map.fitBounds(layer.getBounds().pad(.2), {maxZoom:16}); }
  async function desenhar() {
    if (!dados) return;
    const versao = ++geracao, valor = select.value;
    let rota, viagem, trajeto = [];
    if (valor.startsWith('v:')) {
      const d = await json('/api/mapa/viagens/' + valor.slice(2) + '/');
      if (versao !== geracao) return;
      ({rota,viagem,trajeto}=d);
    } else rota = dados.rotas.find(r => String(r.id) === valor.slice(2));
    layer.clearLayers();
    document.getElementById('pontos-mapa').replaceChildren();
    if (!rota) {aviso('Nenhuma rota ativa cadastrada.');return;}
    const pontos = rota.pontos.filter(p => !viagem || p.sentido === viagem.sentido);
    for (const sentido of ['ida','retorno']) {
      const caminho = pontos.filter(p=>p.sentido===sentido && p.latitude != null && p.longitude != null);
      if(caminho.length>1) L.polyline(caminho.map(p=>[p.latitude,p.longitude]),{color:'#2b5e97',weight:2,dashArray:'6 7'}).addTo(layer);
    }
    const ul = document.createElement('ul');
    for (const p of pontos) {
      const nome = `${p.ordem}. ${p.nome} (${p.sentido})`;
      const li=document.createElement('li');li.textContent=nome+(p.latitude==null?' — sem coordenadas':'');ul.append(li);
      if(p.latitude!=null && p.longitude!=null) L.circleMarker([p.latitude,p.longitude],{radius:6,color:'#1c3b6e',fillOpacity:.9}).bindPopup(texto(nome)).addTo(layer);
    }
    document.getElementById('pontos-mapa').append(ul);
    if (trajeto.length>1) L.polyline(trajeto.map(p=>[p.latitude,p.longitude]),{color:'#ad4700',weight:4}).addTo(layer);
    let msg = `${rota.nome} · ${rota.origem} → ${rota.destino}`;
    if (viagem) {
      msg += ` · ${viagem.presentes}/${viagem.capacidade} embarques · ${viagem.vagas} vagas`;
      const loc=viagem.localizacao;
      if(loc) {
        const hora = new Date(loc.capturada_em).toLocaleTimeString('pt-BR');
        msg += ` · Último GPS: ${hora}` + (loc.desatualizada ? ' · LOCALIZAÇÃO DESATUALIZADA' : '');
        msg += loc.precisao_metros != null ? ` · Precisão estimada: ${loc.precisao_metros} m` : '';
        L.circleMarker([loc.latitude,loc.longitude],{radius:13,color:loc.desatualizada?'#657386':'#ad4700',fillOpacity:1,weight:3}).bindPopup(texto('Ônibus '+viagem.onibus_codigo+' · '+hora)).addTo(layer);
        if(loc.precisao_metros) L.circle([loc.latitude,loc.longitude],{radius:loc.precisao_metros,color:'#ad4700',weight:1,fillOpacity:.08}).addTo(layer);
      } else msg += ' · Aguardando GPS do motorista.';
    } else msg += ` · Ida ${rota.horario_ida} / retorno ${rota.horario_retorno}`;
    aviso(msg);
    if(primeira) {enquadrar();primeira=false;}
  }
  async function atualizar() {
    if(ocupado || document.hidden) return;
    ocupado=true;
    try {
      dados=await json('/api/mapa/');
      if(!tiles) {
        const attr=document.createElement('a');attr.href=dados.mapa.atribuicao_url;attr.textContent=dados.mapa.atribuicao;
        tiles=L.tileLayer(dados.mapa.tiles,{maxZoom:19,attribution:attr.outerHTML}).addTo(map);
        tiles.on('tileerror',()=>aviso('Fundo do mapa indisponível. Confira a conexão; a posição recebida continua marcada.'));
      }
      const anterior=select.value;
      select.replaceChildren();
      for(const v of dados.viagens) select.add(new Option(`${v.onibus_codigo} · ${v.rota_nome} · ${v.sentido}`,`v:${v.id}`));
      for(const r of dados.rotas) select.add(new Option(`Rota: ${r.nome}`,`r:${r.id}`));
      if([...select.options].some(o=>o.value===anterior)) select.value=anterior;
      if(!select.options.length) select.add(new Option('Nenhuma rota disponível',''));
      await desenhar();
    } catch(e) {aviso('Não foi possível atualizar. O mapa pode mostrar dados antigos. '+e.message);}
    finally {ocupado=false;}
  }
  select.addEventListener('change',()=>{primeira=true;desenhar().catch(e=>aviso(e.message));});
  document.getElementById('atualizar').onclick=atualizar;
  document.getElementById('centralizar').onclick=enquadrar;
  document.addEventListener('visibilitychange',()=>{if(!document.hidden) atualizar();});
  setInterval(atualizar,10000);atualizar();
})();
