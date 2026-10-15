import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import '../../services/api_service.dart';
import '../../ui/tema.dart';

class CheckinQr extends StatefulWidget {
  final String accessToken;
  const CheckinQr({super.key, required this.accessToken});
  @override
  State<CheckinQr> createState() => _CheckinQrState();
}

class _CheckinQrState extends State<CheckinQr> {
  final codigo = TextEditingController();
  bool ocupado = false, camera = false, confirmado = false;
  String? mensagem;
  @override
  void dispose() {
    codigo.dispose();
    super.dispose();
  }

  Future<void> confirmar(String valor) async {
    if (ocupado || confirmado) return;
    if (valor.trim().isEmpty) {
      setState(() => mensagem = 'Digite o código apresentado pelo fiscal.');
      return;
    }
    setState(() {
      ocupado = true;
      camera = false;
      mensagem = null;
    });
    try {
      final d = await ApiService.embarques(
        'checkin/',
        widget.accessToken,
        corpo: {'codigo': valor.trim()},
      );
      final c = d['checkin'];
      if (mounted) {
        setState(() {
          confirmado = true;
          mensagem =
              "Embarque confirmado!\n${c['nome']} — ${c['rua']}\nÔnibus ${c['onibus_codigo']} / ${c['placa']}\n${c['rota_nome']} — ${c['sentido']}\n${horarioLocal(c['registrado_em'])}";
        });
      }
    } catch (e) {
      if (mounted) setState(() => mensagem = ApiService.mensagemErro(e));
    } finally {
      if (mounted) setState(() => ocupado = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Confirmar embarque')),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (mensagem != null) Aviso(mensagem!, sucesso: confirmado),
        if (ocupado)
          const Padding(
            padding: EdgeInsets.all(20),
            child: Center(child: CircularProgressIndicator()),
          ),
        if (confirmado)
          OutlinedButton.icon(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back),
            label: const Text('Voltar ao início'),
          ),
        if (!confirmado) ...[
          CartaoSecao(
            titulo: 'Ler QR Code',
            descricao:
                'Aponte a câmera para o QR Code apresentado pelo fiscal.',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ElevatedButton.icon(
                  onPressed: ocupado
                      ? null
                      : () => setState(() => camera = !camera),
                  icon: const Icon(Icons.qr_code_scanner),
                  label: Text(camera ? 'Fechar câmera' : 'Abrir câmera'),
                ),
                if (camera)
                  Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: SizedBox(
                        height: 280,
                        child: MobileScanner(
                          errorBuilder: (context, error, child) => const Center(
                            child: Padding(
                              padding: EdgeInsets.all(20),
                              child: Text(
                                'Não foi possível abrir a câmera. Confira a permissão ou digite o código abaixo.',
                              ),
                            ),
                          ),
                          onDetect: (captura) {
                            for (final b in captura.barcodes) {
                              final valor = b.rawValue;
                              if (valor != null && valor.isNotEmpty) {
                                confirmar(valor);
                                break;
                              }
                            }
                          },
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
          CartaoSecao(
            titulo: 'Digitar código',
            descricao:
                'Você também pode usar o código curto exibido pelo fiscal.',
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: codigo,
                  enabled: !ocupado,
                  textCapitalization: TextCapitalization.characters,
                  autocorrect: false,
                  enableSuggestions: false,
                  onSubmitted: confirmar,
                  decoration: const InputDecoration(
                    labelText: 'Código de embarque',
                    hintText: 'UNIBUS-K7M4Q9',
                    prefixIcon: Icon(Icons.confirmation_number_outlined),
                  ),
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: ocupado ? null : () => confirmar(codigo.text),
                  icon: const Icon(Icons.check),
                  label: const Text('Confirmar embarque'),
                ),
              ],
            ),
          ),
        ],
      ],
    ),
  );
}
