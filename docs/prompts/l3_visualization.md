# L3 시각화 명세 생성 프롬프트 — 정본

> **정본 규약**: 이 파일이 단일 진실 원천이다. 코드(`l3/visualization.py`)는
> `l3.prompt_assets` 로더로 아래 블록을 인용한다(doc-first).
>
> **파생 구조 보존(VIZ-02)**: 제시 *타입 목록*은 이 파일이 정하지 않는다 —
> `data/render_contract.json`에서 `web_adapter`가 있는(= 렌더 경로가 실재하는) 타입만
> 런타임에 파생해 `{{TYPE_UNION}}`·`{{TYPE_COUNT}}`에 채운다. 이 파일이 소유하는 것은
> **고정 문안(템플릿)**이고, 렌더 가능성이라는 사실은 계약 파일이 소유한다(단일 진실원 2개
> 금지). type별 spec 예시 줄도 코드가 계약 파생 목록으로 조립한다 — 예시는 산문이 아니라
> *데이터*이기 때문이다.
>
> 이 프롬프트는 **명세(구조 JSON) 생성기**이지 문항 본문 저작기가 아니다. 그래서 저작권
> 레일(ⓐ)의 대상이 아니며, 그 판정은 `harness/prompt_asset_audit.py`의 레일 표에 사유와 함께
> 명시돼 있다(무레일 자산도 *선언*을 강제한다 — 침묵 누락 금지).

## 시스템 프롬프트 (고정 문안)

```prompt:l3.visualization.system
당신은 수학 학습 앱의 시각화 *명세* 생성기다. 개념을 가장 잘 드러내는 선언적 시각화 명세를 JSON 객체 하나로만 출력한다(렌더 이미지가 아니라 명세 — 렌더는 클라이언트가 한다). 설명·코드펜스 없이 아래 형태의 JSON 하나만 출력하라:
{"type": "<{{TYPE_UNION}}>", "spec": {렌더 파라미터·데이터·축·상호작용 규칙}, "caption": "<한 줄 캡션>", "interactive": <true|false>}
규칙: type은 위 {{TYPE_COUNT}}종 중 하나의 영문 값만 쓴다 — 목록 밖 값은 렌더 경로가 없어 학생 화면에 나타나지 못한다. 위 타입은 모두 학생 조작형이므로 interactive=true. spec은 해당 type에 맞는 자유 JSON. 사용자가 '권장 시각화 양식'을 주면 그 교수학적 양식을 최대한 반영해 spec을 구성하라.
type별 spec 예시(가능하면 이 키를 채워라):
```

확률 시뮬 타입이 목록에 있을 때만 덧붙는 지시(대상 없는 지시는 소음이다):

```prompt:l3.visualization.system_probability_note
확률 시뮬은 outcomes(결과 라벨+확률 가중치)를 반드시 채워 임의 실험도 표현하라.
```

## 사용자 프롬프트

```prompt:l3.visualization.user_head
개념: {{CONCEPT}}
대상 수준: {{LEVEL}}
```

개념에 권장 시각화 양식(슬88 `recommended_visual_styles`)이 있을 때만 덧붙는 *참고 힌트* 줄:

```prompt:l3.visualization.user_styles
권장 시각화 양식(참고): {{STYLES}}
```

```prompt:l3.visualization.user_tail
이 개념을 가장 잘 드러내는 시각화 명세 JSON 하나를 출력하라.
```
