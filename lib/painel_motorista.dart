import 'screens/mapa.dart';
import 'screens/alterar_senha.dart';
import 'package:flutter/material.dart';
import 'dart:async';
import 'home.dart';
import 'login.dart';
import 'services/api_service.dart';
import 'package:geolocator/geolocator.dart';

class PainelMotorista extends StatefulWidget {
  final Map<String, dynamic> usuario;
  final String accessToken;

  const PainelMotorista({
    super.key,
    required this.usuario,
    required this.accessToken,
  });

  @override
  State<PainelMotorista> createState() => _PainelMotoristaState();
}

class _PainelMotoristaState extends State<PainelMotorista>
    with WidgetsBindingObserver {
  bool carregando = true;
  bool enviando = false;
  String? erro;
  Timer? _timerGps;
  int _geracaoGps = 0;
  bool _gpsAtivo = false;
  bool _capturaEmCurso = false;

  String _mensagemGps = 'Localização não iniciada.';
  String? _erroGps;
  DateTime? _ultimoEnvioGps;
  double? _precisaoGps;

  List<Map<String, dynamic>> rotas = [];
  Map<String, dynamic>? viagem;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    carregar();
  }

  bool get _paginaAtiva {
    final estado = WidgetsBinding.instance.lifecycleState;
    return estado == null || estado == AppLifecycleState.resumed;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (mounted && !carregando && !enviando) {
        // Confere se a viagem ainda está em andamento
        // antes de retomar a localização.
        unawaited(carregar());
      }
    } else {
      _pararGps();

      if (mounted) {
        setState(() {
          _mensagemGps = 'Localização pausada: painel fora de foco.';
        });
      }
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pararGps();
    super.dispose();
  }

  void _pararGps() {
    _timerGps?.cancel();
    _timerGps = null;
    _gpsAtivo = false;

    // Invalida resultados de capturas anteriores.
    _geracaoGps++;
  }

  bool _gpsValido(int geracao, int viagemId) {
    return mounted &&
        _gpsAtivo &&
        _paginaAtiva &&
        geracao == _geracaoGps &&
        viagem?['id'] == viagemId;
  }

  void _iniciarGps() {
    _pararGps();

    final atual = viagem;
    if (!mounted || atual == null || !_paginaAtiva) return;

    final viagemId = (atual['id'] as num).toInt();
    final geracao = _geracaoGps;

    setState(() {
      _gpsAtivo = true;
      _erroGps = null;
      _mensagemGps = 'Obtendo localização...';
    });

    unawaited(_capturarEEnviar(geracao, viagemId));
  }

  Future<void> _capturarEEnviar(int geracao, int viagemId) async {
    if (!_gpsValido(geracao, viagemId)) return;

    // Evita capturas simultâneas ao atualizar o painel.
    if (_capturaEmCurso) {
      _timerGps = Timer(
        const Duration(seconds: 2),
        () => unawaited(_capturarEEnviar(geracao, viagemId)),
      );
      return;
    }

    _capturaEmCurso = true;

    try {
      final servicoAtivo = await Geolocator.isLocationServiceEnabled();

      if (!_gpsValido(geracao, viagemId)) return;

      if (!servicoAtivo) {
        throw Exception(
          'Ative a localização do dispositivo e tente novamente.',
        );
      }

      var permissao = await Geolocator.checkPermission();

      if (!_gpsValido(geracao, viagemId)) return;

      if (permissao == LocationPermission.denied) {
        permissao = await Geolocator.requestPermission();
      }

      if (!_gpsValido(geracao, viagemId)) return;

      if (permissao == LocationPermission.denied ||
          permissao == LocationPermission.deniedForever) {
        throw Exception(
          'Permita o acesso à localização nas configurações '
          'do navegador ou dispositivo e tente novamente.',
        );
      }

      final posicao = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 20),
      );

      if (!_gpsValido(geracao, viagemId)) return;

      final inicio = DateTime.parse(viagem!['iniciada_em'].toString()).toUtc();

      final captura = posicao.timestamp.toUtc();
      final agora = DateTime.now().toUtc();

      // Não troca o horário real da leitura pelo horário
      // do envio: uma posição antiga deve ser descartada.
      if (captura.isBefore(inicio) ||
          captura.isBefore(agora.subtract(const Duration(minutes: 2)))) {
        setState(() {
          _mensagemGps =
              'Aguardando uma leitura de localização mais recente...';
        });
        return;
      }

      if (!posicao.latitude.isFinite || !posicao.longitude.isFinite) {
        throw Exception('O dispositivo retornou coordenadas inválidas.');
      }

      final resposta = await ApiService.enviarLocalizacao(
        viagemId: viagemId,
        token: widget.accessToken,
        latitude: posicao.latitude,
        longitude: posicao.longitude,
        precisaoMetros: posicao.accuracy,
        capturadaEm: captura,
      );

      if (!_gpsValido(geracao, viagemId)) return;

      setState(() {
        _ultimoEnvioGps = DateTime.parse(
          resposta['recebida_em'].toString(),
        ).toLocal();

        _precisaoGps = (resposta['precisao_metros'] as num?)?.toDouble();

        _erroGps = null;
        _mensagemGps = 'Localização recebida pelo servidor.';
      });
    } catch (e) {
      if (!_gpsValido(geracao, viagemId)) return;

      _pararGps();

      setState(() {
        _mensagemGps = 'Envio de localização interrompido.';
        _erroGps = e is TimeoutException
            ? 'Tempo esgotado ao obter ou enviar a localização. '
                  'Confira o sinal e a conexão.'
            : ApiService.mensagemErro(e);
      });
    } finally {
      _capturaEmCurso = false;

      if (_gpsValido(geracao, viagemId)) {
        // Aguarda 10 segundos após concluir a tentativa.
        _timerGps = Timer(
          const Duration(seconds: 10),
          () => unawaited(_capturarEEnviar(geracao, viagemId)),
        );
      }
    }
  }

  Future<void> carregar() async {
    if (!mounted) return;

    _pararGps();

    setState(() {
      carregando = true;
      erro = null;
    });

    try {
      final dados = await ApiService.painelMotorista(widget.accessToken);

      if (dados['motorista'] != true) {
        throw Exception('Acesso exclusivo para motoristas ativos.');
      }

      final lista = (dados['rotas'] as List)
          .map((item) => Map<String, dynamic>.from(item as Map))
          .toList();

      final atual = dados['viagem'];
      final novaViagem = atual == null
          ? null
          : Map<String, dynamic>.from(atual as Map);

      if (!mounted) return;

      final mudouViagem = viagem?['id'] != novaViagem?['id'];

      setState(() {
        rotas = lista;
        viagem = novaViagem;
        carregando = false;

        if (mudouViagem) {
          _ultimoEnvioGps = null;
          _precisaoGps = null;
          _erroGps = null;
        }

        _mensagemGps = viagem == null
            ? 'Nenhuma viagem em andamento.'
            : 'Aguardando localização.';
      });

      if (viagem != null) {
        _iniciarGps();
      }
    } catch (e) {
      if (!mounted) return;

      setState(() {
        erro = ApiService.mensagemErro(e);
        carregando = false;
        _mensagemGps = 'Localização parada até confirmar a viagem no servidor.';
      });
    }
  }

  Future<void> executar(
    Future<Map<String, dynamic>> Function() operacao,
    String mensagem,
  ) async {
    if (enviando || carregando) return;
    _pararGps();

    setState(() => enviando = true);

    try {
      await operacao();

      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(mensagem)));
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(ApiService.mensagemErro(e))));
    } finally {
      // Consulta novamente mesmo após falha de rede:
      // a operação pode ter sido concluída pelo servidor.
      if (mounted) {
        await carregar();

        if (mounted) {
          setState(() => enviando = false);
        }
      }
    }
  }

  Future<void> confirmarFinalizacao() async {
    final atual = viagem;
    if (atual == null || enviando || carregando) return;

    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Finalizar viagem?'),
        content: const Text(
          'Confirme somente quando este percurso tiver terminado.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Finalizar'),
          ),
        ],
      ),
    );

    if (confirmar != true || !mounted) return;

    await executar(
      () => ApiService.finalizarViagem(
        (atual['id'] as num).toInt(),
        widget.accessToken,
      ),
      'Viagem finalizada.',
    );
  }

  String formatarHorario(dynamic valor) {
    final data = DateTime.tryParse(valor?.toString() ?? '')?.toLocal();

    if (data == null) return '-';

    String dois(int numero) => numero.toString().padLeft(2, '0');

    return '${dois(data.day)}/${dois(data.month)}/${data.year} '
        '${dois(data.hour)}:${dois(data.minute)}';
  }

  void sair() {
    _pararGps();
    unawaited(ApiService.sair());

    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const Login()),
      (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final ocupado = carregando || enviando;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Minhas viagens'),
        backgroundColor: const Color(0xFF1C3B6E),
        foregroundColor: Colors.white,
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Mais opções',
            enabled: !ocupado,
            itemBuilder: (_) => [
              const PopupMenuItem(
                value: 'mapa',
                child: Text('Acompanhar viagens'),
              ),
              PopupMenuItem(
                value: 'onibus',
                enabled: viagem == null,
                child: const Text('Consultar ônibus'),
              ),
              PopupMenuItem(
                value: 'senha',
                enabled: viagem == null,
                child: const Text('Alterar senha'),
              ),
            ],
            onSelected: (opcao) async {
              final Widget destino = switch (opcao) {
                'mapa' => MapaViagens(accessToken: widget.accessToken),
                'senha' => AlterarSenha(accessToken: widget.accessToken),
                _ => Home(
                  usuario: widget.usuario,
                  accessToken: widget.accessToken,
                ),
              };
              await Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => destino),
              );
              if (mounted) carregar();
            },
          ),
          IconButton(
            tooltip: 'Atualizar',
            onPressed: ocupado ? null : carregar,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Sair',
            onPressed: ocupado ? null : sair,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: carregando
          ? const Center(child: CircularProgressIndicator())
          : erro != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(erro!, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    ElevatedButton(
                      onPressed: enviando ? null : carregar,
                      child: const Text('Tentar novamente'),
                    ),
                  ],
                ),
              ),
            )
          : RefreshIndicator(
              onRefresh: () async {
                if (!enviando) await carregar();
              },
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(20),
                children: [
                  if (enviando) const LinearProgressIndicator(),
                  Text(
                    'Olá, ${widget.usuario['nome'] ?? 'motorista'}',
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (viagem != null)
                    _cartaoViagem()
                  else ...[
                    const Text('Selecione a rota e o sentido para iniciar.'),
                    const SizedBox(height: 16),
                    if (rotas.isEmpty)
                      const Text(
                        'Nenhuma rota ativa vinculada ao seu ônibus. '
                        'Solicite a conferência do cadastro ao administrador.',
                      ),
                    ...rotas.map(_cartaoRota),
                  ],
                ],
              ),
            ),
    );
  }

  Widget _cartaoViagem() {
    final atual = viagem!;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Viagem em andamento',
              style: TextStyle(
                fontSize: 22,
                color: Colors.green,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text('Rota: ${atual['rota_nome']}'),
            Text('Ônibus: ${atual['onibus_codigo']} — ${atual['placa']}'),
            Text('Sentido: ${atual['sentido'] == 'ida' ? 'Ida' : 'Retorno'}'),
            Text('Início: ${formatarHorario(atual['iniciada_em'])}'),
            const SizedBox(height: 16),
            _situacaoGps(),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: enviando ? null : confirmarFinalizacao,
              icon: const Icon(Icons.stop_circle_outlined),
              label: const Text('Finalizar viagem'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _cartaoRota(Map<String, dynamic> rota) {
    final id = (rota['id'] as num).toInt();

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              rota['nome'].toString(),
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text('${rota['origem']} → ${rota['destino']}'),
            Text('Ônibus: ${rota['onibus_codigo']} — ${rota['placa']}'),
            Text(
              'Previsão: ida ${rota['horario_ida']} '
              '/ retorno ${rota['horario_retorno']}',
            ),
            const SizedBox(height: 16),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                ElevatedButton(
                  onPressed: enviando
                      ? null
                      : () => executar(
                          () => ApiService.iniciarViagem(
                            id,
                            'ida',
                            widget.accessToken,
                          ),
                          'Viagem de ida iniciada.',
                        ),
                  child: const Text('Iniciar ida'),
                ),
                ElevatedButton(
                  onPressed: enviando
                      ? null
                      : () => executar(
                          () => ApiService.iniciarViagem(
                            id,
                            'retorno',
                            widget.accessToken,
                          ),
                          'Viagem de retorno iniciada.',
                        ),
                  child: const Text('Iniciar retorno'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _situacaoGps() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: _erroGps == null ? Colors.blue.shade50 : Colors.orange.shade50,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                _gpsAtivo ? Icons.location_on : Icons.location_off,
                color: _erroGps == null ? Colors.blue : Colors.orange,
              ),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Localização da viagem',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(_mensagemGps),
          if (_ultimoEnvioGps != null)
            Text(
              'Último recebimento: '
              '${formatarHorario(_ultimoEnvioGps!.toIso8601String())}'
              ':${_ultimoEnvioGps!.second.toString().padLeft(2, '0')}',
            ),
          if (_precisaoGps != null)
            Text(
              'Margem de precisão informada: '
              '${_precisaoGps!.toStringAsFixed(1)} m',
            ),
          if (_erroGps != null) ...[
            const SizedBox(height: 8),
            Text(_erroGps!, style: const TextStyle(color: Colors.red)),
          ],
          const SizedBox(height: 8),
          const Text(
            'Mantenha este painel aberto e ativo para enviar '
            'a localização. Sair não finaliza a viagem.',
          ),
          if (!_gpsAtivo)
            TextButton.icon(
              onPressed: carregando || enviando ? null : carregar,
              icon: const Icon(Icons.refresh),
              label: const Text('Verificar viagem e tentar novamente'),
            ),
        ],
      ),
    );
  }
}
