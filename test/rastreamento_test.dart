import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aulas_flutter/services/api_service.dart';
import 'package:aulas_flutter/services/armazenamento.dart';
import 'package:aulas_flutter/services/fila_offline.dart';
import 'package:aulas_flutter/services/rastreamento.dart';

class GpsSimulado extends GeolocatorPlatform {
  bool ligado = true;
  LocationPermission permissao = LocationPermission.whileInUse;
  double precisao = 35;
  @override
  Future<bool> isLocationServiceEnabled() async => ligado;
  @override
  Future<LocationPermission> checkPermission() async => permissao;
  @override
  Future<LocationPermission> requestPermission() async => permissao;
  @override
  Stream<Position> getPositionStream({LocationSettings? locationSettings}) =>
      const Stream.empty();
  @override
  Future<Position> getCurrentPosition({
    LocationSettings? locationSettings,
  }) async => Position(
    latitude: -22.61,
    longitude: -54.81,
    timestamp: DateTime.now(),
    accuracy: precisao,
    altitude: 0,
    altitudeAccuracy: 0,
    heading: 0,
    headingAccuracy: 0,
    speed: 5,
    speedAccuracy: 1,
  );
}

void main() {
  final original = GeolocatorPlatform.instance;
  final gps = Rastreamento.instancia;
  final fila = FilaOffline.instancia;
  late GpsSimulado aparelho;
  var envios = 0;
  var recusar = false;
  Map<String, dynamic> viagem() => {
    'id': 9,
    'status': 'em_andamento',
    'etapa': 'transito_ida',
    'iniciada_em': DateTime.now()
        .subtract(const Duration(minutes: 5))
        .toIso8601String(),
  };
  setUp(() async {
    aparelho = GpsSimulado();
    GeolocatorPlatform.instance = aparelho;
    Armazenamento.emMemoria = true;
    await Armazenamento.apagar('fila.9');
    envios = 0;
    recusar = false;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        Object dados;
        if (r.url.path == '/api/login/') {
          dados = {
            'access': 'gps',
            'refresh': 'refresh',
            'usuario': {'id': 9},
          };
        } else {
          envios++;
          expectSync(r.url.path, '/api/viagens/9/localizacoes/');
          expectSync(
            jsonDecode(r.body)['posicoes'].single['precisao_metros'],
            '35.00',
          );
          dados = {
            'aceitas': recusar ? 0 : 1,
            'repetidas': 0,
            'descartadas': recusar ? 1 : 0,
            'motivos': recusar
                ? ['Motorista sem vínculo com este ônibus.']
                : [],
          };
        }
        return http.Response(
          jsonEncode(dados),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
    await ApiService.login('motorista', 'senha');
    await fila.iniciar('gps', '9');
  });
  tearDown(() {
    gps.parar();
    fila.parar();
    ApiService.encerrarSessao();
    GeolocatorPlatform.instance = original;
  });

  testWidgets(
    'GPS envia precisão realista, repete durante trajeto e para no fim',
    (t) async {
      gps.atualizar(viagem(), 'gps');
      await t.pump();
      expect(envios, 1);
      expect(gps.erro, isNull);
      expect(gps.ultimoEnvio, isNotNull);
      expect(fila.itens, isEmpty);
      await t.pump(const Duration(seconds: 11));
      expect(envios, 2);
      gps.atualizar({
        ...viagem(),
        'status': 'finalizada',
        'etapa': 'encerrada',
      }, 'gps');
      await t.pump(const Duration(seconds: 20));
      expect(envios, 2);
      expect(gps.ativo, false);
      fila.parar();
    },
  );

  testWidgets('Recusa do servidor nunca é anunciada como GPS enviado', (
    t,
  ) async {
    recusar = true;
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    expect(gps.ultimoEnvio, isNull);
    expect(gps.erro, contains('Motorista sem vínculo'));
    expect(fila.itens.single['estado'], 'recusado');
    gps.parar();
    fila.parar();
  });

  testWidgets('Sinal impreciso não é enviado e exibe orientação', (t) async {
    aparelho.precisao = 500;
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    expect(envios, 0);
    expect(gps.erro, contains('localização precisa'));
    gps.parar();
    fila.parar();
  });

  test(
    'Permissão negada, bloqueada e GPS desligado têm mensagens claras',
    () async {
      aparelho.permissao = LocationPermission.denied;
      await expectLater(
        Rastreamento.permitir(),
        throwsA(predicate((e) => '$e'.contains('negada'))),
      );
      aparelho.permissao = LocationPermission.deniedForever;
      await expectLater(
        Rastreamento.permitir(),
        throwsA(predicate((e) => '$e'.contains('bloqueada'))),
      );
      aparelho.ligado = false;
      await expectLater(
        Rastreamento.permitir(),
        throwsA(predicate((e) => '$e'.contains('desligada'))),
      );
    },
  );
}
