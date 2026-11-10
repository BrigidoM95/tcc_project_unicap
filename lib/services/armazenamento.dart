import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class Armazenamento {
  static bool emMemoria = false;
  static const _seguro = FlutterSecureStorage();
  static final Map<String, String> _memoria = {};
  static final Map<String, Future<void>> _escritas = {};
  static Future<dynamic> ler(String chave) async {
    await _escritas[chave]?.catchError((_) {});
    final valor = emMemoria
        ? _memoria[chave]
        : await _seguro.read(key: 'unicap.v3.$chave');
    if (valor == null) return null;
    try {
      return jsonDecode(valor);
    } catch (_) {
      return null;
    }
  }

  static Future<void> salvar(String chave, dynamic valor) async {
    final texto = jsonEncode(valor);
    if (emMemoria) {
      _memoria[chave] = texto;
      return;
    }
    final anterior = _escritas[chave] ?? Future<void>.value();
    final escrita = anterior
        .catchError((_) {})
        .then((_) => _seguro.write(key: 'unicap.v3.$chave', value: texto));
    _escritas[chave] = escrita;
    try {
      await escrita;
    } finally {
      if (identical(_escritas[chave], escrita)) _escritas.remove(chave);
    }
  }

  static Future<void> apagar(String chave) async {
    if (emMemoria) {
      _memoria.remove(chave);
      return;
    }
    await _seguro.delete(key: 'unicap.v3.$chave');
  }
}
