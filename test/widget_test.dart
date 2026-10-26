import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:aulas_flutter/login.dart';
import 'package:aulas_flutter/screens/viagens.dart';
import 'package:aulas_flutter/screens/associado/fluxo.dart';
import 'package:aulas_flutter/screens/associado/historico_v3.dart';
import 'package:aulas_flutter/screens/fiscal/fluxo.dart';
import 'package:aulas_flutter/screens/motorista/viagem.dart';
import 'package:aulas_flutter/services/api_service.dart';
import 'package:aulas_flutter/services/armazenamento.dart';
import 'package:aulas_flutter/services/fila_offline.dart';
import 'package:aulas_flutter/services/rastreamento.dart';
import 'package:aulas_flutter/ui/tema.dart';

final usuario = <String, dynamic>{
  'id': 1,
  'nome': 'Maria Souza',
  'tipo': 'associado',
  'instituicao': 'UNIGRAN',
  'estudante': true,
};
Map<String, dynamic> viagem() => {
  'id': 1,
  'rota_id': 1,
  'rota_nome': 'Noturno',
  'destino': 'Dourados',
  'onibus_nome': 'Ônibus 01',
  'onibus_codigo': 'ONI000001',
  'placa': 'ABC1D23',
  'foto': '',
  'motorista_nome': 'João Silva',
  'fiscal_id': 2,
  'fiscal_nome': 'Carlos Lima',
  'horario_ida': '17:40',
  'horario_retorno': '22:30',
  'etapa': 'embarque_ida',
  'etapa_nome': 'Embarque da ida',
  'status': 'em_andamento',
  'data': '2026-10-15',
  'sentido': 'ida',
  'embarque_aberto': true,
  'capacidade': 46,
  'presentes': 30,
  'reservados': 2,
  'ocupados': 32,
  'vagas_disponiveis': 14,
  'total_ida': 30,
  'total_retorno': 0,
  'proximo_ponto': null,
  'escolha_aberta': true,
  'escolha_abre_em': '2026-10-18T08:00:00-04:00',
  'pode_iniciar_volta': true,
  'pode_iniciar': true,
  'liberada_em': DateTime.now()
      .subtract(const Duration(hours: 1))
      .toIso8601String(),
  'iniciada_em': DateTime.now()
      .subtract(const Duration(minutes: 10))
      .toIso8601String(),
  'atualizado_em': DateTime.now().toIso8601String(),
  'pontos': [
    {'id': 1, 'nome': 'Praça Central', 'sentido': 'ida', 'ordem': 1},
    {'id': 2, 'nome': 'UNIGRAN', 'sentido': 'retorno', 'ordem': 1},
  ],
  'localizacao': null,
};
Map<String, dynamic> registro() => {
  'id': 1,
  'viagem_id': 1,
  'nome': 'Maria Souza',
  'rua': '802.023',
  'poltrona': 12,
  'ponto_nome': 'Praça Central',
  'rota_nome': 'Caarapó → Dourados',
  'origem': 'qr',
  'sentido': 'ida',
  'onibus_nome': 'Ônibus 01',
  'onibus_codigo': 'ONI000001',
  'data': DateTime.now().toIso8601String(),
  'registrado_em': DateTime.now().toIso8601String(),
  'comprovante': 'EMB-00001',
  'cancelado': false,
};
Map<String, dynamic> atual = viagem();
Map<String, dynamic>? ultimaEscolha;
String? ultimoTrajeto;
final capturas = GlobalKey();
Future<void> abrir(WidgetTester t, Widget w, {double largura = 390}) async {
  await t.pumpWidget(const SizedBox.shrink());
  t.view.physicalSize = Size(largura, 844);
  t.view.devicePixelRatio = 1;
  await t.pumpWidget(
    RepaintBoundary(
      key: capturas,
      child: MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: temaUnibus(),
        home: w,
      ),
    ),
  );
  for (var i = 0; i < 5; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
  await t.runAsync(() async {
    await precacheImage(
      const AssetImage('assets/logo_unicap.png'),
      capturas.currentContext!,
    );
    await precacheImage(
      const AssetImage('assets/onibus_referencia.png'),
      capturas.currentContext!,
    );
  });
  await t.pump();
  expect(t.takeException(), isNull);
}

