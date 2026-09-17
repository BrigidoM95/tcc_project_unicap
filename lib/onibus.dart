import 'package:flutter/material.dart';

import './services/api_service.dart';

class Onibus extends StatelessWidget {
  final Map<String, dynamic> dados;

  const Onibus({super.key, required this.dados});

  @override
  Widget build(BuildContext context) {
    final foto = ApiService.tratarUrlImagem(dados['foto']?.toString());

    final codigo = dados['codigo']?.toString() ?? '-';

    final nome = dados['nome']?.toString() ?? 'Ônibus';

    final placa = dados['placa']?.toString() ?? '-';

    final capacidade = dados['capacidade']?.toString() ?? '-';

    final motorista =
        dados['motorista_nome']?.toString().trim().isNotEmpty == true
        ? dados['motorista_nome'].toString()
        : 'Não informado';

    final observacoes =
        dados['observacoes']?.toString().trim().isNotEmpty == true
        ? dados['observacoes'].toString()
        : 'Nenhuma observação cadastrada.';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Detalhes do Ônibus'),
        backgroundColor: const Color(0xFFFF5E08),
      ),

      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (foto.isNotEmpty)
              ClipRRect(
                borderRadius: BorderRadius.circular(15),
                child: Image.network(
                  foto,
                  width: double.infinity,
                  height: 230,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return _semImagem();
                  },
                ),
              )
            else
              _semImagem(),

            const SizedBox(height: 25),

            Text(
              nome,
              style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 20),

            _informacao(Icons.confirmation_number, 'Código', codigo),

            _informacao(Icons.pin, 'Placa', placa),

            _informacao(
              Icons.event_seat,
              'Capacidade',
              '$capacidade passageiros',
            ),

            _informacao(Icons.person, 'Motorista', motorista),

            _informacao(Icons.check_circle, 'Status', 'Ativo'),

            const SizedBox(height: 20),

            const Text(
              'Observações',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 8),

            Text(observacoes, style: const TextStyle(fontSize: 16)),

            const SizedBox(height: 30),

            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: () {
                  Navigator.pop(context);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1C3B6E),
                  foregroundColor: Colors.white,
                  minimumSize: const Size(double.infinity, 50),
                ),
                child: const Text('Voltar'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _informacao(IconData icone, String titulo, String valor) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 15),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icone, color: const Color(0xFF1C3B6E)),

          const SizedBox(width: 12),

          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  titulo,
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),

                const SizedBox(height: 3),

                Text(valor),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _semImagem() {
    return Container(
      width: double.infinity,
      height: 230,
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(15),
      ),
      child: const Icon(Icons.directions_bus, size: 100, color: Colors.grey),
    );
  }
}
