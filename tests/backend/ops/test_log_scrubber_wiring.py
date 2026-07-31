"""SEC-11 배선 실재성 — `create_app()`이 루트 로거에 스크러버를 *실제로* 붙이는지.

"저장소에 존재함"과 "돌아감"은 다르다(`tests/infra/test_test_suite_wiring.py` 선례 — CI가
`tests/infra` 199건을 한 번도 실행하지 않았던 2026-07-26 사고와 동형). `PiiSecretScrubberFilter`
클래스가 import 가능한 것과, `create_app()`이 실제로 그것을 루트 로거에 `addFilter`하는 것은
별개 사실이다. 이 테스트는 `app.py`에서 `install_log_scrubber()` 호출을 지우면 반드시
실패하도록, 상태를 능동적으로 초기화한 뒤 `create_app()` 호출 *전/후*를 직접 비교한다.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from whymath_backend.app import create_app
from whymath_backend.ops.log_scrubber import PiiSecretScrubberFilter


def _clear_scrubber_filters(logger: logging.Logger) -> None:
    for existing in list(logger.filters):
        if isinstance(existing, PiiSecretScrubberFilter):
            logger.removeFilter(existing)


class TestRootLoggerWiringReality:
    def test_create_app_attaches_scrubber_to_root_logger(self) -> None:
        """루트 로거에서 스크러버를 지운 뒤 `create_app()`을 부르면 다시 붙는다.

        `app.py`의 `install_log_scrubber()` 호출이 삭제되면 이 테스트는 실패한다 — 필터가
        재부착되지 않으므로. 반대로 필터 클래스만 어딘가에 정의돼 있고 아무도 안 부르는
        상태("존재함")라면 이 테스트가 정확히 그 차이를 잡아낸다.
        """
        root = logging.getLogger()
        _clear_scrubber_filters(root)
        assert not any(
            isinstance(f, PiiSecretScrubberFilter) for f in root.filters
        ), "사전조건 실패 — 다른 테스트가 남긴 스크러버를 제거하지 못함"

        # provider/cache/trace/queue 전부 기본값(지연 구성 — 라이브 인프라 불요, app.py
        # docstring의 "넷 모두 지연이라 앱 구성만으로 라이브 서비스가 필요하지 않다" 그대로).
        create_app()

        assert any(isinstance(f, PiiSecretScrubberFilter) for f in root.filters), (
            "create_app() 이후에도 루트 로거에 PiiSecretScrubberFilter가 없음 — "
            "app.py의 install_log_scrubber() 배선이 지워졌을 가능성"
        )

    def test_wiring_survives_repeated_app_construction_without_duplication(
        self,
    ) -> None:
        """`create_app()`을 여러 번 불러도(테스트 스위트의 흔한 패턴) 필터가 누적되지 않는다."""
        root = logging.getLogger()
        _clear_scrubber_filters(root)

        create_app()
        create_app()
        create_app()

        count = sum(isinstance(f, PiiSecretScrubberFilter) for f in root.filters)
        assert (
            count == 1
        ), f"필터가 {count}개 누적됨 — install_log_scrubber의 중복 방지 실패"

    def test_scrubber_active_end_to_end_through_test_client(self) -> None:
        """`create_app()`으로 만든 실제 앱이 뜬 프로세스에서, 루트 로거로 시크릿을 흘리면 마스킹된다.

        TestClient 생성 자체가 목적이 아니라 — create_app()이 이미 앱 구성 시점(lifespan
        발화와 무관)에 배선을 마쳤음을 HTTP 표면과 함께 확인해 "구성됐지만 실제 요청 경로에선
        안 붙어 있더라" 류의 은닉된 배선 격차를 배제한다.
        """
        root = logging.getLogger()
        _clear_scrubber_filters(root)
        app = create_app()
        TestClient(app)  # lifespan 미발화 상태에서도(=with 없이) 배선이 살아있어야 함

        records: list[logging.LogRecord] = []

        class _Collector(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = _Collector()
        root.addHandler(handler)
        root.setLevel(logging.DEBUG)
        try:
            logging.getLogger("whymath_backend.wiring_probe").warning(
                "테스트 시크릿 유출 시도: sk-testleak000000000000"
            )
        finally:
            root.removeHandler(handler)

        assert records, "핸들러가 레코드를 캡처하지 못함(테스트 배선 오류)"
        rendered = records[-1].getMessage()
        assert "sk-testleak000000000000" not in rendered
        assert "***MASKED***" in rendered


class TestAppPySourceCallsInstall:
    """정적 확인 — `create_app()` 함수 본문이 `install_log_scrubber(...)` 호출을 실제로 담고 있다.

    위 동적 테스트(`TestRootLoggerWiringReality`)가 주 증거이고, 이 테스트는 *왜* 배선이
    사라졌는지(호출 삭제 vs 다른 경로로 우회) 실패 메시지에서 바로 드러나게 하는 보조
    확인이다 — `tests/infra/test_test_suite_wiring.py`가 워크플로 YAML을 파싱해 배선을 직접
    확인하는 것과 동형(문자열 grep이 아니라 AST로 실제 호출문을 찾는다).
    """

    def test_create_app_body_contains_install_log_scrubber_call(self) -> None:
        app_py = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "backend"
            / "whymath_backend"
            / "app.py"
        )
        assert app_py.is_file(), f"app.py를 찾을 수 없음: {app_py}"
        tree = ast.parse(app_py.read_text(encoding="utf-8"), filename=str(app_py))

        create_app_fn = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "create_app"
            ),
            None,
        )
        assert create_app_fn is not None, "app.py에 create_app 함수를 찾을 수 없음"

        calls_install_log_scrubber = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "install_log_scrubber"
            for node in ast.walk(create_app_fn)
        )
        assert calls_install_log_scrubber, (
            "create_app() 본문에서 install_log_scrubber() 호출을 찾지 못함 — "
            "배선이 삭제됐거나 다른 함수로 이동함"
        )
