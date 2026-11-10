import 'dart:convert';
import 'dart:async';
import 'armazenamento.dart';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String mensagem;
  final int? status;
  ApiException(this.mensagem, {this.status});
  @override
  String toString() => mensagem;
}

class _ConsultaGuardada {
  Map<String, dynamic> dados;
  DateTime quando;
  String assinatura, gravada = '';
  Timer? persistencia;
  _ConsultaGuardada(this.dados, this.quando) : assinatura = jsonEncode(dados);
}

class ApiService {
  static Map<String, dynamic>? _usuario;
  static bool falhaTemporaria(Object e) =>
      e is TimeoutException ||
      e is http.ClientException ||
      (e is ApiException && (e.status ?? 0) >= 500);
  static Future<Map<String, dynamic>> requisicao(
    String caminho,
    String token, {
    Map<String, dynamic>? corpo,
    bool delete = false,
    bool cache = false,
  }) async {
    final versao = _versaoSessao;
    final dono = _usuario?['id'];
    final chave = 'consulta.$dono.$caminho';
    final guardar = cache && corpo == null && !delete;
    try {
      final dados = _lerMapa(
        await _autenticada(
          caminho,
          token,
          corpo: corpo,
          post: corpo != null,
          delete: delete,
        ),
      );
      avisosCache.remove(caminho);
      if (guardar) {
        final consulta = _consultas.putIfAbsent(
          chave,
          () => _ConsultaGuardada(dados, DateTime.now()),
        );
        consulta.dados = dados;
        consulta.quando = DateTime.now();
        consulta.assinatura = jsonEncode(dados);
        if (consulta.persistencia == null &&
            consulta.assinatura != consulta.gravada) {
          await _persistirConsulta(chave, consulta);
        }
      }
      return dados;
    } catch (e) {
      _conferirSessao(versao);
      if (guardar && falhaTemporaria(e)) {
        final memoria = _consultas[chave];
        final salvo = memoria != null
            ? {
                'dados': memoria.dados,
                'quando': memoria.quando.toIso8601String(),
              }
            : await Armazenamento.ler(chave);
        _conferirSessao(versao);
        final quando = DateTime.tryParse('${salvo?['quando']}');
        if (quando != null &&
            DateTime.now().difference(quando) < const Duration(hours: 24)) {
          avisosCache[caminho] = quando;
          return Map<String, dynamic>.from(salvo['dados'] as Map);
        }
      }
      rethrow;
    }
  }

  static Future<void> _persistirConsulta(
    String chave,
    _ConsultaGuardada consulta,
  ) async {
    final assinatura = consulta.assinatura;
    final dados = {
      'dados': consulta.dados,
      'quando': consulta.quando.toUtc().toIso8601String(),
    };
    consulta.persistencia = Timer(const Duration(minutes: 2), () {
      consulta.persistencia = null;
      if (identical(_consultas[chave], consulta) &&
          consulta.assinatura != consulta.gravada) {
        unawaited(_persistirConsulta(chave, consulta));
      }
    });
    try {
      await Armazenamento.salvar(chave, dados);
      consulta.gravada = assinatura;
    } catch (_) {
      // O último resultado segue disponível em memória se o aparelho negar escrita.
    }
  }

  static String mensagemErro(Object erro) {
    if (erro is PlatformException) {
      return erro.message ??
          'Recurso do aparelho indisponível. Confira as permissões e tente novamente.';
    }
    if (erro is TimeoutException) {
      return 'O servidor demorou para responder. Confira sua conexão e tente novamente.';
    }
    if (erro is http.ClientException) {
      return 'Não foi possível conectar ao servidor. Confira sua conexão.';
    }
    return erro.toString().replaceFirst(RegExp(r'^Exception:\s*'), '');
  }

  static String _mensagemResposta(dynamic valor) {
    if (valor is String && valor.isNotEmpty) return valor;
    if (valor is Map && valor.isNotEmpty) {
      return _mensagemResposta(
        valor['detail'] ?? valor['erro'] ?? valor.values.first,
      );
    }
    if (valor is List && valor.isNotEmpty) {
      return _mensagemResposta(valor.first);
    }
    return 'Não foi possível concluir a operação. Tente novamente.';
  }

  static http.Client _client = http.Client();
  @visibleForTesting
  static void usarClienteTeste(http.Client client) {
    _client = client;
    Armazenamento.emMemoria = true;
  }

  static final Map<String, _ConsultaGuardada> _consultas = {};
  static final Map<String, DateTime> avisosCache = {};

  static const Duration _timeout = Duration(seconds: 20);

  static String? _access;
  static String? _refresh;
  static String? _tokenDoLogin;
  static Future<String>? _renovacao;
  static int _versaoSessao = 0;

