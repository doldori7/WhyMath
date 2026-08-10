// 나 탭 — 학습 경로·진단·설정 진입점(하단 탭 셸·MOB-08).
//
// PATH-05: 학습 경로·진단 결과 두 섹션을 기존 단일-개념 API(`GET /v1/me/weak-concepts/{id}
// /learning-path`·`GET /v1/me/diagnosis/concepts`)로 배선한다(신규 백엔드 엔드포인트 없음).
// 설정 섹션은 아직 미배선이라 "준비 중"으로 정직하게 남긴다. 실동작하는 나머지는 로그아웃뿐이며,
// 인증 세션일 때만 노출한다(`authControllerProvider`).
//
// **정직 신호(CLAUDE.md "확실하지 않을 때 자신 있게 말함 금지")**: 401(미인증)·has_cycle(선수
// 그래프 순환)·빈 학습 경로/진단 목록은 서로 다른 의미라 하나의 "오류가 발생했습니다" 문구로
// 뭉개지 않는다 — `MeTabState.SectionStatus`가 401/그 외 실패를 분리하고, has_cycle·빈 목록은
// 이 화면이 데이터를 직접 읽어 각각 다른 안내로 렌더한다(`me_tab_controller.dart`).
//
// 절대 금기(정서 안전·반게임화): 랭킹·스트릭·배지·점수 비교·카운트다운을 두지 않는다
// (`docs/design/ui/00_index.md` 전역 UI 불변식 #2). 학습 경로 단계 번호는 순서 표시일 뿐
// 게임 레벨이 아니다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router.dart';
import '../../../theme/spacing.dart';
import '../../auth/application/auth_controller.dart';
import '../../problems/data/problem_models.dart';
import '../application/me_tab_controller.dart';
import '../application/me_tab_state.dart';

/// 나 탭 화면 — 학습 경로·진단 결과(실 API) + 설정(준비 중) + (인증 시) 로그아웃.
class MeScreen extends ConsumerStatefulWidget {
  const MeScreen({super.key});

  @override
  ConsumerState<MeScreen> createState() => _MeScreenState();
}

