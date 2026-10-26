import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aulas_flutter/services/api_service.dart';
import 'package:aulas_flutter/services/armazenamento.dart';
import 'package:aulas_flutter/services/fila_offline.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  final fila = FilaOffline.instancia;
  var offline = true, recusar = false, envios = 0;
  setUp(() async {
    offline = true;
    recusar = false;
    envios = 0;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') {
          return http.Response(
            jsonEncode({
              'access': 'access',
              'refresh': 'refresh',
              'usuario': {'id': 1},
            }),
            200,
          );
        }
        if (offline) throw http.ClientException('Sem rede');
        envios++;
        return http.Response(
          jsonEncode(
            recusar
                ? {'detail': 'Poltrona ocupada'}
                : {
                    'checkin': {'id': 123},
                  },
          ),
          recusar ? 409 : 201,
        );
      }),
    );
    await Armazenamento.apagar('fila.1');
    await ApiService.login('802.001', 'senha');
    await fila.iniciar('access', '1');
  });
  tearDown(() {
    fila.parar();
    ApiService.encerrarSessao();
  });
  Future<void> adicionar() => fila.adicionar(
    'checkin',
    'api/checkins/sincronizar/',
    {
      'viagem_id': 1,
      'sentido': 'ida',
      'poltrona': 1,
      'codigo': 'UNICAP:V3:assinatura',
      'offline': true,
      'lido_em': '2026-10-15T18:00:00Z',
    },
    resumo: {'id': 1},
  );
  test(
    'leitura pendente persiste ao reabrir e só confirma com resposta',
    () async {
      await adicionar();
      await fila.sincronizar();
      expect(fila.itens.single['estado'], 'pendente');
      fila.parar();
      await fila.iniciar('access', '1');
      expect(fila.itens.single['corpo']['lido_em'], '2026-10-15T18:00:00Z');
      await Future<void>.delayed(Duration.zero);
      offline = false;
      await fila.sincronizar();
      expect(fila.itens.single['estado'], 'confirmado');
      expect(fila.itens.single['resposta']['checkin']['id'], 123);
    },
  );
  test('rejeição definitiva fica visível e não repete envio', () async {
    await adicionar();
    offline = false;
    recusar = true;
    await fila.sincronizar();
    expect(fila.itens.single['estado'], 'recusado');
    expect(fila.itens.single['erro'], contains('Poltrona ocupada'));
    await fila.sincronizar();
    expect(envios, 1);
  });
  test('fila pertence ao usuário e deduplica leitura', () async {
    await adicionar();
    await adicionar();
    expect(fila.itens.length, 1);
    await Armazenamento.apagar('fila.2');
    await fila.iniciar('access', '2');
    expect(fila.itens, isEmpty);
    await fila.iniciar('access', '1');
    expect(fila.itens.length, 1);
  });
  test('GPS agrupa até 200 posições e remove lote confirmado', () async {
    for (var i = 0; i < 201; i++) {
      await fila.posicao(1, {'capturada_em': 'hora-$i'});
    }
    expect(fila.itens.length, 2);
    expect((fila.itens.first['corpo']['posicoes'] as List).length, 200);
    offline = false;
    await fila.sincronizar();
    expect(fila.itens, isEmpty);
    expect(envios, 2);
  });
}
