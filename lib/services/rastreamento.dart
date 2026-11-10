import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:geolocator/geolocator.dart';
import 'api_service.dart';
import 'fila_offline.dart';

class Rastreamento extends ChangeNotifier with WidgetsBindingObserver {
  static final instancia = Rastreamento();
  Timer? _timer;
  StreamSubscription<Position>? _fluxo;
  Position? _ultimaPosicao;
  DateTime? _ultimaCaptura;
  int? _intervaloFluxo;
  Map<String, dynamic>? _viagem;
  final List<Map<String, dynamic>> _lote = [];
  Timer? _timerLote;
  Position? _ultimaEnfileirada;
  bool _observando = false;

  int _geracao = 0;
  bool _capturando = false;
  String? erro;
  DateTime? ultimoEnvio;
  double velocidade = 0;
  int intervalo = 10;
  bool get ativo => _viagem != null;
  bool get emMovimento => velocidade > 1.4;
  static Future<bool>? _permissaoPendente;
  static Future<bool> permitir() async {
    final pendente = _permissaoPendente;
    if (pendente != null) return pendente;
    final tarefa = _verificarPermissao();
    _permissaoPendente = tarefa;
    try {
      return await tarefa;
    } finally {
      if (identical(_permissaoPendente, tarefa)) _permissaoPendente = null;
    }
  }

