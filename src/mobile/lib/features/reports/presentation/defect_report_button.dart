// 결함 신고 버튼 — RPT-01의 유일한 생산자.
//
// 배경: 학생이 문항·AI응답·수식 오류를 신고할 경로가 앱에 전혀 없었다(D1). 이 버튼이 없으면
// 백엔드 신고 테이블·엔드포인트가 아무리 갖춰져도 채널은 "만들고 잇지 않음"으로 반복된다.
//
// 범위(v0 동결): 카테고리 6종 중 택1 + 제출만 — 자유서술 입력 필드는 두지 않는다(태스크
// 명시 제약). 정서 안전(CLAUDE.md): 신고 자체는 학생의 정오와 무관한 중립 액션이라 경고색
// (빨강)을 쓰지 않고, 실패해도 질책 없는 톤으로 안내하며 학습 흐름을 막지 않는다(다이얼로그
// 밖 화면 전이 없음).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/defect_report_api.dart';

/// 앱바 등에 붙이는 결함 신고 아이콘 버튼 — 탭하면 카테고리 선택 다이얼로그를 띄우고,
/// 선택·제출되면 [DefectReportApi.reportDefect]를 1회 호출한다.
///
/// [problemId]가 있으면(활성 문제 화면·그 문제로 진입한 코치 대화) 신고에 대상 참조로
/// 실어 보낸다 — 학생 식별 정보가 아니라 "무엇에 대한 신고인지"일 뿐이다.
class DefectReportButton extends ConsumerWidget {
  const DefectReportButton({super.key, this.problemId});

  final String? problemId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return IconButton(
      icon: const Icon(Icons.flag_outlined),
      tooltip: '오류 신고',
      onPressed: () => _openDialog(context, ref),
    );
  }

  Future<void> _openDialog(BuildContext context, WidgetRef ref) async {
    final DefectReportCategory? category =
        await showDialog<DefectReportCategory>(
          context: context,
          builder: (_) => const _DefectReportDialog(),
        );
    if (category == null || !context.mounted) {
      return; // 취소 — 아무 요청도 보내지 않는다.
    }
    try {
      await ref
          .read(defectReportApiProvider)
          .reportDefect(category: category, problemId: problemId);
      if (context.mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            const SnackBar(content: Text('신고가 접수됐어요. 알려줘서 고마워요.')),
          );
      }
    } catch (_) {
      // 신고 실패도 학습 흐름을 막지 않는다(질책 없는 부드러운 안내·재시도 유도).
      if (context.mounted) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            const SnackBar(content: Text('신고 접수에 실패했어요. 잠시 후 다시 시도해 주세요.')),
          );
      }
    }
  }
}

/// 카테고리 선택 다이얼로그 — 6종 라디오 + 취소/신고하기(자유서술 없음).
class _DefectReportDialog extends StatefulWidget {
  const _DefectReportDialog();

  @override
  State<_DefectReportDialog> createState() => _DefectReportDialogState();
}

class _DefectReportDialogState extends State<_DefectReportDialog> {
  DefectReportCategory _selected = DefectReportCategory.contentError;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('어떤 문제를 신고할까요?'),
      content: SingleChildScrollView(
        // RadioGroup 조상 위젯이 그룹 상태를 관리한다(Flutter 3.32+ — RadioListTile의
        // groupValue/onChanged 직접 사용은 deprecated_member_use로 flutter analyze가
        // exit 1을 낸다).
        child: RadioGroup<DefectReportCategory>(
          groupValue: _selected,
          onChanged: (DefectReportCategory? value) {
            if (value != null) {
              setState(() => _selected = value);
            }
          },
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (final DefectReportCategory category
                  in DefectReportCategory.values)
                RadioListTile<DefectReportCategory>(
                  dense: true,
                  title: Text(category.label),
                  value: category,
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('취소'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(_selected),
          child: const Text('신고하기'),
        ),
      ],
    );
  }
}
