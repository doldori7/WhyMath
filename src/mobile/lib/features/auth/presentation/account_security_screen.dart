// 계정 보안 — 내 기기 관리 화면. MOB-12.
//
// 배경(account_security_gap_review.md D4): 학생이 기기를 분실하거나 공용 PC에 로그인한 채로
// 두었을 때 그 세션을 끊을 방법이 앱에 전혀 없었다. SEC-10이 서버 좌석(`GET/DELETE
// /v1/auth/sessions`)을 완비했지만 부르는 화면이 없어 문제는 그대로였다 — 이 화면이 그 좌석을
// 학생 손에 쥐여 준다.
//
// **정서 안전(CLAUDE.md·전역 UI 불변식)**: 이것은 *경고 화면이 아니라 통제 화면*이다.
//  - 제목은 "내 기기 관리"다("낯선 기기 감지"·"보안 경고"가 아니다) — 불안을 조장하지 않는다.
//  - 위험도·의심 배지·빨간 강조를 두지 않는다. 앱 테마의 error 롤은 이미 앰버로 재정의돼 있어
//    (`app_theme.dart`) 빨강이 나올 수 없고, 여기서도 위협 판정 자체를 하지 않는다.
//  - 게임화 요소(점수·스트릭·랭킹) 0종.
//
// **정직 표기**: 전체 로그아웃은 서버가 리프레시 세션만 취소한다 — 이미 발급된 액세스 토큰은
// 자체 만료까지 유효하다(SEC-10 서버 모듈 docstring). 문구가 "잠시 뒤"로 그 한계를 그대로
// 말한다(즉시 차단이라고 말하지 않는다).
//
// 경계(CLAUDE.md): 세션 유효성·소유 판정은 전부 서버(L5)다. 이 화면은 받은 목록을 렌더하고
// 취소를 요청할 뿐이다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../theme/spacing.dart';
import '../application/account_security_controller.dart';
import '../application/account_security_state.dart';
import '../data/auth_sessions_api.dart';

/// 최소 탭 타깃(접근성) — 44dp 이상 요구(A11Y 가드는 48dp 기준으로 검사한다).
const double _minTapTarget = 48;

/// 내 기기 관리 화면 — 활성 세션 목록 + 단건/전체 로그아웃.
class AccountSecurityScreen extends ConsumerStatefulWidget {
  const AccountSecurityScreen({super.key});

  @override
  ConsumerState<AccountSecurityScreen> createState() => _AccountSecurityScreenState();
}

class _AccountSecurityScreenState extends ConsumerState<AccountSecurityScreen> {
  @override
  void initState() {
    super.initState();
    // 첫 프레임 이후 로드(build 중 provider 변경 회피 — me_screen.dart 관례).
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(accountSecurityControllerProvider.notifier).load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(accountSecurityControllerProvider);

    // 조작 결과 안내(스낵바) — 표시 후 즉시 비워 재빌드마다 반복되지 않게 한다.
    ref.listen(accountSecurityControllerProvider.select((s) => s.notice), (previous, next) {
      if (next == null || next.isEmpty) {
        return;
      }
      ScaffoldMessenger.of(context)
        ..clearSnackBars()
        ..showSnackBar(SnackBar(content: Text(next)));
      ref.read(accountSecurityControllerProvider.notifier).clearNotice();
    });

    return Scaffold(
      appBar: AppBar(title: const Text('내 기기 관리')),
      body: RefreshIndicator(
        onRefresh: () => ref.read(accountSecurityControllerProvider.notifier).load(),
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          children: [
            const _IntroText(),
            const SizedBox(height: AppSpacing.xl),
            ..._buildBody(context, state),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildBody(BuildContext context, AccountSecurityState state) {
    switch (state.status) {
      case AccountSectionStatus.idle:
      case AccountSectionStatus.loading:
        return const [
          Center(
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.xxl),
              child: CircularProgressIndicator(),
            ),
          ),
        ];
      case AccountSectionStatus.unauthenticated:
        return const [
          _MessageBlock(icon: Icons.login_outlined, message: '로그인하면 내 기기 목록을 볼 수 있어요.'),
        ];
      case AccountSectionStatus.error:
        return [
          _MessageBlock(icon: Icons.refresh_outlined, message: state.error ?? '기기 목록을 불러오지 못했어요.'),
          const SizedBox(height: AppSpacing.lg),
          Center(
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(
                minimumSize: const Size(_minTapTarget * 2, _minTapTarget),
              ),
              onPressed: () => ref.read(accountSecurityControllerProvider.notifier).load(),
              child: const Text('다시 시도'),
            ),
          ),
        ];
      case AccountSectionStatus.loaded:
        return _buildLoaded(context, state);
    }
  }

  List<Widget> _buildLoaded(BuildContext context, AccountSecurityState state) {
    if (state.sessions.isEmpty) {
      // 빈 목록은 오류가 아니라 정상 응답이다 — 그렇게 말한다.
      return const [_MessageBlock(icon: Icons.devices_outlined, message: '지금 로그인되어 있는 기기가 없어요.')];
    }
    return [
      for (final session in state.sessions)
        _SessionTile(
          session: session,
          isRevoking: state.revokingSessionId == session.sessionId,
          onRevoke: state.isRevokingAll
              ? null
              : () => ref
                    .read(accountSecurityControllerProvider.notifier)
                    .revokeSession(session.sessionId),
        ),
      const SizedBox(height: AppSpacing.xxl),
      _RevokeAllButton(
        isRevoking: state.isRevokingAll,
        onPressed: state.revokingSessionId != null ? null : () => _confirmRevokeAll(context),
      ),
    ];
  }

  /// 전체 로그아웃 확인 — 되돌릴 수 없는 조작이라 한 번 묻는다(불안 조장 없이 사실만).
  Future<void> _confirmRevokeAll(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('모든 기기에서 로그아웃할까요?'),
        content: const Text(
          '이 기기를 포함해 로그인되어 있는 모든 기기가 로그아웃돼요. '
          '다시 쓰려면 로그인만 하면 돼요.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('취소'),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('로그아웃'),
          ),
        ],
      ),
    );
    if (confirmed ?? false) {
      await ref.read(accountSecurityControllerProvider.notifier).revokeAllSessions();
    }
  }
}