class _MeScreenState extends ConsumerState<MeScreen> {
  @override
  void initState() {
    super.initState();
    // 첫 프레임 이후 로드를 트리거한다(build 중 provider 변경 회피 — problem_screen.dart 관례).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(meTabControllerProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final isAuthenticated = ref.watch(
      authControllerProvider.select((s) => s.isAuthenticated),
    );
    final meTabState = ref.watch(meTabControllerProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('나')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
          children: [
            _LearningPathSection(state: meTabState),
            const Divider(height: 1),
            _DiagnosisSection(state: meTabState),
            const Divider(height: 1),
            const _PlaceholderTile(
              icon: Icons.settings_outlined,
              title: '설정',
              subtitle: '알림·표시·계정',
            ),
            // 내 기기 관리(MOB-12) — 인증 세션에서만 노출한다(미인증이면 목록이 401이라
            // 진입해도 볼 것이 없다). 톤은 "보안 경고"가 아니라 "관리"다(정서 안전).
            if (isAuthenticated)
              ListTile(
                leading: const Icon(Icons.devices_outlined),
                title: const Text('내 기기 관리'),
                subtitle: const Text('로그인되어 있는 기기 확인·로그아웃'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => context.push(AppRoutes.accountSecurityPath),
              ),
            if (isAuthenticated) ...[
              const Divider(height: 24),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
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

/// "학습 경로" 섹션 — `GET /v1/me/weak-concepts/{id}/learning-path` 소비.
///
/// 대상 개념은 진단 결과 첫 항목(서버가 이미 약점 먼저 정렬)이다. `MeTabController.load`가
/// 두 섹션을 순서대로 채우므로 이 위젯은 상태를 읽어 렌더만 한다(수학 로직 클라 미구현).
class _LearningPathSection extends ConsumerWidget {
  const _LearningPathSection({required this.state});

  final MeTabState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    void retry() => ref.read(meTabControllerProvider.notifier).load();

    return _Section(
      icon: Icons.timeline_outlined,
      title: '학습 경로',
      subtitle: '막힌 선수개념을 순서대로 다지기',
      child: switch (state.learningPathStatus) {
        SectionStatus.idle ||
        SectionStatus.loading =>
          const _LoadingRow(),
        SectionStatus.unauthenticated => const _MessageRow(
            icon: Icons.lock_outline,
            message: '로그인이 필요해요.',
          ),
        SectionStatus.error => _MessageRow(
            icon: Icons.error_outline,
            message: state.learningPathError ?? '학습 경로를 불러오지 못했어요.',
            onRetry: retry,
          ),
        SectionStatus.loaded => _buildLoaded(state.learningPath),
      },
    );
  }

  Widget _buildLoaded(LearningPath? path) {
    if (path == null) {
      // 진단 근거가 아직 없어 대상 개념을 고르지 못한 상태(정상 — 에러 아님).
      return const _MessageRow(
        icon: Icons.info_outline,
        message: '아직 진단 데이터가 없어요. 문제를 풀면 학습 경로가 만들어져요.',
      );
    }
    if (path.steps.isEmpty) {
      // 서버 정직 신호: steps==0 은 "막힌 선수개념 없음"이라는 정상 결과다(에러 아님).
      return const _MessageRow(
        icon: Icons.check_circle_outline,
        message: '지금은 특별히 복습할 막힌 선수개념이 없어요.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (path.hasCycle)
          // 서버 정직 신호: has_cycle — 삼키지 않고 그대로 알린다(사이클 잔여 단계 존재).
          const Padding(
            padding: EdgeInsets.fromLTRB(
              AppSpacing.lg,
              0,
              AppSpacing.lg,
              AppSpacing.sm,
            ),
            child: _MessageRow(
              icon: Icons.warning_amber_outlined,
              message: '개념 사이 순환 구조가 감지돼 일부 순서는 참고용으로만 표시돼요.',
              dense: true,
            ),
          ),
        for (final step in path.steps)
          ListTile(
            dense: true,
            leading: CircleAvatar(
              radius: 14,
              child: Text('${step.position + 1}'),
            ),
            title: Text(step.conceptName ?? '(이름 미확인 개념)'),
            subtitle: step.isCycleResidual ? const Text('순환 잔여 단계') : null,
          ),
      ],
    );
  }
}

/// "진단 결과" 섹션 — `GET /v1/me/diagnosis/concepts` 소비.
class _DiagnosisSection extends ConsumerWidget {
  const _DiagnosisSection({required this.state});

  final MeTabState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    void retry() => ref.read(meTabControllerProvider.notifier).load();

    return _Section(
      icon: Icons.assessment_outlined,
      title: '진단 결과',
      subtitle: '강점·약점 개념 분석',
      child: switch (state.diagnosisStatus) {
        SectionStatus.idle ||
        SectionStatus.loading =>
          const _LoadingRow(),
        SectionStatus.unauthenticated => const _MessageRow(
            icon: Icons.lock_outline,
            message: '로그인이 필요해요.',
          ),
        SectionStatus.error => _MessageRow(
            icon: Icons.error_outline,
            message: state.diagnosisError ?? '진단 결과를 불러오지 못했어요.',
            onRetry: retry,
          ),
        SectionStatus.loaded => _buildLoaded(state.diagnoses),
      },
    );
  }

  Widget _buildLoaded(List<ConceptDiagnosisItem> diagnoses) {
    if (diagnoses.isEmpty) {
      // 정상 신호(진단 근거 부족) — 에러가 아니다.
      return const _MessageRow(
        icon: Icons.info_outline,
        message: '아직 진단 데이터가 없어요. 문제를 풀면 진단이 쌓여요.',
      );
    }
    return Column(
      children: [
        for (final item in diagnoses)
          ListTile(
            dense: true,
            leading: const Icon(Icons.circle_outlined, size: 20),
            title: Text(item.conceptName ?? '(이름 미확인 개념)'),
            subtitle: Text(item.coaching.rationale),
            // MOB-10: 숙달 상태 라벨(서버 mastery_to_level 산출) — 원시 BKT 확률·θ는
            // 어디에도 노출하지 않는다. 순위·등급 표기가 아니라 상태 서술이므로
            // _PlaceholderTile의 '준비 중'과 동일하게 절제된 trailing 텍스트로 렌더.
            trailing: item.masteryLevel == null
                ? null
                : Builder(
                    builder: (context) => Text(
                      item.masteryLevel!,
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                  ),
          ),
      ],
    );
  }
}

/// 섹션 공통 골격 — 헤더(아이콘·제목·설명) + 상태별 본문.
class _Section extends StatelessWidget {
  const _Section({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.child,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ListTile(
          leading: Icon(icon),
          title: Text(title),
          subtitle: Text(subtitle),
        ),
        child,
        const SizedBox(height: AppSpacing.sm),
      ],
    );
  }
}

/// 로딩 인디케이터 행(작은 크기·섹션 내부용).
class _LoadingRow extends StatelessWidget {
  const _LoadingRow();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.sm,
      ),
      child: SizedBox(
        height: 20,
        width: 20,
        child: CircularProgressIndicator(strokeWidth: 2),
      ),
    );
  }
}

/// 안내 문구 행(아이콘 + 텍스트 + 선택적 재시도 버튼).
class _MessageRow extends StatelessWidget {
  const _MessageRow({
    required this.icon,
    required this.message,
    this.onRetry,
    this.dense = false,
  });

  final IconData icon;
  final String message;
  final VoidCallback? onRetry;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: dense ? 0 : AppSpacing.sm,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
          if (onRetry != null)
            TextButton(onPressed: onRetry, child: const Text('다시 시도')),
        ],
      ),
    );
  }
}

/// 준비 중 항목 — 아이콘·제목·설명 + "준비 중" 표시(정직 placeholder, 설정 섹션 전용).
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
