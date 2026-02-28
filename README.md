# HA Qwen3 TTS

Home Assistant 내부(`/config`)에 Qwen3-TTS 런타임을 자체 설치해서 음성을 생성하고, `media_player`로 재생하는 커스텀 통합입니다.

참고 구현: `/Users/iambaek/.openclaw/workspace/skills/qwen3-tts/qwen3-tts.skill`

## 1) 설치

이 저장소의 `custom_components/ha_qwen3_tts` 폴더를 Home Assistant의 `config/custom_components/` 아래로 복사합니다.

최종 경로:

`/config/custom_components/ha_qwen3_tts`

## 2) configuration.yaml

```yaml
ha_qwen3_tts:
  runtime_dir: /config/ha_qwen3_tts/runtime
  python_bin: /config/ha_qwen3_tts/runtime/venv/bin/python
  auto_install: true
  qwen_package_url: https://github.com/QwenLM/Qwen3-TTS/archive/refs/heads/main.zip
  output_dir: /config/www/tts
  base_url: /local/tts
  default_language: Korean
  default_speaker: Sohee
```

이후 Home Assistant를 재시작합니다.

## 3) 서비스 호출

서비스: `ha_qwen3_tts.speak`

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
4. `media_player_entity_id`가 있으면 `/local/tts/<파일명>.wav` 재생

## 참고

- 모델 다운로드/설치가 처음 1회 오래 걸릴 수 있습니다.
- `qwen_package_url`을 내부 미러 주소로 바꿔 오프라인/사내망에 맞출 수 있습니다.
