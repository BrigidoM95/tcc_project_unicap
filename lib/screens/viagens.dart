import 'dart:async';
import 'package:flutter/material.dart';
import '../login.dart';
import '../services/api_service.dart';
import '../services/fila_offline.dart';
import '../services/rastreamento.dart';
import '../ui/componentes.dart';
import '../ui/tema.dart';
import 'associado/fluxo.dart';
import 'associado/historico_v3.dart';
import 'fiscal/fluxo.dart';
import 'motorista/viagem.dart';

class ViagensHoje extends StatefulWidget {
  final Dados usuario;
  final String token;
  const ViagensHoje({super.key, required this.usuario, required this.token});
  @override
  State<ViagensHoje> createState() => _ViagensHojeState();
}

class _ViagensHojeState extends State<ViagensHoje> {
  List<Dados> viagens = [];
  String? erro;
  bool carregando = true, buscando = false;
  int sentido = 0, aba = 0;
  Timer? timer;
  String get perfil => '${widget.usuario['tipo']}';
  String get caminho =>
      'api/viagens/hoje/${perfil == 'associado' ? '?sentido=${sentido == 0 ? 'ida' : 'retorno'}' : ''}';
  @override
  void initState() {
    super.initState();
    carregar();
    FilaOffline.instancia.addListener(mudouFila);
    timer = Timer.periodic(const Duration(seconds: 2), (_) => carregar());
  }

