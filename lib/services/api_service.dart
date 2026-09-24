import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiService {
  static const String pcIp = '192.168.170.105';
  static const Duration _timeout = Duration(seconds: 20);

  static String? _access;
  static String? _refresh;
  static String? _tokenDoLogin;
  static Future<String>? _renovacao;
  static int _versaoSessao = 0;

  static String get baseUrl {
    if (kIsWeb) {
      return 'http://127.0.0.1:8000/';
    }

    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://$pcIp:8000/';
      // Emulador Android: http://10.0.2.2:8000/
    }

    return 'http://127.0.0.1:8000/';
  }

  static void encerrarSessao() {
    _versaoSessao++;
    _access = null;
    _refresh = null;
    _tokenDoLogin = null;
    _renovacao = null;
  }

  static void _conferirSessao(int versao) {
    if (versao != _versaoSessao) {
      throw Exception('A sessão foi alterada. Entre novamente se necessário.');
    }
  }

  static dynamic _lerResposta(http.Response response) {
    if (response.statusCode == 401) {
      throw Exception('Sessão expirada. Saia e entre novamente.');
    }

    dynamic dados;

    try {
      dados = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      throw Exception(
        'Resposta inválida do servidor. HTTP ${response.statusCode}.',
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      final mensagem = dados is Map
          ? (dados['detail'] ?? dados['erro'] ?? dados.toString())
          : 'Não foi possível concluir a operação.';

      throw Exception(mensagem.toString());
    }

    return dados;
  }

  static Map<String, dynamic> _lerMapa(http.Response response) {
    final dados = _lerResposta(response);

    if (dados is! Map) {
      throw Exception('Formato inesperado recebido do servidor.');
    }

    return Map<String, dynamic>.from(dados);
  }

  // LOGIN E RENOVAÇÃO

  static Future<Map<String, dynamic>?> login(String email, String senha) async {
    encerrarSessao();
    final versao = _versaoSessao;

    try {
      final response = await http
          .post(
            Uri.parse('${baseUrl}api/login/'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'email': email, 'senha': senha}),
          )
          .timeout(_timeout);

      _conferirSessao(versao);

      if (response.statusCode != 200) return null;

      final dados = _lerMapa(response);
      final access = dados['access'];
      final refresh = dados['refresh'];

      if (access is! String ||
          access.isEmpty ||
          refresh is! String ||
          refresh.isEmpty ||
          dados['usuario'] is! Map) {
        return null;
      }

      _access = access;
      _refresh = refresh;
      _tokenDoLogin = access;

      return dados;
    } catch (_) {
      return null;
    }
  }

  static Future<String> _solicitarRenovacao(int versao) async {
    _conferirSessao(versao);

    final refresh = _refresh;

    if (refresh == null || refresh.isEmpty) {
      throw Exception('Sessão expirada. Saia e entre novamente.');
    }

    final response = await http
        .post(
          Uri.parse('${baseUrl}api/token/refresh/'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh': refresh}),
        )
        .timeout(_timeout);

    _conferirSessao(versao);

    if (response.statusCode == 401 || response.statusCode == 403) {
      encerrarSessao();
      throw Exception('Sessão expirada. Saia e entre novamente.');
    }

    final dados = _lerMapa(response);
    final novoAccess = dados['access'];

    if (novoAccess is! String || novoAccess.isEmpty) {
      throw Exception('O servidor não retornou um token válido.');
    }

    _access = novoAccess;

    // Também aceita rotação caso ela seja habilitada no futuro.
    final novoRefresh = dados['refresh'];
    if (novoRefresh is String && novoRefresh.isNotEmpty) {
      _refresh = novoRefresh;
    }

    return novoAccess;
  }

  static Future<String> _renovarToken(int versao) async {
    _conferirSessao(versao);

    final pendente = _renovacao;
    if (pendente != null) {
      return await pendente;
    }

    final tarefa = _solicitarRenovacao(versao);
    _renovacao = tarefa;

    try {
      return await tarefa;
    } finally {
      if (identical(_renovacao, tarefa)) {
        _renovacao = null;
      }
    }
  }

  // Todas as chamadas autenticadas passam por este método.
  static Future<http.Response> _autenticada(
    String caminho,
    String tokenDaTela, {
    Map<String, dynamic>? corpo,
    bool post = false,
  }) async {
    final versao = _versaoSessao;
    final tokenInicial = _access;

    if (tokenInicial == null ||
        (tokenDaTela != _tokenDoLogin && tokenDaTela != tokenInicial)) {
      throw Exception('Sessão expirada. Saia e entre novamente.');
    }

    Future<http.Response> enviar(String token) {
      _conferirSessao(versao);

      final uri = Uri.parse('$baseUrl$caminho');
      final headers = {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

      if (post) {
        return http
            .post(
              uri,
              headers: headers,
              body: corpo == null ? null : jsonEncode(corpo),
            )
            .timeout(_timeout);
      }

      return http.get(uri, headers: headers).timeout(_timeout);
    }

    var response = await enviar(tokenInicial);
    _conferirSessao(versao);

    if (response.statusCode != 401) return response;

    // Outra chamada pode já ter renovado o token.
    final atual = _access;
    final String novoToken;

    if (atual != null && atual != tokenInicial) {
      novoToken = atual;
    } else {
      novoToken = await _renovarToken(versao);
    }

    _conferirSessao(versao);

    // Apenas uma repetição, sem ciclo infinito de renovação.
    response = await enviar(novoToken);
    _conferirSessao(versao);

    if (response.statusCode == 401) {
      encerrarSessao();
      throw Exception('Sessão expirada. Saia e entre novamente.');
    }

    return response;
  }

  // ÔNIBUS

  static Future<List<Map<String, dynamic>>> listarOnibus(
    String accessToken,
  ) async {
    final response = await _autenticada('api/onibus/', accessToken);

    final dados = _lerResposta(response);

    if (dados is! List) {
      throw Exception('Formato inesperado recebido da API.');
    }

    return dados.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  static Future<Map<String, dynamic>> buscarOnibus(
    int id,
    String accessToken,
  ) async {
    return _lerMapa(await _autenticada('api/onibus/$id/', accessToken));
  }

  static String tratarUrlImagem(String? url) {
    if (url == null || url.isEmpty) return '';

    final uri = Uri.tryParse(url);

    if (uri != null && (uri.scheme == 'http' || uri.scheme == 'https')) {
      if (uri.host == '127.0.0.1' || uri.host == 'localhost') {
        return uri.replace(host: Uri.parse(baseUrl).host).toString();
      }

      return url;
    }

    final caminho = url.startsWith('/') ? url.substring(1) : url;
    return '$baseUrl$caminho';
  }

  // VIAGENS

  static Future<Map<String, dynamic>> painelMotorista(String token) async {
    return _lerMapa(await _autenticada('api/viagens/painel/', token));
  }

  static Future<Map<String, dynamic>> iniciarViagem(
    int rotaId,
    String sentido,
    String token,
  ) async {
    return _lerMapa(
      await _autenticada(
        'api/viagens/iniciar/',
        token,
        post: true,
        corpo: {'rota_id': rotaId, 'sentido': sentido},
      ),
    );
  }

  static Future<Map<String, dynamic>> finalizarViagem(
    int viagemId,
    String token,
  ) async {
    return _lerMapa(
      await _autenticada('api/viagens/$viagemId/finalizar/', token, post: true),
    );
  }

  static Future<Map<String, dynamic>> enviarLocalizacao({
    required int viagemId,
    required String token,
    required double latitude,
    required double longitude,
    required double precisaoMetros,
    required DateTime capturadaEm,
  }) async {
    return _lerMapa(
      await _autenticada(
        'api/viagens/$viagemId/localizacao/',
        token,
        post: true,
        corpo: {
          'latitude': latitude.toStringAsFixed(6),
          'longitude': longitude.toStringAsFixed(6),
          'precisao_metros': precisaoMetros.isFinite && precisaoMetros >= 0
              ? precisaoMetros.toStringAsFixed(2)
              : null,
          'capturada_em': capturadaEm.toUtc().toIso8601String(),
        },
      ),
    );
  }
}
