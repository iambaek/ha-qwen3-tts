# HA Qwen3 TTS

Home Assistant 내부(`/config`)에 Qwen3-TTS 런타임을 자체 설치해서 음성을 생성하고, `media_player`로 재생하는 커스텀 통합입니다.

## 1) 설치

### HACS를 통한 설치 (권장)

1. HACS > 오른쪽 상단 메뉴 > **사용자 지정 저장소**
2. 저장소 URL: `https://github.com/iambaek/ha-qwen3-tts`, 카테고리: **통합**
3. 추가 후 `HA Qwen3 TTS` 검색 → 설치

### 수동 설치

이 저장소의 `custom_components/ha_qwen3_tts` 폴더를 Home Assistant의 `config/custom_components/` 아래로 복사합니다.

최종 경로:

`/config/custom_components/ha_qwen3_tts`

## 2) configuration.yaml

모든 항목은 선택사항이며 생략하면 기본값이 적용됩니다. `ha_qwen3_tts:` 섹션 자체를 생략해도 기본값으로 동작합니다.

```yaml
ha_qwen3_tts:
  runtime_dir: /config/ha_qwen3_tts/runtime       # 기본값
  python_bin: /config/ha_qwen3_tts/runtime/venv/bin/python  # 기본값
  auto_install: true                               # 기본값
  qwen_package_url: https://github.com/QwenLM/Qwen3-TTS/archive/refs/heads/main.zip  # 기본값
  output_dir: /config/www/tts                      # 기본값
  base_url: /local/tts                             # 기본값 (HA 내부 URL 자동감지)
  default_language: Korean                         # 기본값
  default_speaker: Sohee                           # 기본값
```

이후 Home Assistant를 재시작합니다.

### base_url 설정 안내

| 상황 | 설정 예시 |
|------|----------|
| 기본 (내부망, 자동감지) | `base_url: /local/tts` |
| 외부 접근이 필요한 경우 | `base_url: https://your-ha-domain.com/local/tts` |

`base_url`이 `/local/tts` 같은 상대 경로이면 Home Assistant의 내부 URL을 자동으로 감지하여 Chromecast 등 미디어 플레이어에 절대 URL을 전달합니다. 외부에서 접근해야 하는 경우 `https://` 로 시작하는 전체 URL을 직접 지정하세요.

## 3) 서비스 호출

서비스: `ha_qwen3_tts.speak`

| 파라미터 | 필수 | 설명 |
|----------|------|------|
| `text` | ✅ | 변환할 텍스트 |
| `media_player_entity_id` | ❌ | 재생할 미디어 플레이어 entity_id |
| `language` | ❌ | 언어 (기본값: `Korean`) |
| `speaker` | ❌ | 화자 이름 (기본값: `Sohee`) |

예시:

```yaml
service: ha_qwen3_tts.speak
data:
  text: "안녕하세요. Home Assistant에서 Qwen3 TTS 테스트 중입니다."
  media_player_entity_id: media_player.living_room_speaker
  language: Korean
  speaker: Sohee
```

## 4) 동작 방식

1. 첫 호출 시 `/config/ha_qwen3_tts/runtime`에 venv 생성 + Qwen3-TTS 패키지 설치
2. `qwen3_generate.py`가 Qwen3 모델로 WAV 파일 생성
3. 파일을 `output_dir`(예: `/config/www/tts`)에 저장
4. `media_player_entity_id`가 있으면 HA 내부 URL 기반의 절대 URL(예: `http://192.168.x.x:8123/local/tts/<파일명>.wav`)로 재생 명령 전송

## 참고

- 모델 다운로드/설치가 처음 1회 오래 걸릴 수 있습니다.
- TTS 생성은 최대 **5분** 타임아웃이 적용됩니다. 초과 시 서비스 호출이 실패로 처리됩니다.
- TTS 생성 실패 시 HA 개발자 도구 및 자동화에서 오류 메시지를 확인할 수 있습니다.
- `qwen_package_url`을 내부 미러 주소로 바꿔 오프라인/사내망에 맞출 수 있습니다.
