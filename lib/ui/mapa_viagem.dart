import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';
import 'componentes.dart';
import 'tema.dart';

class MapaDaViagem extends StatefulWidget {
  final Dados viagem;
  final double altura;
  const MapaDaViagem(this.viagem, {super.key, this.altura = 156});
  @override
  State<MapaDaViagem> createState() => _MapaDaViagemState();
}

class _MapaDaViagemState extends State<MapaDaViagem> {
  final _controle = MapController();
  bool _pronto = false;
  Dados get viagem => widget.viagem;
  double get altura => widget.altura;

  @override
  void didUpdateWidget(covariant MapaDaViagem oldWidget) {
    super.didUpdateWidget(oldWidget);
    final anterior = oldWidget.viagem['localizacao'] as Map?;
    final atual = viagem['localizacao'] as Map?;
    if (_pronto &&
        atual != null &&
        (anterior?['latitude'] != atual['latitude'] ||
            anterior?['longitude'] != atual['longitude'])) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted || !_pronto) return;
        _controle.move(
          LatLng(
            (atual['latitude'] as num).toDouble(),
            (atual['longitude'] as num).toDouble(),
          ),
          _controle.camera.zoom,
        );
      });
    }
  }

  @override
  void dispose() {
    _controle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final local = viagem['localizacao'] as Map?;
    LatLng coord(Map p) => LatLng(
      (p['latitude'] as num).toDouble(),
      (p['longitude'] as num).toDouble(),
    );
    final coords = mapas(viagem['trajeto_percorrido']).map(coord).toList();
    if (local != null) coords.add(coord(local));
    if (coords.isEmpty) {
      return Container(
        height: altura,
        decoration: BoxDecoration(
          color: fundoSuave,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: bordaUnicap),
        ),
        child: const Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.location_off_outlined, color: cinzaUnicap),
              SizedBox(height: 8),
              Text(
                'Aguardando localização do ônibus',
                style: TextStyle(fontSize: 11),
              ),
            ],
          ),
        ),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(14),
      child: SizedBox(
        height: altura,
        child: Stack(
          children: [
            FlutterMap(
              key: ValueKey('${viagem['id']}:${viagem['sentido']}'),
              mapController: _controle,
              options: MapOptions(
                onMapReady: () => _pronto = true,
                initialCenter: coords.last,
                initialZoom: 12,
                initialCameraFit: coords.length > 1
                    ? CameraFit.bounds(
                        bounds: LatLngBounds.fromPoints(coords),
                        padding: const EdgeInsets.all(30),
                        maxZoom: 15,
                      )
                    : null,
              ),
              children: [
                TileLayer(
                  urlTemplate: const String.fromEnvironment(
                    'MAP_TILE_URL',
                    defaultValue:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  ),
                  userAgentPackageName: 'br.org.unicap.transporte',
                ),
                if (mapas(viagem['trajeto_percorrido']).length > 1)
                  PolylineLayer(
                    polylines: [
                      Polyline(
                        points: mapas(
                          viagem['trajeto_percorrido'],
                        ).map(coord).toList(),
                        color: laranjaUnibus,
                        strokeWidth: 5,
                      ),
                    ],
                  ),
                MarkerLayer(
                  markers: [
                    if (local != null)
                      Marker(
                        point: coord(local),
                        width: 32,
                        height: 32,
                        child: Icon(
                          Icons.directions_bus,
                          color: local['atrasada'] == true
                              ? cinzaUnicap
                              : laranjaUnibus,
                          size: 30,
                        ),
                      ),
                  ],
                ),
              ],
            ),
            Positioned(
              right: 3,
              bottom: 2,
              child: GestureDetector(
                onTap: () => launchUrl(
                  Uri.parse('https://www.openstreetmap.org/copyright'),
                ),
                child: const ColoredBox(
                  color: Colors.white,
                  child: Text('© OpenStreetMap', style: TextStyle(fontSize: 8)),
                ),
              ),
            ),
            if (viagem['proximo_ponto'] != null)
              Positioned(
                left: 10,
                right: 10,
                bottom: 19,
                child: Etiqueta(
                  'Próximo ponto: ${viagem['proximo_ponto']}${viagem['previsao_chegada'] != null ? ' • ~ ${hora(viagem['previsao_chegada'])}' : ''}',
                  icone: Icons.location_on,
                ),
              ),
          ],
        ),
      ),
    );
  }
}
