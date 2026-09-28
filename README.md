# Sorting — OMX 실물 파프리카 시연 수집

OMX-L 리더 + OMX-F 팔로워, 상단 D435와 손목 USB 카메라로 **실물 모방학습 데이터**를 수집한다. Isaac Sim/Lab, ROS, 기존 manyfarm 작업공간 없이 실행한다.

미리보기에서 `f → s → 동작 → s → y`로 한 에피소드를 저장한다. 실패한 시연은 `n`으로 버리고 재시도한다. 빨강은 왼쪽, 노랑은 오른쪽 창고로 분류한다.

## 새 PC 설치

지원 대상: Ubuntu 22.04/24.04 x86_64, Python 3.10–3.12, 데스크톱 세션. 녹화에는 NVIDIA GPU가 필요하지 않다. 인터넷과 설치용 디스크 공간이 필요하다.

```bash
sudo apt update
sudo apt install -y git python3-venv python3-dev ffmpeg libgl1 libglib2.0-0 libxcb-xinerama0
# 로봇/USB 카메라 장치 권한. 적용 후 로그아웃→로그인.
sudo usermod -aG dialout,video "$USER"

git clone https://github.com/Robot3FinalProject/sorting.git
cd sorting
bash scripts/setup.sh
```

설치는 저장소 내부 `.venv`에 한다. LeRobot 소스 커밋과 주요 라이브러리를 고정한다. 리더/팔로워 드라이버의 별도 로컬 수정은 필요 없다. 설치 스크립트는 LeRobot 의존성인 headless OpenCV를 GUI OpenCV로 교체한다(따라서 `pip check`의 headless 패키지 미설치 보고는 예상된다). 추후 LeRobot을 재설치했다면 setup을 다시 실행한다.

## 동일 장비를 옮겼을 때

1. 리더·팔로워 USB와 모터 전원을 연결한다. 두 팔이 지지된 상태에서 시작한다.
2. 상단 D435와 손목 Innomaker USB 카메라를 연결한다.
3. 장치 목록 확인:

```bash
.venv/bin/python scripts/doctor.py
cp config/cameras.example.json config/cameras.local.json
```

`config/cameras.local.json`의 D435 `serial_number_or_name`을 doctor에 나온 정확한 이름 또는 시리얼로 맞춘다. 손목 카메라는 `/dev/v4l/by-id/...-video-index0` 경로를 사용한다. 이 경로는 `/dev/video2` 같은 순번보다 안정적이다. 화면으로 상단/손목 대응을 확인한다.

실행 스크립트에는 현재 장비 두 대의 USB 고유 경로와 보정 파일이 포함돼 있다. **같은 물리 장비를 다른 PC로 옮기면 ACM 번호가 바뀌어도 연결된다.** 보정 파일을 사용자 홈으로 복사하거나 모터에 덮어쓰지 않고 저장소에서 읽는다. 장치 모드와 보정값이 맞지 않으면 중단한다.

```bash
# 모터 연결 없이 Python/config/포트 경로/보정 파일 점검
bash scripts/collect.sh --check
# 처음에는 두 번만 시험: 빨강 하나, 노랑 하나
EPISODES=2 COLOR_MODE=alternate bash scripts/collect.sh
```

D435 권한 문제가 있으면 Intel 공식 librealsense Linux udev 설치 안내를 따른다: https://github.com/realsenseai/librealsense/blob/master/doc/distribution_linux.md . SDK Python 설치만으로 모든 시스템의 USB 권한까지 설정되지는 않는다.

## 다른 장비 또는 포트 구성

```bash
cp config/hardware.example.env config/hardware.local.env
```

여기에서 `LEADER_PORT`, `FOLLOWER_PORT`, 보정 ID/디렉터리를 변경한다. **다른 팔에 포함된 보정 파일을 그대로 적용하지 않는다.** 해당 팔의 기존 LeRobot 보정 JSON을 별도 디렉터리에 두고 지정한다. 이 수집기는 자동 재보정/모터 모드 변경/전류·PID 변경을 하지 않는다. 기존 LeRobot OMX 설정 완료 상태(팔 mode4, 집게 mode5, 리더 팔 토크 off)가 필요하다. 기구 조립이나 모터 설정이 달라진 장비는 별도 설정이 먼저다.

로컬 설정 파일이 있으면 해당 파일 값이 환경 변수보다 우선한다. `EPISODES`, `COLOR_MODE`는 기본 파일에 없으므로 실행 시 지정 가능하다.

