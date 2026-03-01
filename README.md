# HA Qwen3 TTS

Home Assistant Add-on + Custom Component 구성으로 Qwen3-TTS를 이용해 음성을 생성하고 `media_player`로 재생합니다.

- **Add-on**: 독립된 Docker 컨테이너에서 무거운 ML 런타임 실행 (모델 1회 로딩)
- **Custom Component**: Add-on HTTP API를 호출하는 경량 연동

---

## 1) Add-on 설치

### HA Supervisor 사용자 지정 저장소 등록

1. **설정 → 추가 기능 → 추가 기능 스토어 → 우측 상단 메뉴 (점 3개) → 저장소**
2. `https://github.com/iambaek/ha-qwen3-tts` 입력 후 추가
3. 스토어에서 **HA Qwen3 TTS** 검색 → 설치
4. Add-on 옵션(선택 사항):

```yaml
model_id: "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
speaker: "Sohee"
language: "Korean"
```

5. **시작** — 로그에서 `Model loaded and ready` 메시지가 나타날 때까지 대기

> 첫 시작 시 모델을 HuggingFace에서 다운로드하므로 시간이 걸릴 수 있습니다.
> 이후 재시작에는 `/data/hf_cache`에 캐시된 모델을 사용합니다.

---

## 2) Custom Component 설치

### HACS를 통한 설치 (권장)

1. HACS > 오른쪽 상단 메뉴 > **사용자 지정 저장소**
2. 저장소 URL: `https://github.com/iambaek/ha-qwen3-tts`, 카테고리: **통합**
3. 추가 후 `HA Qwen3 TTS` 검색 → 설치

### 수동 설치

`custom_components/ha_qwen3_tts` 폴더를 HA의 `config/custom_components/` 아래로 복사합니다.

최종 경로: `/config/custom_components/ha_qwen3_tts`

---

## 3) configuration.yaml

모든 항목은 선택사항이며 생략하면 기본값이 적용됩니다.

```yaml
ha_qwen3_tts:
  addon_url: http://localhost:5000   # 기본값 (Add-on이 같은 호스트에 있을 때)
  output_dir: /config/www/tts       # 기본값
  base_url: /local/tts              # 기본값 (HA 내부 URL 자동 감지)
  default_language: Korean          # 기본값
  default_speaker: Sohee            # 기본값
```

이후 Home Assistant를 재시작합니다.

### addon_url 설정

| 상황 | 설정 예시 |
|------|----------|
| 기본 (같은 호스트) | `addon_url: http://localhost:5000` |
| Add-on이 별도 서버에 있을 때 | `addon_url: http://192.168.1.100:5000` |

### base_url 설정

| 상황 | 설정 예시 |
|------|----------|
| 기본 (내부망, 자동감지) | `base_url: /local/tts` |
| 외부 접근이 필요한 경우 | `base_url: https://your-ha-domain.com/local/tts` |

`base_url`이 상대 경로(`/local/tts`)이면 HA 내부 URL을 자동 감지하여 미디어 플레이어에 절대 URL을 전달합니다.

---

## 4) 서비스 호출

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

---

## 5) 동작 방식

1. HA가 `ha_qwen3_tts.speak` 서비스를 받으면 Add-on의 `POST /tts`로 HTTP 요청
2. Add-on(Docker)이 이미 메모리에 로딩된 Qwen3 모델로 WAV 생성 → binary 반환
3. Custom Component가 WAV를 `output_dir`(예: `/config/www/tts`)에 저장
4. `media_player_entity_id`가 있으면 HA 내부 URL 기반 절대 URL로 재생 명령 전송

---

## 6) 검증

```bash
# Add-on 상태 확인
curl http://localhost:5000/health

# TTS 생성 테스트
curl -X POST http://localhost:5000/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"안녕하세요"}' \
  --output test.wav
```

---

## 참고

- TTS 요청 타임아웃: **300초**
- Add-on을 별도 서버에서 직접 실행하려면 `docker build` / `docker run` 후 `addon_url`을 해당 주소로 지정하세요.
- Add-on 재시작 시 모델이 캐시(`/data/hf_cache`)에서 로딩되므로 첫 로딩보다 빠릅니다.
