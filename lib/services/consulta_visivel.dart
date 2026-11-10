import 'dart:async';
import 'package:flutter/material.dart';
import 'api_service.dart';

final observadorConsultas = RouteObserver<ModalRoute<dynamic>>();

/// Uma única consulta periódica por tela visível; requisições já iniciadas
/// terminam normalmente, mas nenhuma nova começa fora da tela ativa.
abstract class EstadoComConsulta<T extends StatefulWidget> extends State<T>
    with WidgetsBindingObserver, RouteAware {
  Timer? _consultaTimer;
  ModalRoute<dynamic>? _rota;
  bool _emPrimeiroPlano = true, _bloqueada = false, _consultando = false;
  bool get consultaHabilitada => true;
  bool get consultaAtiva =>
      mounted &&
      _emPrimeiroPlano &&
      !_bloqueada &&
      _rota?.isCurrent != false &&
      consultaHabilitada;
  Duration get intervaloConsulta;
  Future<void> consultar();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    final estado = WidgetsBinding.instance.lifecycleState;
    _emPrimeiroPlano = estado == null || estado == AppLifecycleState.resumed;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final rota = ModalRoute.of(context);
    if (_rota != rota) {
      observadorConsultas.unsubscribe(this);
      _rota = rota;
      if (rota != null) observadorConsultas.subscribe(this, rota);
      WidgetsBinding.instance.addPostFrameCallback((_) => retomarConsulta());
    }
  }

  void falhaConsulta(Object erro) {
    if (erro is ApiException && [403, 404].contains(erro.status)) {
      _bloqueada = true;
      _consultaTimer?.cancel();
    }
  }

  void pausarConsulta() => _consultaTimer?.cancel();

  void retomarConsulta() {
    _consultaTimer?.cancel();
    if (consultaAtiva) unawaited(_executarConsulta());
  }

  Future<void> _executarConsulta() async {
    if (!consultaAtiva || _consultando) return;
    _consultando = true;
    try {
      await consultar();
    } finally {
      _consultando = false;
      _consultaTimer?.cancel();
      if (consultaAtiva) {
        _consultaTimer = Timer(intervaloConsulta, _executarConsulta);
      }
    }
  }

  @override
  void didPush() => retomarConsulta();
  @override
  void didPopNext() => retomarConsulta();
  @override
  void didPushNext() => pausarConsulta();
  @override
  void didPop() => pausarConsulta();
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _emPrimeiroPlano = state == AppLifecycleState.resumed;
    if (_emPrimeiroPlano) {
      retomarConsulta();
    } else {
      pausarConsulta();
    }
  }

  @override
  void dispose() {
    _consultaTimer?.cancel();
    observadorConsultas.unsubscribe(this);
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
}

Duration intervaloDaViagem(Map<String, dynamic> viagem) => Duration(
  seconds: viagem['embarque_aberto'] == true || viagem['escolha_aberta'] == true
      ? 3
      : 15,
);