## 조작

| 키 | 동작 |
|---|---|
| `f` | READY 상태에서 추종 시작/중지. 두 팔 각도가 다르면 차이를 출력하고 시작 거부 |
| `Space` 또는 `s` | 녹화 시작 / 녹화 종료 후 REVIEW |
| `y` | REVIEW에서 성공 시연 저장 |
| `n` | REVIEW에서 폐기 후 같은 색상 재시도 |
| `q`, Ctrl-C | 종료. 이미 저장한 에피소드는 보존, 미확인 녹화는 폐기 |

미리보기 창은 키만 누른다. 터미널은 문자+Enter(빈 Enter는 s)다. 창고 도착까지 확인하고 종료·저장한다. 검토 중 추종은 중단되며 마지막 목표를 유지한다. 다음 시연을 준비할 때 f를 다시 눌러 추종을 시작한다. 자동 HOME 복귀와 자동 성공 판정은 없다.

`alternate`는 **저장 성공마다 빨강→노랑**을 바꾼다. 물체 색상은 자동 인식하지 않으므로 화면의 목표 색상과 실제 집는 물체를 맞춘다. `red`, `yellow`로 고정할 수도 있다.

종료 시 현재 측정 위치를 목표로 설정하려고 시도하며 토크를 유지한다. 전원 차단/토크 해제 전 팔을 받친다. 통신 오류가 있으면 이 유지 명령도 실패할 수 있다. 목표 변화율/추종 오차 제한과250ms지연 감시는 충돌 방지나 하드웨어 비상정지가 아니다.

## 첫 100개 수집 계획

카메라·선별장·조명을 고정한다. 팔이 닿는 투입 영역에서 중앙/왼쪽 앞/오른쪽 앞/왼쪽 뒤/오른쪽 뒤의 다섯 위치를 정한다. 각 에피소드는 준비 자세→한 개 집기→창고 도착까지이며 끝나면 창고를 비운다.

| 세션 | 환경 | 성공 수 |
|---|---|---:|
| 1 | 단일 과실. 다섯 위치 각각 빨강/노랑 × 꼭지 왼쪽/오른쪽. 두 바퀴 반복 | 40 |
| 2 | 빨강2+노랑2, 집게가 들어갈 간격. 한 개 분류 후 네 개로 복구하고 전체 재배치 | 40 |
| 3 | 빨강2+노랑2, 일부 가깝거나 닿게 배치. 쌓지 않고 한 개씩 분류 후 재배치 | 20 |

각 세션에서 `EPISODES=40` 또는20, `COLOR_MODE=alternate`를 지정한다. 실패는 n으로 버리며 표의 횟수는 저장 성공 기준이다. 100개는 최초 학습/평가를 위한 계획이지 성능 보장 수량은 아니다.

## 저장 형식과 범위

`outputs/sorting_station/real_demos/<시각>/`에 native LeRobot 데이터셋을 만든다. 새 실행은 새 세션이며 기존 경로 덮어쓰기/이어쓰기는 하지 않는다. Git이나 Hugging Face Hub로 데이터를 자동 업로드하지 않는다.

- `observation.state`: 실제 팔로워 관절6개
- `action`: 제한 적용 후 실제 송신한 관절 목표6개
- `observation.images.top`, `.wrist`: RGB 이미지(현재 depth 저장 미지원)
- `task`: 색상/목표 창고 설명
- `observation.wall_time`: 호스트 실측 경과시간. 표준 `timestamp`는 명목 FPS 기준
- `collection_config.json`: 실행 옵션과 카메라 설정

LeRobot 단위는 팔 -100..100, 집게0..100이며 rad가 아니다. 영상·관절은 하드웨어 동기화하지 않는다. SDK 최신 영상과 관절 관측을 기록하며 현재 구현은 영상 촬영 시각을 따로 저장하지 않는다. 과도한 지연은 녹화를 중지하므로 FPS/USB 대역폭을 점검한다. depth:true는 지원하지 않으므로 오류로 거부한다.

## 검증

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/smoke_dataset.py
```

단위검사와 합성 두 카메라 데이터의 폐기/저장/재로드를 제공한다. 소프트웨어 테스트 통과가 실제 장비 동작 검증을 뜻하지 않는다. 현재 물리 팔의 수집 실행은 이 배포 작업에서 수행하지 않았다.