/// 화면 목적 안내 — 통제감 있는 톤(경고가 아니라 관리).
class _IntroText extends StatelessWidget {
  const _IntroText();

  @override
  Widget build(BuildContext context) {
    return Text(
      '지금 내 계정에 로그인되어 있는 기기 목록이에요. '
      '쓰지 않는 기기는 로그아웃해 두면 좋아요.',
      style: Theme.of(context).textTheme.bodyMedium,
    );
  }
}

/// 세션 1건 — 플랫폼·로그인 시각 + 로그아웃 버튼.
class _SessionTile extends StatelessWidget {
  const _SessionTile({required this.session, required this.isRevoking, required this.onRevoke});

  final AuthSessionInfo session;
  final bool isRevoking;
  final VoidCallback? onRevoke;

  @override
  Widget build(BuildContext context) {
    final label = session.platform ?? '기기 정보 없음';
    final issued = _formatDate(session.issuedAt);
    return Card(
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Row(
          children: [
            const Icon(Icons.devices_outlined),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Semantics(
                label: '$label, $issued에 로그인',
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label, style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: AppSpacing.xs),
                    Text('$issued 로그인', style: Theme.of(context).textTheme.bodySmall),
                  ],
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            if (isRevoking)
              const SizedBox(
                width: _minTapTarget,
                height: _minTapTarget,
                child: Center(
                  child: SizedBox(
                    width: AppSpacing.xl,
                    height: AppSpacing.xl,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
              )
            else
              TextButton(
                style: TextButton.styleFrom(
                  minimumSize: const Size(_minTapTarget * 1.5, _minTapTarget),
                ),
                onPressed: onRevoke,
                child: const Text('로그아웃'),
              ),
          ],
        ),
      ),
    );
  }

  /// 날짜 표기 — 로컬 시각 기준 `YYYY.MM.DD` (초 단위 정밀도는 학생에게 의미가 없다).
  static String _formatDate(DateTime value) {
    final local = value.toLocal();
    final month = local.month.toString().padLeft(2, '0');
    final day = local.day.toString().padLeft(2, '0');
    return '${local.year}.$month.$day';
  }
}

/// 전체 로그아웃 버튼 — 한계를 정직하게 덧붙인다.
class _RevokeAllButton extends StatelessWidget {
  const _RevokeAllButton({required this.isRevoking, required this.onPressed});

  final bool isRevoking;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OutlinedButton(
          style: OutlinedButton.styleFrom(minimumSize: const Size(double.infinity, _minTapTarget)),
          onPressed: isRevoking ? null : onPressed,
          child: isRevoking
              ? const SizedBox(
                  width: AppSpacing.xl,
                  height: AppSpacing.xl,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('모든 기기에서 로그아웃'),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          '모든 기기가 잠시 뒤 로그아웃돼요.',
          style: Theme.of(context).textTheme.bodySmall,
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}

/// 상태 안내 블록(빈 목록·미인증·오류 공통).
class _MessageBlock extends StatelessWidget {
  const _MessageBlock({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxl),
      child: Column(
        children: [
          Icon(icon, size: AppSpacing.huge),
          const SizedBox(height: AppSpacing.lg),
          Text(message, style: Theme.of(context).textTheme.bodyMedium, textAlign: TextAlign.center),
        ],
      ),
    );
  }
}