Future<void> salvar(WidgetTester t, String nome) async {
  if (!const bool.fromEnvironment('CAPTURAR_TELAS')) return;
  await t.pump(const Duration(milliseconds: 500));
  await t.runAsync(() async {
    final boundary =
        capturas.currentContext!.findRenderObject() as RenderRepaintBoundary;
    final image = await boundary.toImage();
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    final f = File('tmp/telas/$nome.png');
    await f.parent.create(recursive: true);
    await f.writeAsBytes(data!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final font = FontLoader('DejaVuSans')
      ..addFont(rootBundle.load('assets/fonts/DejaVuSans.ttf'))
      ..addFont(rootBundle.load('assets/fonts/DejaVuSans-Bold.ttf'));
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });
  setUp(() async {
    final messenger =
        TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(
      const MethodChannel('dev.steenbakker.mobile_scanner/scanner/event'),
      (call) async => null,
    );
    // Simula indisponibilidade de câmera no host de widgets; testa a mensagem dentro do visor.
    messenger.setMockMethodCallHandler(
      const MethodChannel('dev.steenbakker.mobile_scanner/scanner/method'),
      (call) async {
        if (call.method == 'state') return 0;
        if (call.method == 'request') return false;
        return null;
      },
    );
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('flutter.baseflow.com/geolocator_updates'),
          (c) async => null,
        );
    atual = viagem();
    ultimaEscolha = null;
    ultimoTrajeto = null;
    Armazenamento.emMemoria = true;
    await Armazenamento.apagar('sessao');
    ApiService.usarClienteTeste(
      MockClient((r) async {
        Object d = {};
        if (r.url.path == '/api/login/') {
          d = {'access': 'teste', 'refresh': 'refresh', 'usuario': usuario};
        } else if (r.url.path.contains('/associados/')) {
          d = {
            'associados': [
              {...usuario, 'rua': '802.023', 'curso': 'Computação'},
            ],
          };
        } else if (r.url.path.contains('hoje')) {
          d = {
            'viagens': [
              atual,
              {
                ...atual,
                'id': 2,
                'onibus_nome': 'Ônibus 02',
                'ocupados': 46,
                'vagas_disponiveis': 0,
              },
            ],
          };
        } else if (r.url.path.contains('assentos')) {
          ultimoTrajeto = r.url.queryParameters['trajeto'];
          d = {
            'viagem': atual,
            'assentos': List.generate(
              atual['capacidade'] as int,
              (i) => {'numero': i + 1, 'estado': i < 8 ? 'ocupada' : 'livre'},
            ),
          };
        } else if (r.url.path.contains('qr-do-dia')) {
          d = {
            'viagem': atual,
            'codigo': 'UNICAP:V3:QR-de-teste',
            'gerado_em': DateTime.now().toIso8601String(),
            'expira_em': DateTime.now()
                .add(const Duration(hours: 4))
                .toIso8601String(),
          };
        } else if (r.url.path == '/api/me/embarques/') {
          d = {
            'checkins': [
              registro(),
              {...registro(), 'sentido': 'retorno'},
            ],
            'frequencia': {
              'dias': 12,
              'idas': 12,
              'voltas': 11,
              'dias_com_viagem': 14,
            },
          };
        } else if (r.url.path.contains('embarques')) {
          d = {
            'viagem': atual,
            'checkins': [
              registro(),
              {...registro(), 'nome': 'Ana Oliveira', 'poltrona': 3},
            ],
          };
        } else if (r.url.path.endsWith('/minha-escolha/') &&
            r.method == 'DELETE') {
          atual = {...atual, 'minha_escolha': null, 'minha_reserva': null};
          d = atual;
        } else if (r.url.path.contains('reservas')) {
          ultimaEscolha = Map<String, dynamic>.from(jsonDecode(r.body) as Map);
          final reserva = {
            'id': 1,
            'poltrona': ultimaEscolha!['poltrona'],
            'sentido': atual['sentido'],
            'ponto_id': 1,
            'ponto_nome': 'Praça Central',
            'expira_em': DateTime.now()
                .add(const Duration(hours: 10))
                .toIso8601String(),
          };
          d = {
            'viagem': atual,
            'reserva': reserva,
            'reservas': [reserva],
          };
        } else {
          d = atual;
        }
        return http.Response(
          jsonEncode(d),
          200,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
    await ApiService.login('802.023', 'senha');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
          const MethodChannel('flutter.baseflow.com/geolocator'),
          (c) async {
            if (c.method == 'isLocationServiceEnabled') return true;
            if (c.method == 'checkPermission') return 3;
            throw PlatformException(
              code: 'indisponivel',
              message: 'Aguardando localização',
            );
          },
        );
  });
  tearDown(() {
    FilaOffline.instancia.parar();
    Rastreamento.instancia.parar();
    ApiService.encerrarSessao();
  });
  testWidgets('Login aceita RUA, oculta senha e valida campos', (t) async {
    await abrir(t, const Login());
    await salvar(t, '01-login');
    expect(find.text('Acesse sua conta'), findsOneWidget);
    expect(find.text('E-mail ou RUA'), findsOneWidget);
    await t.tap(find.text('Entrar'));
    await t.pump();
    expect(find.text('Informe o e-mail ou RUA e a senha.'), findsOneWidget);
    await t.enterText(find.byType(TextField).first, '802.023');
    await t.enterText(find.byType(TextField).last, 'Segredo');
    expect(t.widget<TextField>(find.byType(TextField).last).obscureText, true);
    await t.tap(find.byTooltip('Exibir senha'));
    await t.pump();
    expect(t.widget<TextField>(find.byType(TextField).last).obscureText, false);
  });
  testWidgets('Telas do associado em 390 px e reserva de poltrona', (t) async {
    await abrir(t, ViagensHoje(usuario: usuario, token: 'teste'));
    await salvar(t, '02-associado-onibus');
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    await salvar(t, '03-associado-detalhe');
    await abrir(t, SelecionarPoltrona(viagem: atual, token: 'teste'));
    final livres = find.text('12');
    expect(livres, findsOneWidget);
    await t.tap(livres);
    await t.pump();
    await salvar(t, '04-associado-poltronas');
    await t.tap(find.text('Confirmar poltrona 12'));
    await t.pump(const Duration(milliseconds: 400));
    await t.pump();
    expect(find.text('Ler QR Code'), findsOneWidget);
    expect(find.text('Rota'), findsNothing);
    expect(find.text('Sentido'), findsNothing);
    expect(find.textContaining('reservado por'), findsNothing);
    expect(find.text('Sua poltrona 12'), findsOneWidget);
    expect(ultimaEscolha, containsPair('trajeto', 'ida_volta'));
    expect(ultimaEscolha, containsPair('ponto_ida_id', 1));
    expect(ultimaEscolha, containsPair('ponto_volta_id', 2));
    await salvar(t, '05-associado-confirmar');
    await t.pumpWidget(const SizedBox.shrink());
    await abrir(t, ComprovanteEmbarque(viagem: atual, checkin: registro()));
    await salvar(t, '06-associado-comprovante');
    await abrir(
      t,
      OnibusLotado(
        viagem: {
          ...atual,
          'id': 3,
          'onibus_nome': 'Ônibus 03',
          'vagas_disponiveis': 0,
          'ocupados': 46,
        },
        token: 'teste',
      ),
    );
    await salvar(t, '07-associado-lotado');
    await abrir(t, HistoricoV3(token: 'teste', onViagens: () {}));
    await salvar(t, '08-associado-historico');
    await abrir(t, CheckinPendente(viagem: atual, poltrona: 12));
    await salvar(t, '08b-associado-pendente');
    await t.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('Painel, contador, QR e conferência do fiscal', (t) async {
    final fiscal = {...usuario, 'tipo': 'fiscal', 'nome': 'Carlos Lima'};
    await abrir(t, ViagensHoje(usuario: fiscal, token: 'teste'));
    await salvar(t, '09-fiscal-onibus');
    await abrir(t, FluxoFiscal(viagem: atual, usuario: fiscal, token: 'teste'));
    await salvar(t, '10-fiscal-painel');
    await t.tap(find.text('Embarque e QR Code'));
    await t.pump(const Duration(milliseconds: 200));
    await salvar(t, '11-fiscal-contador');
    await t.tap(find.text('Mostrar QR Code do dia'));
    await t.pump(const Duration(milliseconds: 200));
    await t.pump();
    await salvar(t, '12-fiscal-qr');
    expect(find.text('QR Code do dia'), findsOneWidget);
    await t.pumpWidget(const SizedBox.shrink());
    await abrir(
      t,
      FluxoFiscal(
        viagem: atual,
        usuario: fiscal,
        token: 'teste',
        telaInicial: 5,
      ),
    );
    await salvar(t, '13-fiscal-conferencia');
    await abrir(
      t,
      FluxoFiscal(
        viagem: atual,
        usuario: fiscal,
        token: 'teste',
        telaInicial: 3,
      ),
    );
    await t.enterText(find.byType(TextField).first, 'Maria');
    await t.pump(const Duration(milliseconds: 500));
    await t.pump();
    await salvar(t, '13b-fiscal-busca');
    await t.tap(find.text('Maria Souza'));
    await t.pump(const Duration(milliseconds: 500));
    await salvar(t, '13c-fiscal-manual');
    expect(find.text('Motivo do check-in manual'), findsOneWidget);
    await abrir(
      t,
      SelecionarPoltrona(viagem: atual, token: 'teste', proprioFiscal: true),
    );
    await salvar(t, '13d-fiscal-proprio');
    await t.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('Etapas do motorista e adaptação a 360 px', (t) async {
    final motorista = {...usuario, 'tipo': 'motorista', 'nome': 'João Silva'};
    atual = {
      ...atual,
      'status': 'agendada',
      'etapa': 'agendada',
      'etapa_nome': 'Agendada',
      'embarque_aberto': false,
    };
    await abrir(t, ViagensHoje(usuario: motorista, token: 'teste'));
    await salvar(t, '14-motorista-viagens');
    for (final etapa in [
      'agendada',
      'embarque_ida',
      'transito_ida',
      'no_destino',
      'transito_volta',
      'encerrada',
    ]) {
      atual = {
        ...atual,
        'etapa': etapa,
        'status': etapa == 'agendada'
            ? 'agendada'
            : etapa == 'encerrada'
            ? 'finalizada'
            : 'em_andamento',
        'embarque_aberto': ['embarque_ida', 'no_destino'].contains(etapa),
      };
      await t.pumpWidget(const SizedBox.shrink());
      Rastreamento.instancia.parar();
      await abrir(
        t,
        ViagemMotorista(viagem: atual, usuario: motorista, token: 'teste'),
        largura: 360,
      );
      await salvar(t, 'motorista-$etapa');
      if (etapa == 'transito_ida') {
        await t.tap(find.text('Finalizar viagem'));
        await t.pump(const Duration(milliseconds: 500));
        await salvar(t, 'motorista-confirmacao');
        expect(find.text('Deseja finalizar a viagem?'), findsOneWidget);
      }
    }
    await t.pumpWidget(const SizedBox.shrink());
    Rastreamento.instancia.parar();
  });
  testWidgets('Menu da conta contém somente sair', (t) async {
    await abrir(t, ViagensHoje(usuario: usuario, token: 'teste'));
    await t.tap(find.byTooltip('Opções da conta'));
    await t.pump(const Duration(milliseconds: 300));
    expect(find.text('Sair'), findsOneWidget);
    expect(find.byType(PopupMenuItem<String>), findsOneWidget);
    expect(find.text('Alterar senha'), findsNothing);
    await salvar(t, '15-menu-conta');
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Mapas de 16 e 46 lugares mostram todos sem rolagem em 390x844', (
    t,
  ) async {
    for (final capacidade in [16, 46]) {
      atual = {
        ...viagem(),
        'capacidade': capacidade,
        'onibus_nome': capacidade == 16 ? 'Van 02' : 'Ônibus 01',
      };
      await abrir(t, SelecionarPoltrona(viagem: atual, token: 'teste'));
      expect(find.text('Ponto da ida'), findsOneWidget);
      expect(find.text('Ponto da volta'), findsOneWidget);
      expect(ultimoTrajeto, 'ida_volta');
      expect(find.byKey(const ValueKey('rolagem-poltronas')), findsNothing);
      for (var n = 1; n <= capacidade; n++) {
        final seat = find.text(n.toString().padLeft(2, '0'));
        expect(seat, findsOneWidget);
        expect(t.getRect(seat).bottom, lessThan(710));
      }
      await salvar(t, 'v4-poltronas-$capacidade');
    }
    await t.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('Escolha exige ponto e continua visível mesmo com GPS', (
    t,
  ) async {
    atual = {
      ...viagem(),
      'pontos': [
        {'id': 1, 'nome': 'Praça Central', 'sentido': 'ida', 'ordem': 1},
        {'id': 3, 'nome': 'Bairro', 'sentido': 'ida', 'ordem': 2},
        {'id': 2, 'nome': 'UNIGRAN', 'sentido': 'retorno', 'ordem': 1},
      ],
      'localizacao': {'latitude': -22.6, 'longitude': -54.8, 'atrasada': false},
    };
    await abrir(t, SelecionarPoltrona(viagem: atual, token: 'teste'));
    await t.tap(find.text('12'));
    await t.pump();
    ElevatedButton botao() => t.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Confirmar poltrona 12'),
    );
    expect(botao().onPressed, isNull);
    expect(find.text('Ponto da ida'), findsOneWidget);
    await t.tap(find.byType(DropdownButtonFormField<int>).first);
    await t.pump(const Duration(milliseconds: 400));
    await t.tap(find.text('Bairro').last);
    await t.pump(const Duration(milliseconds: 400));
    expect(botao().onPressed, isNotNull);
    await t.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('Antes das 08 aviso e escolha desabilitada', (t) async {
    atual = {
      ...viagem(),
      'status': 'agendada',
      'etapa': 'agendada',
      'escolha_aberta': false,
      'embarque_aberto': false,
      'fiscal_id': null,
      'escolha_abre_em': '2026-10-18T08:00:00-04:00',
    };
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(find.text('A escolha de poltrona abre às 08:00.'), findsOneWidget);
    final botao = t.widget<ElevatedButton>(
      find.widgetWithText(ElevatedButton, 'Escolher poltrona'),
    );
    expect(botao.onPressed, isNull);
    await salvar(t, 'v4-antes-abertura');
    await t.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('Ônibus cheio após partida mostra check-in encerrado', (t) async {
    atual = {
      ...viagem(),
      'vagas_disponiveis': 0,
      'escolha_aberta': false,
      'embarque_aberto': false,
      'partida_ida_em': '2026-10-18T18:00:00-04:00',
    };
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(
      find.text('Check-in encerrado: o ônibus já partiu.'),
      findsOneWidget,
    );
    expect(find.byType(OnibusLotado), findsNothing);
    await t.pumpWidget(const SizedBox.shrink());
  });
  testWidgets('Login com senha gerada abre lista sem exigir troca', (t) async {
    await abrir(t, const Login());
    await t.enterText(find.byType(TextField).first, '802.023');
    await t.enterText(find.byType(TextField).last, 'Abc123');
    await t.tap(find.text('Entrar'));
    for (var i = 0; i < 8; i++) {
      await t.pump(const Duration(milliseconds: 150));
    }
    expect(find.byType(ViagensHoje), findsOneWidget);
    expect(find.text('Alterar senha'), findsNothing);
    FilaOffline.instancia.parar();
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Login ignora sessão antiga e preserva fila do usuário', (
    t,
  ) async {
    final refresh =
        'x.${base64Url.encode(utf8.encode(jsonEncode({'exp': DateTime.now().add(const Duration(days: 1)).millisecondsSinceEpoch ~/ 1000})))}.x';
    await Armazenamento.salvar('sessao', {
      'access': 'teste',
      'refresh': refresh,
      'usuario': usuario,
    });
    await Armazenamento.salvar('fila.1', [
      {'id': 'pendente', 'estado': 'pendente'},
    ]);
    await abrir(t, const Login());
    expect(find.textContaining('Continuar como'), findsNothing);
    expect(find.byType(ViagensHoje), findsNothing);
    expect(await Armazenamento.ler('sessao'), isNull);
    expect(
      (await Armazenamento.ler('fila.1') as List).single['id'],
      'pendente',
    );
    await expectLater(
      ApiService.requisicao('api/viagens/hoje/', 'teste'),
      throwsA(isA<ApiException>()),
    );
    await Armazenamento.apagar('fila.1');
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Ações da escolha são exclusivas antes e depois do check-in', (
    t,
  ) async {
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(find.text('Escolher poltrona'), findsOneWidget);
    expect(find.text('Alterar escolha'), findsNothing);
    expect(find.text('Ler QR Code'), findsNothing);
    final escolha = {'poltrona': 12, 'trajeto': 'ida_volta'};
    atual = {
      ...viagem(),
      'minha_escolha': escolha,
      'minha_reserva': {'poltrona': 12},
      'embarque_aberto': false,
    };
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(find.text('Escolher poltrona'), findsNothing);
    expect(find.text('Alterar escolha'), findsOneWidget);
    expect(find.text('Ler QR Code'), findsNothing);
    await salvar(t, 'correcao-escolha-salva');
    atual = {...atual, 'embarque_aberto': true};
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(find.text('Alterar escolha'), findsOneWidget);
    expect(find.text('Ler QR Code'), findsOneWidget);
    await salvar(t, 'correcao-embarque-aberto');
    atual = {...atual, 'meu_embarque': registro()};
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(find.text('Escolher poltrona'), findsNothing);
    expect(find.text('Alterar escolha'), findsNothing);
    expect(find.text('Cancelar escolha'), findsNothing);
    expect(find.text('Ler QR Code'), findsNothing);
    expect(find.text('Ver comprovante'), findsOneWidget);
    await salvar(t, 'correcao-checkin-confirmado');
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Cancelar escolha pede confirmação e libera a seleção', (
    t,
  ) async {
    atual = {
      ...viagem(),
      'minha_escolha': {'poltrona': 12, 'trajeto': 'ida_volta'},
      'minha_reserva': {'poltrona': 12},
    };
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    await t.ensureVisible(find.text('Cancelar escolha'));
    await t.tap(find.text('Cancelar escolha'));
    await t.pump(const Duration(milliseconds: 300));
    expect(find.text('Cancelar escolha?'), findsOneWidget);
    await t.tap(find.widgetWithText(TextButton, 'Cancelar escolha').last);
    await t.pump(const Duration(milliseconds: 300));
    expect(find.text('Escolher poltrona'), findsOneWidget);
    expect(find.text('Alterar escolha'), findsNothing);
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Reserva em outro ônibus oferece apenas trecho disponível', (
    t,
  ) async {
    atual = {
      ...viagem(),
      'trajetos_disponiveis': ['volta'],
      'bloqueios_trajeto': {'ida': 'Você já escolheu a ida no Ônibus 02.'},
    };
    await abrir(t, SelecionarPoltrona(viagem: atual, token: 'teste'));
    expect(ultimoTrajeto, 'volta');
    expect(find.text('Ida e volta'), findsNothing);
    expect(find.text('Ponto da ida'), findsNothing);
    expect(find.text('Ponto da volta'), findsOneWidget);
    expect(find.text('Você já escolheu a ida no Ônibus 02.'), findsOneWidget);
    atual = {...atual, 'trajetos_disponiveis': <String>[]};
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(
      t
          .widget<ElevatedButton>(
            find.widgetWithText(ElevatedButton, 'Escolher poltrona'),
          )
          .onPressed,
      isNull,
    );
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'Ida lotada permite escolher a volta disponível em outro ônibus',
    (t) async {
      atual = {
        ...viagem(),
        'vagas_disponiveis': 0,
        'ocupados': 46,
        'vagas_por_sentido': {'ida': 0, 'retorno': 14},
        'trajetos_disponiveis': ['volta'],
        'bloqueios_trajeto': {'ida': 'Você já escolheu a ida no Ônibus 02.'},
      };
      await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
      expect(find.byType(OnibusLotado), findsNothing);
      expect(
        t
            .widget<ElevatedButton>(
              find.widgetWithText(ElevatedButton, 'Escolher poltrona'),
            )
            .onPressed,
        isNotNull,
      );
      await t.tap(find.text('Escolher poltrona'));
      await t.pump(const Duration(milliseconds: 400));
      await t.pump(const Duration(milliseconds: 400));
      expect(find.byType(SelecionarPoltrona), findsOneWidget);
      expect(ultimoTrajeto, 'volta');
      expect(find.text('Ponto da ida'), findsNothing);
      expect(find.text('Ponto da volta'), findsOneWidget);
      expect(find.byKey(const ValueKey('rolagem-poltronas')), findsNothing);
      expect(t.getRect(find.text('46')).bottom, lessThan(710));
      await salvar(t, 'correcao-volta-ida-lotada');
      await t.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets('Tela de lotação considera todos os trechos permitidos', (
    t,
  ) async {
    for (final vagasIda in [0, 5]) {
      atual = {
        ...viagem(),
        'vagas_disponiveis': vagasIda,
        'vagas_por_sentido': {'ida': vagasIda, 'retorno': 0},
        'trajetos_disponiveis': ['volta'],
      };
      await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
      expect(find.byType(OnibusLotado), findsOneWidget);
      expect(find.text('Escolher poltrona'), findsNothing);
      expect(
        find.text('Não há poltronas livres para a volta.'),
        findsOneWidget,
      );
    }
    await t.pumpWidget(const SizedBox.shrink());
  });

  testWidgets('Conflito de escolha continua visível mesmo com ônibus cheio', (
    t,
  ) async {
    atual = {
      ...viagem(),
      'vagas_disponiveis': 0,
      'vagas_por_sentido': {'ida': 0, 'retorno': 0},
      'trajetos_disponiveis': <String>[],
      'bloqueios_trajeto': {
        'ida': 'Cancele sua escolha no Ônibus 02 para escolher outro ônibus.',
      },
    };
    await abrir(t, DetalheAssociado(viagem: atual, token: 'teste'));
    expect(find.byType(OnibusLotado), findsNothing);
    expect(
      find.text('Cancele sua escolha no Ônibus 02 para escolher outro ônibus.'),
      findsOneWidget,
    );
    expect(
      t
          .widget<ElevatedButton>(
            find.widgetWithText(ElevatedButton, 'Escolher poltrona'),
          )
          .onPressed,
      isNull,
    );
    await t.pumpWidget(const SizedBox.shrink());
  });
}
