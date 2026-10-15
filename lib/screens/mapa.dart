import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_service.dart';

class MapaViagens extends StatefulWidget {
  final String accessToken;
  const MapaViagens({super.key, required this.accessToken});
  @override
  State<MapaViagens> createState() => _MapaViagensState();
}

class _MapaViagensState extends State<MapaViagens> with WidgetsBindingObserver {
  final _map = MapController();
  Timer? _timer;
  bool _ocupado = false, _pronto = false, _primeira = true;
  String? _erro, _selecao;
  int _geracao = 0;
  Map<String, dynamic>? _dados, _rota, _viagem;
  List<LatLng> _trajeto = [];
  List<Map<String, dynamic>> _lista(dynamic v) => (v as List? ?? [])
      .map((x) => Map<String, dynamic>.from(x as Map))
      .toList();
  List<Map<String, dynamic>> get _rotas => _lista(_dados?['rotas']);
  List<Map<String, dynamic>> get _viagens => _lista(_dados?['viagens']);
  List<Map<String, dynamic>> get _pontos => _lista(_rota?['pontos'])
      .where((p) => _viagem == null || p['sentido'] == _viagem!['sentido'])
      .toList();
  LatLng _coord(Map p) => LatLng(
    (p['latitude'] as num).toDouble(),
    (p['longitude'] as num).toDouble(),
  );
  Map<String, dynamic>? get _local => _viagem?['localizacao'] == null
      ? null
      : Map<String, dynamic>.from(_viagem!['localizacao'] as Map);
  bool get _desatualizada {
    final t = DateTime.tryParse(_local?['capturada_em']?.toString() ?? '');
    return t == null || DateTime.now().difference(t).inSeconds > 60;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _carregar();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _carregar());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _carregar();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _geracao++;
    WidgetsBinding.instance.removeObserver(this);
    _map.dispose();
    super.dispose();
  }

  Future<void> _carregar() async {
    if (_ocupado ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.paused) {
      return;
    }
    _ocupado = true;
    try {
      final d = await ApiService.mapa(widget.accessToken);
      if (!mounted) return;
      setState(() {
        _dados = d;
        _erro = null;
      });
      final opcoes = [
        ..._viagens.map((v) => 'v:${v['id']}'),
        ..._rotas.map((r) => 'r:${r['id']}'),
      ];
      if (!opcoes.contains(_selecao)) {
        _selecao = opcoes.isEmpty ? null : opcoes.first;
        _primeira = true;
      }
      await _selecionar();
    } catch (e) {
      if (mounted) {
        setState(
          () => _erro =
              'Não foi possível atualizar. Os dados exibidos podem estar antigos. ${ApiService.mensagemErro(e)}',
        );
      }
    } finally {
      _ocupado = false;
    }
  }

  Future<void> _selecionar() async {
    final geracao = ++_geracao, escolha = _selecao;
    Map<String, dynamic>? rota, viagem;
    List<LatLng> trajeto = [];
    if (escolha?.startsWith('v:') == true) {
      final d = await ApiService.mapaViagem(
        int.parse(escolha!.substring(2)),
        widget.accessToken,
      );
      rota = Map<String, dynamic>.from(d['rota'] as Map);
      viagem = Map<String, dynamic>.from(d['viagem'] as Map);
      trajeto = _lista(d['trajeto']).map(_coord).toList();
    } else if (escolha != null) {
      for (final r in _rotas) {
        if ('r:${r['id']}' == escolha) rota = r;
      }
    }
    if (!mounted || geracao != _geracao) return;
    setState(() {
      _rota = rota;
      _viagem = viagem;
      _trajeto = trajeto;
    });
    if (_primeira) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _enquadrar();
      });
    }
  }

  void _enquadrar() {
    if (!_pronto) return;
    final pts = _pontos
        .where((p) => p['latitude'] != null && p['longitude'] != null)
        .map(_coord)
        .toList();
    if (_local != null) pts.add(_coord(_local!));
    pts.addAll(_trajeto);
    if (pts.isEmpty) return;
    _map.fitCamera(
      CameraFit.bounds(
        bounds: LatLngBounds.fromPoints(pts),
        padding: const EdgeInsets.all(48),
        maxZoom: 16,
      ),
    );
    _primeira = false;
  }

  @override
  Widget build(BuildContext context) {
    final loc = _local,
        pontos = _pontos
            .where((p) => p['latitude'] != null && p['longitude'] != null)
            .toList();
    final conf = _dados?['mapa'] as Map?;
    final linhas = <Polyline>[];
    for (final sentido in ['ida', 'retorno']) {
      final pts = pontos
          .where((p) => p['sentido'] == sentido)
          .map(_coord)
          .toList();
      if (pts.length > 1) {
        linhas.add(
          Polyline(points: pts, color: const Color(0xFF2B5E97), strokeWidth: 2),
        );
      }
    }
    if (_trajeto.length > 1) {
      linhas.add(
        Polyline(
          points: _trajeto,
          color: const Color(0xFFAD4700),
          strokeWidth: 4,
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(
        title: const Text('Acompanhar viagens'),
        actions: [
          IconButton(
            onPressed: _carregar,
            icon: const Icon(Icons.refresh),
            tooltip: 'Atualizar',
          ),
          IconButton(
            onPressed: _enquadrar,
            icon: const Icon(Icons.center_focus_strong),
            tooltip: 'Enquadrar mapa',
          ),
        ],
      ),
      body: Column(
        children: [
          if (_dados == null && _erro == null) const LinearProgressIndicator(),
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (_viagens.isNotEmpty || _rotas.isNotEmpty)
                  DropdownButtonFormField<String>(
                    key: ValueKey(_selecao),
                    initialValue: _selecao,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Viagem ou rota',
                    ),
                    items: [
                      ..._viagens.map(
                        (v) => DropdownMenuItem(
                          value: 'v:${v['id']}',
                          child: Text(
                            '${v['onibus_codigo']} · ${v['rota_nome']} · ${v['sentido']}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                      ..._rotas.map(
                        (r) => DropdownMenuItem(
                          value: 'r:${r['id']}',
                          child: Text(
                            'Rota: ${r['nome']}',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                    onChanged: (v) async {
                      setState(() {
                        _selecao = v;
                        _primeira = true;
                      });
                      try {
                        await _selecionar();
                      } catch (e) {
                        if (mounted) {
                          setState(() => _erro = ApiService.mensagemErro(e));
                        }
                      }
                    },
                  )
                else if (_dados != null)
                  const Text('Nenhuma rota ativa disponível.'),
                if (_erro != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      _erro!,
                      style: const TextStyle(color: Colors.red),
                    ),
                  ),
                if (_viagem != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      '${_viagem!['presentes']}/${_viagem!['capacidade']} embarques · ${_viagem!['vagas']} vagas',
                    ),
                  ),
                if (_viagem != null && loc == null)
                  const Text('Aguardando GPS do motorista.'),
                if (loc != null)
                  Text(
                    '${_desatualizada ? 'GPS DESATUALIZADO · ' : ''}Última leitura: ${DateTime.tryParse(loc['capturada_em'].toString())?.toLocal().toString().substring(11, 19) ?? '—'} · Precisão: ${loc['precisao_metros'] ?? '—'} m',
                    style: TextStyle(color: _desatualizada ? Colors.red : null),
                  ),
              ],
            ),
          ),
          Expanded(
            child: FlutterMap(
              mapController: _map,
              options: MapOptions(
                initialCenter: const LatLng(-22.63, -54.82),
                initialZoom: 12,
                onMapReady: () {
                  _pronto = true;
                  _enquadrar();
                },
              ),
              children: [
                if (conf != null)
                  TileLayer(
                    urlTemplate: conf['tiles'].toString(),
                    userAgentPackageName: 'br.org.unicap.unibus',
                    maxZoom: 19,
                  ),
                PolylineLayer(polylines: linhas),
                MarkerLayer(
                  markers: [
                    ...pontos.map(
                      (p) => Marker(
                        point: _coord(p),
                        width: 38,
                        height: 38,
                        child: Tooltip(
                          message:
                              '${p['ordem']}. ${p['nome']} (${p['sentido']})',
                          child: const Icon(
                            Icons.location_on,
                            color: Color(0xFF1C3B6E),
                            size: 32,
                          ),
                        ),
                      ),
                    ),
                    if (loc != null)
                      Marker(
                        point: _coord(loc),
                        width: 48,
                        height: 48,
                        child: Tooltip(
                          message: 'Ônibus ${_viagem!['onibus_codigo']}',
                          child: Container(
                            decoration: BoxDecoration(
                              color: _desatualizada
                                  ? Colors.grey
                                  : const Color(0xFFAD4700),
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 3),
                            ),
                            child: const Icon(
                              Icons.directions_bus,
                              color: Colors.white,
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                if (conf != null)
                  SimpleAttributionWidget(
                    source: Text(
                      conf['atribuicao'].toString().replaceFirst(
                        RegExp(r'^©\s*'),
                        '',
                      ),
                      style: const TextStyle(fontSize: 11),
                    ),
                    onTap: () =>
                        launchUrl(Uri.parse(conf['atribuicao_url'].toString())),
                  ),
              ],
            ),
          ),
          const SafeArea(
            top: false,
            child: Padding(
              padding: EdgeInsets.all(10),
              child: Text(
                'Atualiza a cada 10 s. Azul: pontos cadastrados (referência, não navegação). Laranja: GPS recente.',
                style: TextStyle(fontSize: 12),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
