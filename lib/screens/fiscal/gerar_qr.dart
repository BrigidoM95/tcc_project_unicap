import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

class GerarQr extends StatelessWidget {
  final String codigo;

  const GerarQr({super.key, required this.codigo});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(backgroundColor: const Color(0xFFFF5E08)),
      body: Center(child: QrImageView(data: codigo, size: 250)),
    );
  }
}
