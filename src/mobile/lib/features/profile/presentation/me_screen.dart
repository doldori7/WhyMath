// 나 탭 — 학습 경로·진단·설정 진입점(하단 탭 셸·MOB-08).
//
// 정직(범위): 학습 경로 시각화(L2 학습자 모델)·진단 결과·설정은 아직 이 탭에 배선되지 않았다.
// 가짜 데이터를 만들지 않고 "준비 중"으로 정직하게 표기한다. 실동작하는 것은 로그아웃뿐이며,
// 인증 세션일 때만 노출한다(`authControllerProvider`).
//
// 절대 금기(정서 안전): 랭킹·스트릭·배지·점수 비교를 두지 않는다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/application/auth_controller.dart';

/// 나 탭 화면 — 준비 중 섹션 3개 + (인증 시) 로그아웃.
class MeScreen extends ConsumerWidget {
  const MeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final isAuthenticated = ref.watch(
      authControllerProvider.select((s) => s.isAuthenticated),
    );
    return Scaffold(
      appBar: AppBar(title: const Text('나')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          children: [
            const _PlaceholderTile(
              icon: Icons.timeline_outlined,
              title: '학습 경로',
              subtitle: '내 개념 지도와 진행 상황',
            ),
            const _PlaceholderTile(
              icon: Icons.assessment_outlined,
              title: '진단 결과',
              subtitle: '강점·약점 개념 분석',
            ),
            const _PlaceholderTile(
              icon: Icons.settings_outlined,
              title: '설정',
              subtitle: '알림·표시·계정',
            ),
            if (isAuthenticated) ...[
              const Divider(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: OutlinedButton.icon(
                  onPressed: () =>
                      ref.read(authControllerProvider.notifier).logout(),
                  icon: const Icon(Icons.logout_outlined),
                  label: const Text('로그아웃'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// 준비 중 항목 — 아이콘·제목·설명 + "준비 중" 표시(정직 placeholder).
class _PlaceholderTile extends StatelessWidget {
  const _PlaceholderTile({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon),
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: Text(
        '준비 중',
        style: Theme.of(context).textTheme.labelMedium,
      ),
    );
  }
}