  static String get baseUrl {
    const configurada = String.fromEnvironment('API_URL');
    if (configurada.isNotEmpty) {
      return configurada.endsWith('/') ? configurada : '$configurada/';
    }
    if (kIsWeb) {
      if (kReleaseMode || Uri.base.scheme == 'https') {
        return '${Uri.base.origin}/';
      }
      return 'http://127.0.0.1:8000/';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000/';
    }
    return 'http://127.0.0.1:8000/';
  }

  static Future<void> sair() async {
    final access = _access, refresh = _refresh;
    encerrarSessao();
    await Armazenamento.apagar('sessao');
    if (access == null || refresh == null) return;
    try {
      await _client
          .post(
            Uri.parse('${baseUrl}api/logout/'),
            headers: {
              'Authorization': 'Bearer $access',
              'Content-Type': 'application/json',
            },
            body: jsonEncode({'refresh': refresh}),
          )
          .timeout(const Duration(seconds: 5));
    } catch (_) {
      /* A sessão local sempre é apagada, mesmo sem rede. */
    }
  }

  static void encerrarSessao() {
    _versaoSessao++;
    for (final consulta in _consultas.values) {
      consulta.persistencia?.cancel();
    }
    _consultas.clear();
    avisosCache.clear();
    _access = null;
    _usuario = null;
    _refresh = null;
    _tokenDoLogin = null;
    _renovacao = null;
  }

  static void _conferirSessao(int versao) {
    if (versao != _versaoSessao) {
      throw ApiException(
        'A sessão foi alterada. Entre novamente se necessário.',
      );
    }
  }

  static dynamic _lerResposta(http.Response response) {
    if (response.statusCode == 401) {
      throw ApiException('Sessão expirada. Saia e entre novamente.');
    }

    dynamic dados;

    try {
      dados = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      throw ApiException(
        'Resposta inválida do servidor. HTTP ${response.statusCode}.',
      );
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(_mensagemResposta(dados), status: response.statusCode);
    }

    return dados;
  }

  static Map<String, dynamic> _lerMapa(http.Response response) {
    final dados = _lerResposta(response);

    if (dados is! Map) {
      throw ApiException('Formato inesperado recebido do servidor.');
    }

    return Map<String, dynamic>.from(dados);
  }

  // LOGIN E RENOVAÇÃO

  static Future<Map<String, dynamic>?> login(String email, String senha) async {
    encerrarSessao();
    final versao = _versaoSessao;

    final response = await _client
        .post(
          Uri.parse('${baseUrl}api/login/'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'identificador': email, 'senha': senha}),
        )
        .timeout(_timeout);

    _conferirSessao(versao);

    if (response.statusCode != 200) {
      _lerResposta(response);
    }

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
    _usuario = Map<String, dynamic>.from(dados['usuario'] as Map);
    return dados;
  }

  static Future<String> _solicitarRenovacao(int versao) async {
    _conferirSessao(versao);

    final refresh = _refresh;

    if (refresh == null || refresh.isEmpty) {
      throw ApiException('Sessão expirada. Saia e entre novamente.');
    }

    final response = await _client
        .post(
          Uri.parse('${baseUrl}api/token/refresh/'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh': refresh}),
        )
        .timeout(_timeout);

    _conferirSessao(versao);

    if (response.statusCode == 401 || response.statusCode == 403) {
      encerrarSessao();
      throw ApiException('Sessão expirada. Saia e entre novamente.');
    }

    final dados = _lerMapa(response);
    final novoAccess = dados['access'];

    if (novoAccess is! String || novoAccess.isEmpty) {
      throw ApiException('O servidor não retornou um token válido.');
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
    bool delete = false,
  }) async {
    final versao = _versaoSessao;
    final tokenInicial = _access;

    if (tokenInicial == null ||
        (tokenDaTela != _tokenDoLogin && tokenDaTela != tokenInicial)) {
      throw ApiException('Sessão expirada. Saia e entre novamente.');
    }

    Future<http.Response> enviar(String token) {
      _conferirSessao(versao);

      final uri = Uri.parse('$baseUrl$caminho');
      final headers = {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

      if (delete) {
        return _client
            .delete(uri, headers: headers, body: jsonEncode(corpo ?? {}))
            .timeout(_timeout);
      }
      if (post) {
        return _client
            .post(
              uri,
              headers: headers,
              body: corpo == null ? null : jsonEncode(corpo),
            )
            .timeout(_timeout);
      }

      return _client.get(uri, headers: headers).timeout(_timeout);
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
      throw ApiException('Sessão expirada. Saia e entre novamente.');
    }

    return response;
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
}
