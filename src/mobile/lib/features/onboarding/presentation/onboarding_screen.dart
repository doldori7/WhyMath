// 온보딩 화면 — 앱의 메타인지 접근을 안내해 학생 기대를 관리한다.
//
// 목적(CLAUDE.md): "답이 아닌, 이유를 묻는 수학"이라는 정체성과 *답 미루기* 철학을 첫
// 화면에서 부드럽게 안내한다. 정답을 바로 주지 않고 함께 생각한다는 점을 미리 알리면
// 학생이 답 지연을 "불친절"이 아니라 *함께 배우는 방식*으로 받아들이게 된다(정서 안전).
//
// 절대 금기: 중독성·게임화·카운트다운·보상 연출을 두지 않는다. 톤은 은근하고 격려하는
// 한국어이며, 외부 이미지 자산에 의존하지 않고 텍스트+아이콘만으로 구성한다(asset 경고 회피).
//
// 범위(정직): 온보딩 1회-노출 영속은 후속(shared_preferences 미도입)이라 현재는 매 진입마다
// 노출된다. "건너뛰기"·"시작하기" 모두 채팅(`/`)으로 이동한다.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/router.dart';

/// 온보딩 한 페이지의 콘텐츠 모델(아이콘·제목·설명).
class _OnboardingPage {
  const _OnboardingPage({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;
}

/// 온보딩 페이지 정의 — 메타인지 철학 3단계.
///
/// ① 브랜드(이유를 묻는다) ② 답 미루기 수용(막혀도 함께 단계를 짚는다) ③ 검산(함께 확인).
const List<_OnboardingPage> _pages = [
  _OnboardingPage(
    icon: Icons.lightbulb_outline,
    title: '답이 아닌, 이유를 묻습니다',
    body: '정답을 바로 알려주지 않아요.\n어떻게 생각했는지, 왜 그런지\n함께 짚어가며 풀이를 만들어 가요.',
  ),
  _OnboardingPage(
    icon: Icons.route_outlined,
    title: '막혀도 괜찮아요',
    body: '막히는 건 배움의 자연스러운 일부예요.\n어디서 멈췄는지 같이 살펴보고\n다음 한 걸음을 함께 찾아요.',
  ),
  _OnboardingPage(
    icon: Icons.checklist_rtl_outlined,
    title: '풀이를 함께 검산해요',
    body: '답이 나와도 끝이 아니에요.\n각 단계가 맞는지 함께 확인하며\n스스로 점검하는 힘을 길러요.',
  ),
];

/// 온보딩 화면 — PageView로 메타인지 철학을 안내하고 채팅으로 진입한다.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();

  /// 현재 페이지 인덱스(인디케이터·버튼 분기에 사용).
  int _index = 0;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  /// 채팅(메인) 화면으로 이동한다 — "시작하기"·"건너뛰기" 공통 동작.
  void _goToChat() {
    context.go(AppRoutes.chatPath);
  }

  /// 다음 페이지로 부드럽게 넘긴다(마지막 페이지면 호출되지 않음).
  void _next() {
    _pageController.nextPage(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeInOut,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLast = _index == _pages.length - 1;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // 상단 "건너뛰기" — 마지막 페이지에선 숨겨 "시작하기"로 자연 수렴한다.
            Align(
              alignment: Alignment.centerRight,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                child: isLast
                    ? const SizedBox(height: 48)
                    : TextButton(
                        onPressed: _goToChat,
                        child: const Text('건너뛰기'),
                      ),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _pageController,
                itemCount: _pages.length,
                onPageChanged: (i) => setState(() => _index = i),
                itemBuilder: (context, i) => _OnboardingPageView(page: _pages[i]),
              ),
            ),
            // 페이지 인디케이터 — 현재 위치를 점으로만 표시(보상·진척 게임화 아님).
            _PageIndicator(count: _pages.length, index: _index),
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: isLast ? _goToChat : _next,
                  child: Text(isLast ? '시작하기' : '다음'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 온보딩 한 페이지 렌더 — 아이콘·제목·본문을 가운데 정렬로 보여준다.
class _OnboardingPageView extends StatelessWidget {
  const _OnboardingPageView({required this.page});

  final _OnboardingPage page;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(page.icon, size: 96, color: theme.colorScheme.primary),
          const SizedBox(height: 32),
          Text(
            page.title,
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            page.body,
            textAlign: TextAlign.center,
            style: theme.textTheme.bodyLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }
}

/// 페이지 인디케이터 — 현재 페이지를 채운 점으로 표시한다.
class _PageIndicator extends StatelessWidget {
  const _PageIndicator({required this.count, required this.index});

  final int count;
  final int index;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(count, (i) {
        final isActive = i == index;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 240),
          margin: const EdgeInsets.symmetric(horizontal: 4),
          width: isActive ? 24 : 8,
          height: 8,
          decoration: BoxDecoration(
            color: isActive
                ? theme.colorScheme.primary
                : theme.colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(4),
          ),
        );
      }),
    );
  }
}
