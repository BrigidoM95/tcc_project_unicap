import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aulas_flutter/services/api_service.dart';

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
  tearDown(ApiService.encerrarSessao);
  test('login e chamada autenticada usam token recebido', () async {
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        expect(r.headers['Authorization'], 'Bearer access-1');
        return resposta([
          {'id': 1},
        ]);
      }),
    );
    final d = await ApiService.login('a@example.test', 'Senha!81234');
    expect(
      (await ApiService.listarOnibus(d!['access'] as String)).single['id'],
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
        return resposta([]);
      }),
    );
    final d = await ApiService.login('a@example.test', 'Senha!81234');
    await Future.wait([
      ApiService.listarOnibus(d!['access'] as String),
      ApiService.listarOnibus(d['access'] as String),
    ]);
    expect(refresh, 1);
  });
  test('rede indisponível permite consulta temporária em cache', () async {
    var offline = false;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        if (offline) throw http.ClientException('offline');
        return resposta([
          {'id': 7},
        ]);
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.listarOnibus('access-1');
    offline = true;
    expect((await ApiService.listarOnibus('access-1')).single['id'], 7);
    expect(ApiService.avisosCache['api/onibus/'], isNotNull);
  });
  test('cache não esconde rejeição de permissão', () async {
    var negar = false;
    ApiService.usarClienteTeste(
      MockClient((r) async {
        if (r.url.path == '/api/login/') return resposta(sessao());
        return negar
            ? resposta({'detail': 'proibido'}, 403)
            : resposta([
                {'id': 7},
              ]);
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.listarOnibus('access-1');
    negar = true;
    await expectLater(
      ApiService.listarOnibus('access-1'),
      throwsA(isA<ApiException>()),
    );
  });
  test('encerrar sessão apaga cache e impede reutilização do token', () async {
    ApiService.usarClienteTeste(
      MockClient(
        (r) async => r.url.path == '/api/login/'
            ? resposta(sessao())
            : resposta([
                {'id': 1},
              ]),
      ),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.listarOnibus('access-1');
    ApiService.encerrarSessao();
    expect(ApiService.avisosCache, isEmpty);
    await expectLater(
      ApiService.listarOnibus('access-1'),
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
      ApiService.embarques(
        'checkin/',
        'access-1',
        corpo: {'codigo': 'UNIBUS-ABC234'},
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
        return resposta([]);
      }),
    );
    await ApiService.login('a@example.test', 'Senha!81234');
    await ApiService.sair();
    expect(logout, true);
    await expectLater(
      ApiService.listarOnibus('access-1'),
      throwsA(isA<ApiException>()),
    );
  });
  test('resposta de login anterior não invade uma nova sessão', () async {
    ApiService.usarClienteTeste(
      MockClient((r) async {
        final id = jsonDecode(r.body)['email'] == 'primeiro@example.test'
            ? '1'
            : '2';
        if (id == '1') {
          await Future<void>.delayed(const Duration(milliseconds: 30));
        }
        return resposta(sessao(id));
      }),
    );
    final primeiro = ApiService.login('primeiro@example.test', 'Senha!81234');
    final segundo = await ApiService.login(
      'segundo@example.test',
      'Senha!81234',
    );
    expect(segundo!['access'], 'access-2');
    expect(await primeiro, isNull);
  });
}
