// 이미지 선택 경계 — 카메라·갤러리에서 풀이 사진 1장을 고르는 서비스.
//
// 경계·테스트 가능성(CLAUDE.md·token_store.dart 답습): image_picker는 플랫폼 채널이라
// `flutter test`에서 직접 검증 불가하다 — 추상 인터페이스([ImageSourceService])로 감싸고,
// 실 구현([PickerImageSourceService])은 통합/수동 검증·소비자(컨트롤러)는 fake로 단위 테스트한다.
//
// 미성년 풀이 데이터(민감정보): 고른 이미지는 *업로드 직후 휘발*한다 — 클라가 평문 장기
// 저장하지 않는다(저장·재학습은 서버 책임·CLAUDE.md). imageQuality로 압축해 모바일 데이터를
// 아낀다(원본 그대로 보내지 않음).
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

/// 풀이 이미지를 어디서 고를지 — 카메라(즉석 촬영)·갤러리(저장된 사진).
enum OcrImageSource {
  /// 카메라로 즉석 촬영.
  camera,

  /// 갤러리에서 저장된 사진 선택.
  gallery,
}

/// 선택된 이미지 — 표시(파일 경로)·전송(바이트·파일명)에 필요한 최소 정보만.
///
/// 플랫폼 파일 객체(`dart:io` File)에 직접 의존하지 않고 바이트·경로·파일명만 들고 다닌다
/// (테스트에서 가짜 바이트로 주입하기 쉽고·웹/멀티플랫폼에도 안전).
class PickedImage {
  const PickedImage({
    required this.bytes,
    required this.path,
    required this.fileName,
  });

  /// 이미지 바이트(업로드 multipart 본문).
  final Uint8List bytes;

  /// 로컬 파일 경로(화면 미리보기용).
  final String path;

  /// 업로드 파일명(확장자 포함·서버 디코드 힌트).
  final String fileName;
}

/// 이미지 선택 경계 — 한 장을 고르거나(취소면 null) 반환한다.
abstract interface class ImageSourceService {
  /// 주어진 [source]에서 이미지 한 장을 고른다. 사용자가 취소하면 null.
  Future<PickedImage?> pick(OcrImageSource source);
}

/// image_picker 기반 실 구현 — 카메라/갤러리 모달을 띄워 한 장을 고른다.
///
/// 플랫폼 채널이라 `flutter test`에서 직접 검증 불가(통합/수동) — 소비자는 [ImageSourceService]
/// fake로 단위 테스트한다(token_store.dart의 SecureTokenStore와 같은 방침).
class PickerImageSourceService implements ImageSourceService {
  PickerImageSourceService([ImagePicker? picker])
      : _picker = picker ?? ImagePicker();

  final ImagePicker _picker;

  /// JPEG 압축 품질(0~100) — 모바일 데이터 절약·서버 디코드 부담 완화(원본 미전송).
  static const int _imageQuality = 85;

  @override
  Future<PickedImage?> pick(OcrImageSource source) async {
    final xfile = await _picker.pickImage(
      source: source == OcrImageSource.camera
          ? ImageSource.camera
          : ImageSource.gallery,
      imageQuality: _imageQuality,
    );
    if (xfile == null) {
      return null; // 사용자가 취소함(에러가 아님).
    }
    final bytes = await xfile.readAsBytes();
    return PickedImage(bytes: bytes, path: xfile.path, fileName: xfile.name);
  }
}

/// 앱 전역 이미지 선택 서비스 provider — 실 구현 주입(테스트는 fake로 override).
final imageSourceServiceProvider = Provider<ImageSourceService>(
  (ref) => PickerImageSourceService(),
);
