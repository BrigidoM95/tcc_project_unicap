import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class ApiService {
  static const String pcIp =
      '192.168.170.105'; // Substitua pelo IP do seu PC na rede local
  static String get baseUrl {
    // Chrome / Web
    if (kIsWeb) {
      return 'http://127.0.0.1:8000/';
    }

    // Android
    if (defaultTargetPlatform == TargetPlatform.android) {
      // Para celular físico:
      return 'http://$pcIp:8000/';

      // Para emulador Android, use:
      // return 'http://10.0.2.2:8000/';
    }

    // Windows
    if (defaultTargetPlatform == TargetPlatform.windows) {
      return 'http://127.0.0.1:8000/';
    }

    return 'http://127.0.0.1:8000/';
  }

  // ============================================================
  // LOGIN
  // ============================================================

  static Future<Map<String, dynamic>?> login(String email, String senha) async {
    try {
      final response = await http.post(
        Uri.parse('${baseUrl}api/login/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'email': email, 'senha': senha}),
      );

      if (response.statusCode == 200) {
        return Map<String, dynamic>.from(
          jsonDecode(utf8.decode(response.bodyBytes)),
        );
      }

      return null;
    } catch (e) {
      return null;
    }
  }

  // ============================================================
  // LISTAR ÔNIBUS
  // ============================================================

  static Future<List<Map<String, dynamic>>> listarOnibus(
    String accessToken,
  ) async {
    final response = await http.get(
      Uri.parse('${baseUrl}api/onibus/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      },
    );

    if (response.statusCode == 200) {
      final dynamic dados = jsonDecode(utf8.decode(response.bodyBytes));

      if (dados is List) {
        return dados.map((item) => Map<String, dynamic>.from(item)).toList();
      }

      throw Exception('Formato inesperado recebido da API.');
    }

    if (response.statusCode == 401) {
      throw Exception('Sessão expirada ou usuário não autenticado.');
    }

    throw Exception(
      'Erro ao carregar ônibus. '
      'Código HTTP: ${response.statusCode}',
    );
  }

  // ============================================================
  // DETALHE DO ÔNIBUS
  // ============================================================

  static Future<Map<String, dynamic>> buscarOnibus(
    int id,
    String accessToken,
  ) async {
    final response = await http.get(
      Uri.parse('${baseUrl}api/onibus/$id/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      },
    );

    if (response.statusCode == 200) {
      return Map<String, dynamic>.from(
        jsonDecode(utf8.decode(response.bodyBytes)),
      );
    }

    throw Exception('Não foi possível carregar o ônibus.');
  }

  // ============================================================
  // TRATAR URL DA FOTO
  // ============================================================

  static String tratarUrlImagem(String? url) {
    if (url == null || url.isEmpty) {
      return '';
    }

    if (url.startsWith('http://') || url.startsWith('https://')) {
      // O serializer pode retornar 127.0.0.1.
      // No Android Emulator, precisamos trocar pelo host acessível.
      if (baseUrl.contains('10.0.2.2')) {
        return url
            .replaceFirst('127.0.0.1', '10.0.2.2')
            .replaceFirst('localhost', '10.0.2.2');
      }

      return url;
    }

    final caminho = url.startsWith('/') ? url.substring(1) : url;

    return '$baseUrl$caminho';
  }
}
