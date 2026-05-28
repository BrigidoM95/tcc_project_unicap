import 'package:flutter/material.dart';

class CheckinQr extends StatefulWidget {
  const CheckinQr({super.key});

  @override
  State<CheckinQr> createState() => _CheckinQrState();
}

class _CheckinQrState extends State<CheckinQr> {
  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: Center(child: Text("Check-in QR")));
  }
}