  static Future<bool> _verificarPermissao() async {
    if (kIsWeb &&
        Uri.base.scheme != 'https' &&
        !['localhost', '127.0.0.1', '::1'].contains(Uri.base.host)) {
      throw ApiException(
        'Abra o aplicativo por HTTPS para permitir a localização no navegador.',
      );
    }
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw ApiException(
        'A localização do aparelho está desligada. Ative o GPS nas configurações e tente novamente.',
      );
    }
    var p = await Geolocator.checkPermission();
    if (p == LocationPermission.denied) {
      p = await Geolocator.requestPermission();
    }
    if (p == LocationPermission.deniedForever) {
      throw ApiException(
        'Permissão de localização bloqueada. Nas configurações do aparelho ou navegador, permita a localização para a UNICAP e tente novamente.',
      );
    }
    if (p == LocationPermission.denied) {
      throw ApiException(
        'Permissão de localização negada. Permita o acesso à localização para transmitir a posição do ônibus.',
      );
    }
    // Alguns navegadores não implementam consulta de permissão: a captura
    // seguinte abre a solicitação nativa de acesso à localização.
    return p == LocationPermission.always ||
        p == LocationPermission.whileInUse ||
        kIsWeb;
  }

  void atualizar(Map<String, dynamic> v, String token) {
    if (v['status'] != 'em_andamento' ||
        ['agendada', 'encerrada', 'cancelada'].contains(v['etapa'])) {
      if (_viagem?['id'] == v['id']) parar();
      return;
    }
    final nova = _viagem?['id'] != v['id'];
    if (nova) unawaited(parar());
    _viagem = v;
    if (!_observando) {
      WidgetsBinding.instance.addObserver(this);
      _observando = true;
    }

    intervalo = v['etapa'] == 'no_destino' ? 60 : 10;
    if (nova) {
      _geracao++;
      _timer?.cancel();
      unawaited(_capturar(_geracao));
    }
  }

  Future<void> parar() async {
    final envio = enviarLote(preservar: true);
    final pendentes = FilaOffline.instancia.protegerGpsEmEnvio();
    _geracao++;
    _timer?.cancel();
    _viagem = null;
    _fluxo?.cancel();
    _fluxo = null;
    _ultimaPosicao = null;
    _ultimaCaptura = null;
    _ultimaEnfileirada = null;
    _intervaloFluxo = null;
    erro = null;
    ultimoEnvio = null;
    velocidade = 0;
    if (_observando) {
      WidgetsBinding.instance.removeObserver(this);
      _observando = false;
    }
    notifyListeners();
    await envio;
    await pendentes;
  }

  Future<void> enviarLote({bool preservar = false}) async {
    _timerLote?.cancel();
    _timerLote = null;
    if (_lote.isEmpty || _viagem == null) return;
    final viagem = _viagem!['id'] as int, geracao = _geracao;
    final posicoes = List<Map<String, dynamic>>.from(_lote);
    _lote.clear();
    final envio = await FilaOffline.instancia.enviarGps(
      viagem,
      posicoes,
      preservar: preservar,
    );
    if (geracao != _geracao) return;
    if (envio['estado'] == 'recusado') {
      if ([403, 404].contains(envio['status'])) await parar();
      erro = 'Posição não recebida: ${envio['erro']}';
    } else if (envio['estado'] == 'pendente') {
      erro = 'Posições aguardando envio • guardadas no aparelho.';
    } else {
      final resposta = envio['resposta'] as Map?;
      erro = (resposta?['descartadas'] as num? ?? 0) > 0
          ? 'Algumas posições foram recusadas: ${(resposta?['motivos'] as List? ?? []).join(' ')}'
          : null;
      ultimoEnvio = DateTime.now();
    }
    notifyListeners();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      // A gravação antecede a rede para sobreviver à suspensão do processo.
      unawaited(enviarLote(preservar: true));
      unawaited(FilaOffline.instancia.protegerGpsEmEnvio());
    } else if (ativo) {
      _timer?.cancel();
      unawaited(_capturar(_geracao));
    }
  }

  Future<void> _capturar(int geracao) async {
    if (_viagem == null || geracao != _geracao) return;
    if (_capturando) {
      _timer = Timer(const Duration(seconds: 2), () => _capturar(geracao));
      return;
    }
    _capturando = true;
    try {
      if (!await permitir()) {
        throw ApiException(
          'Permita a localização do celular para transmitir o GPS.',
        );
      }
      await _manterFluxo(geracao);
      final recente = _ultimaPosicao;
      final p =
          recente != null &&
              DateTime.now().difference(recente.timestamp).inSeconds < 20 &&
              (_ultimaCaptura == null ||
                  recente.timestamp.isAfter(_ultimaCaptura!))
          ? recente
          : await Geolocator.getCurrentPosition(
              desiredAccuracy: LocationAccuracy.high,
              timeLimit: const Duration(seconds: 20),
            );
      if (_viagem == null || geracao != _geracao) return;
      velocidade = p.speed.isFinite && p.speed >= 0 ? p.speed : 0;
      if (!p.accuracy.isFinite || p.accuracy < 0 || p.accuracy > 100) {
        throw ApiException(
          'Sinal de GPS impreciso. Vá para uma área aberta e habilite a localização precisa.',
        );
      }
      final inicio = DateTime.tryParse('${_viagem!['iniciada_em']}');
      if (inicio != null && p.timestamp.isBefore(inicio)) {
        throw ApiException('Aguardando uma posição recente.');
      }
      if (_ultimaCaptura != null && !p.timestamp.isAfter(_ultimaCaptura!)) {
        throw ApiException('Aguardando uma nova posição do GPS.');
      }
      _ultimaCaptura = p.timestamp;
      final anterior = _ultimaEnfileirada;
      if (anterior != null &&
          Geolocator.distanceBetween(
                anterior.latitude,
                anterior.longitude,
                p.latitude,
                p.longitude,
              ) <
              15 &&
          p.timestamp.difference(anterior.timestamp) <
              const Duration(seconds: 60)) {
        return;
      }
      final posicao = <String, dynamic>{
        'latitude': p.latitude.toStringAsFixed(6),
        'longitude': p.longitude.toStringAsFixed(6),
        'precisao_metros': p.accuracy.toStringAsFixed(2),
        'capturada_em': p.timestamp.toUtc().toIso8601String(),
        'velocidade': velocidade,
      };
      _ultimaEnfileirada = p;
      _lote.add(posicao);
      if (_lote.length >= 3) {
        await enviarLote();
      } else {
        _timerLote ??= Timer(const Duration(seconds: 30), () {
          _timerLote = null;
          unawaited(enviarLote());
        });
      }
    } catch (e) {
      if (geracao == _geracao) {
        erro = e is TimeoutException
            ? 'O GPS ainda não encontrou uma posição. Confira o sinal e a permissão de localização precisa.'
            : ApiService.mensagemErro(e);
      }
    } finally {
      _capturando = false;
      if (_viagem != null && geracao == _geracao) {
        intervalo = _viagem!['etapa'] == 'no_destino' ? 60 : 10;
        notifyListeners();
        _timer = Timer(
          Duration(seconds: erro != null ? 20 : intervalo),
          () => _capturar(geracao),
        );
      }
    }
  }

  Future<void> _manterFluxo(int geracao) async {
    if (kIsWeb ||
        ![
          TargetPlatform.android,
          TargetPlatform.iOS,
        ].contains(defaultTargetPlatform)) {
      return;
    }
    if (_fluxo != null && _intervaloFluxo == intervalo) return;
    await _fluxo?.cancel();
    if (geracao != _geracao || _viagem == null) return;
    final LocationSettings configuracao =
        defaultTargetPlatform == TargetPlatform.android
        ? AndroidSettings(
            accuracy: LocationAccuracy.high,
            distanceFilter: 15,
            intervalDuration: Duration(seconds: intervalo),
            foregroundNotificationConfig: const ForegroundNotificationConfig(
              notificationTitle: 'Viagem UNICAP em andamento',
              notificationText:
                  'A localização do ônibus está sendo compartilhada durante a viagem.',
              enableWakeLock: true,
            ),
          )
        : AppleSettings(
            accuracy: LocationAccuracy.high,
            distanceFilter: 15,
            activityType: ActivityType.automotiveNavigation,
            pauseLocationUpdatesAutomatically: false,
            showBackgroundLocationIndicator: true,
            allowBackgroundLocationUpdates: true,
          );
    _intervaloFluxo = intervalo;
    _fluxo = Geolocator.getPositionStream(locationSettings: configuracao)
        .listen(
          (p) {
            if (geracao == _geracao) _ultimaPosicao = p;
          },
          onError: (Object e) {
            if (geracao == _geracao) {
              erro = ApiService.mensagemErro(e);
              _fluxo?.cancel();
              _fluxo = null;
              notifyListeners();
            }
          },
        );
  }
}
