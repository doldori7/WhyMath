// 탐구 탭 — 사고력·시각화·개념 탐색 진입점(하단 탭 셸·MOB-08).
//
// 정직(범위): 사고력 장면·인터랙티브 시각화(Visualization)·개념 점화 지도·다중 풀이 갤러리(Phase 3)는
// 아직 이 탭에 배선되지 않았다. 가짜 목록을 만들지 않고 "준비 중"으로 정직하게 표기한다(무엇이 올지
// 서술만). 화면이 채워지면 이 placeholder를 실제 콘텐츠 렌더러로 교체한다.
import 'package:flutter/material.dart';

/// 탐구 탭 화면 — 준비 중 placeholder(예정 콘텐츠 서술).
class ExploreScreen extends StatelessWidget {
  const ExploreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('탐구')),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  Icons.explore_outlined,
                  size: 48,
                  color: theme.colorScheme.primary,
                ),
                const SizedBox(height: 16),
                Text(
                  '탐구 (준비 중)',
                  style: theme.textTheme.titleLarge,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  '사고력 문제와 움직이는 시각화, 개념 점화 지도,\n'
                  '다른 학생들의 풀이 갤러리가 이곳에 준비됩니다.',
                  style: theme.textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
