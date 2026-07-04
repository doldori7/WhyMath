"""L1 437↔원자 크로스워크 소비 — 437-키 자산의 원자 축 이전(S0-2·Phase 4-ⓒ).

S0-1이 커밋한 크로스워크 코퍼스(`data/corpus/concept_atom_crosswalk_v1/crosswalk.jsonl`)를
*읽기만* 하여(rekey 금지) 두 437-키 자산을 원자 축에 투영한다:
  ① `concept_node.behavior_skills`(#419 저작) → `atom_node.behavior_skills` (union+dedup·사전순)
  ② `concept_content` K-12 행 → `concept_content.atom_codes` (대학 행 무변경)
"""

from __future__ import annotations
