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

  Future<Map<String, dynamic>> posicao(
    int viagem,
    Map<String, dynamic> posicao,
  ) async {
    final caminho = 'api/viagens/$viagem/localizacoes/';
    final candidatos = itens.where(
      (e) =>
          e['tipo'] == 'gps' &&
          e['caminho'] == caminho &&
          e['estado'] == 'pendente' &&
          (e['corpo']['posicoes'] as List).length < 200,
    );
    final Map<String, dynamic> item;
    if (candidatos.isNotEmpty && !_enviando) {
      item = candidatos.last;
      (item['corpo']['posicoes'] as List).add(posicao);
    } else {
      item = {
        'id': 'gps:$viagem:${posicao['capturada_em']}',
        'tipo': 'gps',
        'caminho': caminho,
        'corpo': {
          'posicoes': [posicao],
        },
        'estado': 'pendente',
      };
      itens.add(item);
    }
    await _salvar();
    return item;
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
          if (item['tipo'] == 'gps' &&
              (resposta['descartadas'] as num? ?? 0) > 0 &&
              (resposta['aceitas'] as num? ?? 0) == 0 &&
              (resposta['repetidas'] as num? ?? 0) == 0) {
            final motivos = (resposta['motivos'] as List? ?? []).join(' ');
            throw ApiException(
              motivos.isEmpty
                  ? 'O servidor recusou a posição do GPS.'
                  : motivos,
            );
          }
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
