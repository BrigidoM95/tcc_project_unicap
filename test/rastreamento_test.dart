import 'dart:convert';
import 'package:flutter/widgets.dart';
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
  bool emMovimento = true;
  int capturas = 0;
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
    latitude: -22.61 + (++capturas * (emMovimento ? .001 : 0)),
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
  var offline = false;
  var tamanhoLote = 0;
  var status = 200;
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
    offline = false;
    tamanhoLote = 0;
    status = 200;
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
          if (offline) throw http.ClientException('Sem rede');
          envios++;
          tamanhoLote = (jsonDecode(r.body)['posicoes'] as List).length;
          expectSync(r.url.path, '/api/viagens/9/localizacoes/');
          expectSync(
            jsonDecode(r.body)['posicoes'].first['precisao_metros'],
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
          r.url.path == '/api/login/' ? 200 : status,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
    await ApiService.login('motorista', 'senha');
    await fila.iniciar('gps', '9');
  });
  tearDown(() async {
    await gps.parar();
    fila.parar();
    ApiService.encerrarSessao();
    GeolocatorPlatform.instance = original;
  });

  testWidgets('GPS agrupa três posições e descarrega o restante ao encerrar', (
    t,
  ) async {
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    expect(envios, 0);
    await t.pump(const Duration(seconds: 11));
    expect(envios, 0);
    await t.pump(const Duration(seconds: 11));
    expect(envios, 1);
    expect(tamanhoLote, 3);
    expect(gps.erro, isNull);
    expect(gps.ultimoEnvio, isNotNull);
    expect(fila.itens, isEmpty);
    expect(await Armazenamento.ler('fila.9'), isNull);
    await t.pump(const Duration(seconds: 11));
    expect(envios, 1);
    gps.atualizar({
      ...viagem(),
      'status': 'finalizada',
      'etapa': 'encerrada',
    }, 'gps');
    await t.pump(const Duration(seconds: 20));
    expect(envios, 2);
    expect(tamanhoLote, 1);
    expect(gps.ativo, false);
    fila.parar();
  });

  testWidgets('Recusa do servidor nunca é anunciada como GPS enviado', (
    t,
  ) async {
    recusar = true;
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    await gps.enviarLote();
    expect(gps.ultimoEnvio, isNull);
    expect(gps.erro, contains('Motorista sem vínculo'));
    expect(fila.itens.single['estado'], 'recusado');
    await gps.parar();
    fila.parar();
  });

  testWidgets('Lote incompleto sai em30s e evita repetir posição parada', (
    t,
  ) async {
    aparelho.emMovimento = false;
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    await t.pump(const Duration(seconds: 11));
    await t.pump(const Duration(seconds: 11));
    expect(envios, 0);
    await t.pump(const Duration(seconds: 8));
    expect(envios, 1);
    expect(tamanhoLote, 1);
    await gps.parar();
    fila.parar();
  });

  testWidgets('GPS deixa de capturar após revogação de acesso', (t) async {
    status = 403;
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    await gps.enviarLote();
    expect(gps.ativo, false);
    expect(gps.erro, contains('Posição não recebida'));
    final antes = aparelho.capturas;
    await t.pump(const Duration(minutes: 1));
    expect(aparelho.capturas, antes);
    expect(envios, 1);
    fila.parar();
  });

  testWidgets('Sinal impreciso não é enviado e exibe orientação', (t) async {
    aparelho.precisao = 500;
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    expect(envios, 0);
    expect(gps.erro, contains('localização precisa'));
    await gps.parar();
    fila.parar();
  });

  testWidgets('Suspensão protege lote GPS e mantém check-in pendente', (
    t,
  ) async {
    offline = true;
    await fila.adicionar('checkin', 'api/checkins/sincronizar/', {
      'viagem_id': 9,
      'sentido': 'ida',
    });
    gps.atualizar(viagem(), 'gps');
    await t.pump();
    gps.didChangeAppLifecycleState(AppLifecycleState.paused);
    await t.pump();
    final salvos = await Armazenamento.ler('fila.9') as List;
    expect(salvos.map((e) => e['tipo']), containsAll(['checkin', 'gps']));
    expect(
      salvos.firstWhere((e) => e['tipo'] == 'gps')['corpo']['posicoes'],
      hasLength(1),
    );
    await gps.parar();
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
