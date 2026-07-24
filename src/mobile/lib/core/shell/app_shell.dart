// 하단 탭 네비게이션 셸 — 홈/학습/탐구/나 4탭(MOB-08).
//
// go_router `StatefulShellRoute.indexedStack`가 넘겨주는 [StatefulNavigationShell]을 body로 얹고,
// Material 3 [NavigationBar]로 탭을 전환한다(각 탭은 자체 Scaffold+AppBar를 유지 — 셸은 하단 바만
// 소유). 탭 인덱스·브랜치 상태는 navigationShell이 소유하므로 별도 provider가 필요 없다.
//
// 절대 금기(정서 안전·coding_flutter.md): 배지·스트릭·카운트다운·보상 연출·빨강 강조를 두지 않는다.
// 탭은 4개(설계 문서 01 §4의 "탭 4개 이하 유지"), 라벨은 NavigationDestination의 접근성 라벨이 된다.
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

/// 하단 탭 셸 — 4개 브랜치(홈/학습/탐구/나)를 감싸고 [NavigationBar]로 전환한다.
class AppShell extends StatelessWidget {
  const AppShell({super.key, required this.navigationShell});

  /// go_router가 제공하는 셸 — 현재 탭 인덱스·브랜치 네비게이션을 소유한다.
  final StatefulNavigationShell navigationShell;

  /// 탭 전환 — 같은 탭을 다시 누르면 해당 탭의 첫 화면으로 돌아간다(표준 동작).
  void _onSelect(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: _onSelect,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: '홈',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: '학습',
          ),
          NavigationDestination(
            icon: Icon(Icons.explore_outlined),
            selectedIcon: Icon(Icons.explore),
            label: '탐구',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: '나',
          ),
        ],
      ),
    );
  }
}
