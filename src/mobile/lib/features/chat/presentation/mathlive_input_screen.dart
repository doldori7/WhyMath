// MathliveInputScreen — 수식 입력 화면(채팅에서 push해 진입, 완료 시 LaTeX를 pop 결과로 반환).
//
// 경계(CLAUDE.md): 화면은 학생이 입력한 LaTeX를 *수집·반환*만 한다 — 수학 판정·검증은 서버(L3)가
// 한다. OCR 화면(ocr_capture_screen)과 동형으로 채팅을 알지 못한 채 `context.pop(latex)`로 결과만
// 돌려주고, 채팅이 `sendSolution`으로 매핑·전송한다(단방향 chat→math-input 의존).
//
// 정서 안전(절대 금기): 정오 강조·정답·빨강 경고·게임화 없음. 입력을 격려하는 중립 톤만.
import 'package:flutter/material.dart';

import 'mathlive_input_webview.dart';

/// 수식(LaTeX) 입력 화면 — MathLive WebView로 입력받아 "완료"로 반환한다.
class MathliveInputScreen extends StatefulWidget {
  const MathliveInputScreen({super.key});

  @override
  State<MathliveInputScreen> createState() => _MathliveInputScreenState();
}

class _MathliveInputScreenState extends State<MathliveInputScreen> {
  /// WebView 입력 상태 핸들(전송/취소 시 비우기).
  final GlobalKey<MathliveInputWebViewState> _inputKey =
      GlobalKey<MathliveInputWebViewState>();

  /// 웹에서 흘러온 현재 LaTeX(미리보기·완료 활성화 판정).
  String _latex = '';

  bool get _canSubmit => _latex.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('수식으로 풀이 입력'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          tooltip: '취소',
          // 취소는 아무것도 반환하지 않는다(null) — 채팅은 그대로 유지된다.
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '풀이 수식을 입력해 주세요. 정답 여부는 함께 확인해요.',
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 12),
              MathliveInputWebView(
                key: _inputKey,
                height: 140,
                onChanged: (latex) => setState(() => _latex = latex),
              ),
              const SizedBox(height: 12),
              // 입력 미리보기(LaTeX 원문) — 렌더 위젯 전까지 plain Text(기존 관행).
              if (_latex.trim().isNotEmpty)
                Text(
                  _latex,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                ),
              const Spacer(),
              Row(
                children: [
                  TextButton(
                    onPressed: () {
                      _inputKey.currentState?.clear();
                    },
                    child: const Text('지우기'),
                  ),
                  const Spacer(),
                  FilledButton(
                    // 빈 입력은 보낼 게 없으므로 비활성(전송 무의미).
                    onPressed: _canSubmit
                        ? () => Navigator.of(context).pop(_latex.trim())
                        : null,
                    child: const Text('완료'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
