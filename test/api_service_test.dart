import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aulas_flutter/services/api_service.dart';
import 'package:aulas_flutter/services/armazenamento.dart';

http.Response resposta(Object data, [int code = 200]) => http.Response(
  jsonEncode(data),
  code,
  headers: {'content-type': 'application/json'},
);
Map<String, dynamic> sessao([String id = '1']) => {
  'access': 'access-$id',
  'refresh': 'refresh-$id',
  'usuario': {'id': id, 'nome': 'Teste', 'tipo': 'associado'},
};
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  tearDown(ApiService.encerrarSessao);
  testWidgets(
    'Cache usa último resultado em memória e limita gravações alteradas a dois minutos',
    (t) async {
      var versao = 1, offline = false;
      const chave = 'consulta.1.api/cache-teste/';
      Armazenamento.emMemoria = true;
      await Armazenamento.apagar(chave);
      ApiService.usarClienteTeste(
        MockClient((r) async {
          if (r.url.path == '/api/login/') return resposta(sessao());
          if (offline) throw http.ClientException('Sem rede');
          return resposta({'versao': versao});
        }),
      );
      await ApiService.login('teste', 'senha');
      await ApiService.requisicao('api/cache-teste/', 'access-1', cache: true);
      versao = 2;
      await ApiService.requisicao('api/cache-teste/', 'access-1', cache: true);
      expect((await Armazenamento.ler(chave))['dados']['versao'], 1);
      offline = true;
      expect(
        (await ApiService.requisicao(
          'api/cache-teste/',
          'access-1',
          cache: true,
        ))['versao'],
        2,
      );
      await t.pump(const Duration(minutes: 2));
      final salvo = await Armazenamento.ler(chave);
      expect(salvo['dados']['versao'], 2);
      offline = false;
      await ApiService.requisicao('api/cache-teste/', 'access-1', cache: true);
      await t.pump(const Duration(minutes: 2));
      expect(await Armazenamento.ler(chave), salvo);
      ApiService.encerrarSessao();
    },
  );
  test('login e chamada autenticada usam token recebido', () async {
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        expect(r.headers['Authorization'], 'Bearer access-1');
        return resposta({
          'viagens': [
            {'id': 1},
          ],
        });
      }),
    );
    final d = await ApiService.login('a@example.test', 'Senha!81234');
    expect(
      (await ApiService.requisicao(
        'api/viagens/hoje/',
        d!['access'] as String,
        cache: true,
      ))['viagens'].single['id'],
      1,
    );
  });
  test('duas chamadas com token vencido compartilham uma renovação', () async {
    var refresh = 0;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        if (r.url.path == '/api/token/refresh/') {
          refresh++;
          await Future<void>.delayed(const Duration(milliseconds: 20));
          return resposta({'access': 'novo', 'refresh': 'refresh-novo'});
        }
        if (r.headers['Authorization'] == 'Bearer access-1') {
          return resposta({'detail': 'expirado'}, 401);
        }
        expect(r.headers['Authorization'], 'Bearer novo');
        return resposta({'viagens': []});
      }),
    );
    final d = await ApiService.login('a@example.test', 'Senha!81234');
    await Future.wait([
      ApiService.requisicao(
        'api/viagens/hoje/',
        d!['access'] as String,
        cache: true,
      ),
      ApiService.requisicao(
        'api/viagens/hoje/',
        d['access'] as String,
        cache: true,
      ),
    ]);
    expect(refresh, 1);
  });
  test('rede indisponível permite consulta temporária em cache', () async {
    var offline = false;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        if (offline) throw http.ClientException('offline');
        return resposta({
          'viagens': [
            {'id': 7},
          ],
        });
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.requisicao('api/viagens/hoje/', 'access-1', cache: true);
    offline = true;
    expect(
      (await ApiService.requisicao(
        'api/viagens/hoje/',
        'access-1',
        cache: true,
      ))['viagens'].single['id'],
      7,
    );
    expect(ApiService.avisosCache['api/viagens/hoje/'], isNotNull);
  });
  test('cache não esconde rejeição de permissão', () async {
    var negar = false;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        return negar
            ? resposta({'detail': 'proibido'}, 403)
            : resposta({
                'viagens': [
                  {'id': 7},
                ],
              });
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.requisicao('api/viagens/hoje/', 'access-1', cache: true);
    negar = true;
    await expectLater(
      ApiService.requisicao('api/viagens/hoje/', 'access-1', cache: true),
      throwsA(isA<ApiException>()),
    );
  });
  test('encerrar sessão apaga cache e impede reutilização do token', () async {
    ApiService.usarClienteTeste(
      MockClient(
        (r) async => r.url.path == '/api/login/'
            ? resposta(sessao())
            : resposta({
                'viagens': [
                  {'id': 1},
                ],
              }),
      ),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.requisicao('api/viagens/hoje/', 'access-1', cache: true);
    ApiService.encerrarSessao();
    expect(ApiService.avisosCache, isEmpty);
    await expectLater(
      ApiService.requisicao('api/viagens/hoje/', 'access-1', cache: true),
      throwsA(isA<ApiException>()),
    );
  });
  test('check-in sem rede não vira confirmação em cache', () async {
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        throw http.ClientException('offline');
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await expectLater(
      ApiService.requisicao(
        'api/embarques/checkin/',
        'access-1',
        corpo: {'codigo': 'UNICAP:V3:QR-assinado'},
      ),
      throwsA(isA<http.ClientException>()),
    );
  });
  test('logout envia refresh e limpa a sessão local', () async {
    bool logout = false;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        if (r.url.path == '/api/logout/') {
          logout = true;
          expect(jsonDecode(r.body)['refresh'], 'refresh-1');
          return resposta({'detail': 'ok'});
        }
        return resposta({'viagens': []});
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.sair();
    expect(logout, true);
    await expectLater(
      ApiService.requisicao('api/viagens/hoje/', 'access-1', cache: true),
      throwsA(isA<ApiException>()),
    );
  });
  test('resposta de login anterior não invade uma nova sessão', () async {
    ApiService.usarClienteTeste(
      MockClient((r) async {
        final id =
            jsonDecode(r.body)['identificador'] == 'primeiro@example.test'
            ? '1'
            : '2';
        if (id == '1') {
          await Future<void>.delayed(const Duration(milliseconds: 30));
        }
        return resposta(sessao(id));
      }),
    );
    final primeiro = expectLater(
      ApiService.login('primeiro@example.test', 'Senha!81234'),
      throwsA(isA<ApiException>()),
    );
    final segundo = await ApiService.login(
      'segundo@example.test',
      'Senha!81234',
    );
    expect(segundo!['access'], 'access-2');
    await primeiro;
  });
}
