import 'dart:async';
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'armazenamento.dart';

/// A confirmação só existe depois da resposta do servidor. Falhas definitivas
/// ficam visíveis para o usuário; falhas de rede permanecem na fila.
class FilaOffline extends ChangeNotifier {
  static final instancia = FilaOffline();
  List<Map<String, dynamic>> itens = [];
  String? _token, _dono;
  Timer? _timer;
  bool _enviando = false;
  int _geracao = 0;
  final Set<Future<void> Function()> _protegerGps = {};
  Future<void> protegerGpsEmEnvio() async {
    await Future.wait(_protegerGps.toList().map((guardar) => guardar()));
  }

  Future<void> iniciar(String token, String dono) async {
    parar();
    _token = token;
    _dono = dono;
    final geracao = _geracao;
    final salvos = await Armazenamento.ler('fila.$dono');
    if (geracao != _geracao) return;
    itens = (salvos as List? ?? [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    notifyListeners();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => sincronizar());
    unawaited(sincronizar());
  }

  void parar() {
    _geracao++;
    _timer?.cancel();
    _token = null;
    _dono = null;
    itens = [];
  }

  Future<void> _salvar() async {
    if (_dono != null) await Armazenamento.salvar('fila.$_dono', itens);
    notifyListeners();
  }

  Future<void> adicionar(
    String tipo,
    String caminho,
    Map<String, dynamic> corpo, {
    Map<String, dynamic>? resumo,
  }) async {
    final id =
        '$tipo:${corpo['viagem_id'] ?? caminho}:${corpo['sentido'] ?? ''}:${corpo['acao'] ?? ''}';
    if (itens.any((e) => e['id'] == id && e['estado'] == 'pendente')) return;
    itens.add({
      'id': id,
      'tipo': tipo,
      'caminho': caminho,
      'corpo': corpo,
      'resumo': resumo,
      'estado': 'pendente',
      'criado_em': DateTime.now().toUtc().toIso8601String(),
    });
    await _salvar();
  }

  Future<Map<String, dynamic>> enviarGps(
    int viagem,
    List<Map<String, dynamic>> posicoes, {
    bool preservar = false,
  }) async {
    if (posicoes.isEmpty || posicoes.length > 200) {
      throw ArgumentError('O lote deve conter de 1 a 200 posições.');
    }
    final dono = _dono, token = _token, geracao = _geracao;
    final item = <String, dynamic>{
      'id': 'gps:$viagem:${posicoes.first['capturada_em']}',
      'tipo': 'gps',
      'caminho': 'api/viagens/$viagem/localizacoes/',
      'corpo': {'posicoes': List<Map<String, dynamic>>.from(posicoes)},
      'estado': 'pendente',
    };
    var guardado = false;
    Future<void> guardar() async {
      guardado = true;
      if (dono == null) return;
      if (geracao == _geracao) {
        if (!itens.contains(item)) itens.add(item);
        await _salvar();
      } else {
        final salvos = List<dynamic>.from(
          await Armazenamento.ler('fila.$dono') as List? ?? [],
        );
        salvos.removeWhere((e) => e['id'] == item['id']);
        salvos.add(item);
        await Armazenamento.salvar('fila.$dono', salvos);
      }
    }

    _protegerGps.add(guardar);
    try {
      if (preservar) await guardar();
      if (token == null) {
        throw ApiException('Entre novamente para enviar a localização.');
      }
      final resposta = await ApiService.requisicao(
        item['caminho'] as String,
        token,
        corpo: Map<String, dynamic>.from(item['corpo'] as Map),
      );
      validarGps(resposta);
      item['estado'] = 'confirmado';
      item['resposta'] = resposta;
      if (guardado && geracao == _geracao) {
        itens.remove(item);
        await _salvar();
      }
    } catch (e) {
      item['erro'] = ApiService.mensagemErro(e);
      if (e is ApiException) item['status'] = e.status;
      if (!ApiService.falhaTemporaria(e)) item['estado'] = 'recusado';
      await guardar();
    } finally {
      _protegerGps.remove(guardar);
    }
    return item;
  }

  static void validarGps(Map<String, dynamic> resposta) {
    if ((resposta['descartadas'] as num? ?? 0) > 0 &&
        (resposta['aceitas'] as num? ?? 0) == 0 &&
        (resposta['repetidas'] as num? ?? 0) == 0) {
      final motivos = (resposta['motivos'] as List? ?? []).join(' ');
      throw ApiException(
        motivos.isEmpty ? 'O servidor recusou a posição do GPS.' : motivos,
      );
    }
  }

  Future<void> sincronizar() async {
    if (_enviando || _token == null) return;
    _enviando = true;
    final geracao = _geracao;
    try {
      for (final item in List<Map<String, dynamic>>.from(
        itens.where((e) => e['estado'] == 'pendente'),
      )) {
        if (geracao != _geracao) return;
        try {
          final resposta = await ApiService.requisicao(
            item['caminho'] as String,
            _token!,
            corpo: Map<String, dynamic>.from(item['corpo'] as Map),
          );
          if (geracao != _geracao) return;
          if (item['tipo'] == 'gps') validarGps(resposta);
          item['estado'] = 'confirmado';
          item['resposta'] = resposta;
          if (item['tipo'] == 'gps') itens.remove(item);
          await _salvar();
        } catch (e) {
          if (ApiService.falhaTemporaria(e)) break;
          if (geracao != _geracao) return;
          item['estado'] = 'recusado';
          item['erro'] = ApiService.mensagemErro(e);
          await _salvar();
        }
      }
    } finally {
      _enviando = false;
    }
  }

  Map<String, dynamic>? checkin(int viagem, String sentido) {
    for (final x in itens.reversed) {
      if (x['tipo'] == 'checkin' &&
          x['corpo']['viagem_id'] == viagem &&
          x['corpo']['sentido'] == sentido) {
        return x;
      }
    }
    return null;
  }
}
