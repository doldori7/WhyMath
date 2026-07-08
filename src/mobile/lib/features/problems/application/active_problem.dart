// 활성 문제 provider — 진단→문제제시에서 확보한 문제를 코치 세션(Slice 2 소비처)으로 나른다.
//
// 경계(CLAUDE.md): 단순 표현 상태다. 문제 화면이 "풀이 시작" 시 활성 문제를 세팅하고, 코치 화면이
// 이를 읽어 세션을 problem_id에 묶는다(Slice 2). 코치 화면이 문제 화면을 알 필요 없이 provider
// 하나로 단방향 전달한다(feature 간 직접 의존 회피).
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/problem_models.dart';

/// 현재 학습 중인 문제(없으면 null) — 진단 화면이 세팅·코치 화면이 소비.
final activeProblemProvider = StateProvider<Problem?>((ref) => null);
