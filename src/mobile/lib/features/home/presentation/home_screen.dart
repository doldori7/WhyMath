// 홈 탭 — 학습 진입점(하단 탭 셸의 첫 탭·MOB-08).
//
// 정직(범위): 교과서 좌표(자동 커리큘럼 정렬 출력·L1+L6)는 아직 런타임 배선 전이라 "준비 중"
// placeholder로 둔다(가짜 데이터 금지). 핵심 행동 2개만 노출한다 — "오늘의 문제 풀기"(진단→문제
// 화면으로 push)와 "코치와 대화하기"(학습 탭으로 이동).
//
// 절대 금기(정서 안전): 랭킹·스트릭·배지·카운트다운·보상 연출을 두지 않는다.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router.dart';
import '../../../theme/spacing.dart';

/// 홈 탭 화면 — 교과서 좌표(준비 중) + 학습 진입 행동 2개.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('WhyMath')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            Text('안녕하세요', style: theme.textTheme.headlineSmall),
            const SizedBox(height: AppSpacing.xs),
            Text('오늘도 함께 이유를 찾아봐요.', style: theme.textTheme.bodyMedium),
            const SizedBox(height: AppSpacing.xl),
            const _TextbookCoordinateCard(),
            const SizedBox(height: AppSpacing.xxl),
            FilledButton.icon(
              onPressed: () => context.push(AppRoutes.problemPath),
              icon: const Icon(Icons.play_arrow_outlined),
              label: const Text('오늘의 문제 풀기'),
            ),
            const SizedBox(height: AppSpacing.md),
            OutlinedButton.icon(
              onPressed: () => context.go(AppRoutes.chatPath),
              icon: const Icon(Icons.chat_bubble_outline),
              label: const Text('코치와 대화하기'),
            ),
          ],
        ),
      ),
    );
  }
}

/// 교과서 좌표 카드 — 자동 커리큘럼 정렬 출력이 들어올 자리(현재 준비 중·정직 placeholder).
class _TextbookCoordinateCard extends StatelessWidget {
  const _TextbookCoordinateCard();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.menu_book_outlined, color: theme.colorScheme.primary),
                const SizedBox(width: AppSpacing.sm),
                Text('내 교과서 좌표', style: theme.textTheme.titleMedium),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              '내 교과서·진도에 맞춘 학습 위치가 여기에 표시됩니다.\n(준비 중)',
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}