  void mudouFila() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    timer?.cancel();
    FilaOffline.instancia.removeListener(mudouFila);
    super.dispose();
  }

  Future<void> carregar() async {
    if (buscando) return;
    buscando = true;
    final consulta = caminho;
    try {
      final d = await ApiService.requisicao(
        consulta,
        widget.token,
        cache: true,
      );
      if (!mounted || consulta != caminho) return;
      if (perfil == 'motorista' && ApiService.avisosCache[consulta] == null) {
        final pendente = FilaOffline.instancia.itens.any(
          (e) => e['tipo'] == 'transicao' && e['estado'] == 'pendente',
        );
        if (!pendente) {
          final ativas = mapas(
            d['viagens'],
          ).where((v) => v['status'] == 'em_andamento');
          if (ativas.isNotEmpty) {
            Rastreamento.instancia.atualizar(ativas.first, widget.token);
          } else if (Rastreamento.instancia.ativo) {
            Rastreamento.instancia.parar();
          }
        }
      }
      setState(() {
        viagens = mapas(d['viagens']);
        erro = null;
      });
    } catch (e) {
      if (mounted) setState(() => erro = ApiService.mensagemErro(e));
    } finally {
      buscando = false;
      if (mounted) setState(() => carregando = false);
    }
  }

  Future<void> abrir(Dados v) async {
    final Widget tela = switch (perfil) {
      'motorista' => ViagemMotorista(
        viagem: v,
        token: widget.token,
        usuario: widget.usuario,
      ),
      'fiscal' => FluxoFiscal(
        viagem: v,
        token: widget.token,
        usuario: widget.usuario,
      ),
      _ => DetalheAssociado(viagem: v, token: widget.token),
    };
    await Navigator.push(context, MaterialPageRoute(builder: (_) => tela));
    if (mounted) carregar();
  }

  Future<void> sair() async {
    if (perfil == 'motorista' &&
        viagens.any((v) => v['status'] == 'em_andamento')) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Finalize a viagem antes de sair.')),
      );
      return;
    }
    FilaOffline.instancia.parar();
    Rastreamento.instancia.parar();
    await ApiService.sair();
    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const Login()),
      (_) => false,
    );
  }

  Future<void> assumir(Dados v) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Assumir esta viagem?'),
        content: Text(
          'Você será responsável pelo embarque do ${v['onibus_nome']}.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('Cancelar'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('Assumir'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await ApiService.requisicao(
        'api/viagens/${v['id']}/assumir/',
        widget.token,
        corpo: {},
      );
      await carregar();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(ApiService.mensagemErro(e))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final historico =
        perfil == 'associado' ||
        (perfil == 'fiscal' && widget.usuario['estudante'] == true);
    if (aba == 1) {
      return HistoricoV3(
        token: widget.token,
        onViagens: () => setState(() => aba = 0),
      );
    }
    return TelaUnicap(
      titulo: perfil == 'motorista'
          ? 'Minhas viagens'
          : perfil == 'fiscal'
          ? 'Ônibus do dia'
          : 'Ônibus disponíveis',
      saudacao: 'Olá, ${nomeCurto(widget.usuario)}',
      subtitulo:
          '${dataHoje()} • ${perfil == 'associado'
              ? 'rotas que atendem a ${widget.usuario['instituicao'] ?? 'sua instituição'}'
              : perfil == 'fiscal'
              ? 'Fiscal'
              : 'Motorista'}',
      topoAcao: PopupMenuButton<String>(
        tooltip: 'Opções da conta',
        icon: const CircleAvatar(
          backgroundColor: Colors.white,
          child: Icon(Icons.logout, color: azulUnibus, size: 21),
        ),
        onSelected: (s) {
          if (s == 'sair') {
            sair();
          }
        },
        itemBuilder: (_) => [
          const PopupMenuItem(value: 'sair', child: Text('Sair')),
        ],
      ),
      rodape: historico
          ? BarraAbas(indice: 0, onChanged: (i) => setState(() => aba = i))
          : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (perfil == 'associado') ...[
            Seletor(
              itens: [
                'Ida${viagens.isNotEmpty ? ' • ${viagens.first['horario_ida']}' : ''}',
                'Volta${viagens.isNotEmpty ? ' • ${viagens.first['horario_retorno']}' : ''}',
              ],
              selecionado: sentido,
              onChanged: (i) {
                setState(() => sentido = i);
                carregar();
              },
            ),
            const SizedBox(height: 12),
          ],
          if (carregando) const Center(child: CircularProgressIndicator()),
          if (erro != null) ...[
            Aviso(erro!),
            Botao('Tentar novamente', contorno: true, onPressed: carregar),
          ],
          if (ApiService.avisosCache[caminho] != null)
            Aviso(
              'Sem internet • última atualização ${hora(ApiService.avisosCache[caminho]!.toIso8601String())}.',
            ),
          if (perfil == 'motorista') const TituloSecao('Hoje'),
          if (perfil == 'fiscal') const TituloSecao('Sob sua responsabilidade'),
          for (final v in viagens.where(
            (v) => perfil != 'fiscal' || v['fiscal_id'] != null,
          ))
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: cartao(v),
            ),
          if (perfil == 'fiscal' &&
              viagens.any((v) => v['fiscal_id'] == null)) ...[
            const TituloSecao('Rotas de hoje sem fiscal'),
            for (final v in viagens.where((v) => v['fiscal_id'] == null))
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: cartao(v, semFiscal: true),
              ),
          ],
          if (!carregando && erro == null && viagens.isEmpty)
            const Aviso(
              'Nenhuma viagem disponível para hoje. Confira as rotas com a administração.',
            ),
          if (viagens.isNotEmpty)
            Text(
              perfil == 'motorista'
                  ? 'Só aparecem as viagens em que você é o motorista.'
                  : 'Atualizado agora • ocupação em tempo real',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 10, color: cinzaUnicap),
            ),
        ],
      ),
    );
  }

  Widget cartao(Dados v, {bool semFiscal = false}) {
    final pendente = FilaOffline.instancia.checkin(
      v['id'] as int,
      '${v['sentido']}',
    );
    final lotado = (v['vagas_disponiveis'] as num? ?? 0) == 0;
    final estado = pendente?['estado'] == 'pendente'
        ? 'Check-in pendente'
        : v['meu_embarque'] != null
        ? 'Você embarcou • poltrona ${v['meu_embarque']['poltrona']}'
        : semFiscal
        ? 'Sem fiscal'
        : v['status'] == 'finalizada'
        ? 'Encerrada'
        : v['embarque_aberto'] == true
        ? 'Embarque ${perfil == 'fiscal' ? 'da ${sentidoNome(v['sentido']).toLowerCase()} ' : ''}aberto'
        : v['etapa'] == 'agendada'
        ? (perfil == 'motorista' && v['pode_iniciar'] == true
              ? 'Pronta para iniciar'
              : 'Aguardando motorista')
        : v['etapa_nome'].toString();
    return InkWell(
      onTap: semFiscal ? null : () => abrir(v),
      borderRadius: BorderRadius.circular(16),
      child: Cartao(
        borda: perfil == 'motorista' && v['pode_iniciar'] == true
            ? laranjaUnibus
            : null,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                SizedBox(width: 88, child: FotoOnibus(v, altura: 65)),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${v['onibus_nome']}',
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Etiqueta(
                        lotado &&
                                perfil == 'associado' &&
                                v['meu_embarque'] == null
                            ? 'Lotado'
                            : estado,
                        cor: lotado ? vermelhoUnicap : azulUnibus,
                        fundo: lotado
                            ? const Color(0xFFFDEDEB)
                            : const Color(0xFFEDF0F4),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        'para ${v['destino']} • ${perfil == 'motorista' ? v['rota_nome'] : 'saída ${v['sentido'] == 'retorno' ? v['horario_retorno'] : v['horario_ida']}'}',
                        style: const TextStyle(
                          fontSize: 10,
                          color: cinzaUnicap,
                        ),
                      ),
                    ],
                  ),
                ),
                if (!semFiscal) const Icon(Icons.chevron_right, size: 20),
              ],
            ),
            if (perfil == 'motorista') ...[
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Saída\n${v['horario_ida']}'),
                  Text('Retorno\n${v['horario_retorno']}'),
                  Text('Placa\n${v['placa']}'),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                'Fiscal: ${v['fiscal_nome'] ?? 'Sem fiscal'}',
                style: const TextStyle(fontSize: 11),
              ),
              const SizedBox(height: 6),
              Text(
                v['status'] == 'finalizada'
                    ? 'Ida ${hora(v['partida_ida_em'])}–${hora(v['chegada_em'])} • volta ${hora(v['partida_volta_em'])}–${hora(v['finalizada_em'])}'
                    : 'Iniciar rota liberado ${v['pode_iniciar'] == true ? 'desde' : 'a partir de'} ${hora(v['liberada_em'])}',
                style: const TextStyle(fontSize: 10, color: cinzaUnicap),
              ),
            ] else if (semFiscal) ...[
              const SizedBox(height: 10),
              const Text(
                'Sem fiscal, ninguém consegue embarcar neste ônibus.',
                style: TextStyle(fontSize: 11, color: cinzaUnicap),
              ),
              const SizedBox(height: 12),
              Botao(
                'Assumir esta viagem',
                contorno: true,
                icone: Icons.person_add_alt,
                onPressed: () => assumir(v),
              ),
            ] else ...[
              if (v['proximo_ponto'] != null) ...[
                const SizedBox(height: 10),
                Text(
                  '⌖ Próximo ponto: ${v['proximo_ponto']}',
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
              if (perfil == 'fiscal')
                Text(
                  'Motorista: ${v['motorista_nome']}',
                  style: const TextStyle(fontSize: 10, color: cinzaUnicap),
                ),
              Ocupacao(v),
            ],
          ],
        ),
      ),
    );
  }
}
