# 현재 연결된 D435 실행 (2026-09-29)

```bash
cd /home/ubuntu/manyfarm_ws/sorting
bash src/sorting_station/hcr/run_d435_preview.sh
```

RealSense SDK로 D435 컬러 스트림만 선택한다. 현재 실장치 **920312070027**, USB2.1, BGR8 640×480@30으로60프레임 취득을 확인했다. Depth는 사용하지 않는다. 창 제목과 터미널에서 시리얼을 확인한다. 카메라 창에서 a/b/c/d 후 마우스 드래그, s 저장, Space 일시정지, q 종료는 동일하다. 실행 중인 다른 카메라 프로그램이 있으면 먼저 종료한다.

기본 backend가 realsense로 변경됐다. 다른 웹캠은 `--backend opencv --camera 0`을 명시한다. D435가 없으면 다른 카메라로 자동 대체하지 않는다. 여러 대면 `--serial 920312070027`로 선택한다. 해상도/FPS 옵션은 `--width 640 --height 480 --fps 30`이다. 지원하지 않는 조합은 SDK 오류로 중단한다.

D435 ROI는 `outputs/sorting_station/hcr_preview/d435_zones.json`에 따로 저장한다. 이전 웹캠 ROI를 자동 승계하지 않으므로 처음에는4개 구역을 다시 그린다. 저장 설정에 시리얼/해상도/FPS가 포함되며 다른 카메라/설정에 재사용을 거부한다. 카메라의 물리적 위치 변경은 감지하지 못하므로 재지정해야 한다.

Modbus 서버 명령과 state.json 경로, 주소0의11..42 코드는 그대로다. UI는 sudo 없이 실행한다. SDK 읽기 실패 시 출력0으로 종료하며 별도 bridge의1초 TTL도 유지된다.

현재PC 전용환경 설치완료: `outputs/sorting_station/hcr_preview/venv`, SDK `pyrealsense2==2.58.4.10922`, 시스템 OpenCV4.6.0/numpy 사용. 환경 재생성 시:

```bash
/usr/bin/python3 -m venv --system-site-packages outputs/sorting_station/hcr_preview/venv
outputs/sorting_station/hcr_preview/venv/bin/python -m pip install pyrealsense2==2.58.4.10922
```

SDK 참고: https://github.com/realsenseai/librealsense/tree/master/wrappers/python

# HCR PC Modbus 읽기 테스트

실제 로봇 제어용 서버가 아닌 단일 상수 통신 진단 도구. Python 3 표준 라이브러리만 사용한다.

2026-09-28 사용자 확인: HCR IP는 **192.168.3.100/24**, 게이트웨이는 **192.168.3.1**이다. 이전 핸드오프의 HCR IP `.1` 기록을 정정한다. PC eno1에 보조 IP `192.168.3.2/24` 추가 후 사용자 ping 4/4 성공.

펜던트: 디바이스 PC / IP 192.168.3.2 / Slave ID 1. 신호 PC_TEST / Signal Address 0 / Register Input / 수량 1 / 10 Hz.

```bash
cd /home/ubuntu/manyfarm_ws/sorting
sudo /usr/bin/python3 src/sorting_station/hcr/modbus_test_server.py
```

`Listening`은 서버 준비, `Connected`는 TCP 연결, `READ OK: value=123`은 정상 Modbus 요청에 응답한 상태다. 최종적으로 펜던트 PC_TEST 값 123을 확인한다. Ctrl+C로 종료. PC 보조 IP는 재부팅 시 재설정이 필요할 수 있다. 응답이 없으면 서버 로그/펜던트 오류로 진단하며 방화벽을 일괄 해제하지 않는다.

서버는 PC 보조 IP에만 bind하고 HCR IP의 연결만 허용한다. unit 1, 주소 0, 수량 1에만 123을 반환한다. HCR UI의 Register Input이 실제로 사용하는 function code는 수신 로그로 확인하며 FC03과 FC04 양쪽 읽기를 지원한다. 쓰기를 포함한 다른 function은 exception으로 거절한다. START/출력/로봇 동작 구현 없음. 실제 운용 handshake/ROS 인터페이스/확정 register map이 아니다.

프로토콜 참고: https://modbus.org/docs/Modbus_Application_Protocol_V1_1b3.pdf

테스트 값 변경: 종료 후 `sudo /usr/bin/python3 src/sorting_station/hcr/modbus_test_server.py --value 310`. `--value` 범위는 0..65535, 기본123. 숫자 레지스터이므로 0310의 앞자리0은 보존되지 않는다. 사용자가 펜던트에서123 수신을 확인했으며310은 후속 확인 대상이다.

## 카메라 A/B/C/D 구역 미리보기 (2026-09-29)

현재 PC는 `/usr/bin/python3`에 OpenCV/numpy가 있다. Conda 기본 python에는 cv2가 없으므로 아래 절대 경로를 사용한다. 카메라 프로그램과 통신 서버는 분리되어 GUI를 sudo로 실행할 필요가 없다.

터미널 1 — 카메라와 더미 데이터 생성:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
/usr/bin/python3 src/sorting_station/hcr/zone_preview.py --backend opencv --camera 0
```

- 화면을 클릭해 키 입력 초점을 둔다. `a`를 누르고 마우스로 A 사각형을 드래그한다. `b`, `c`, `d`도 반복한다. 서로 겹치는 구역/5픽셀 미만 구역은 거부한다.
- `s`: ROI 저장. 같은 카메라 이름/해상도에서 다음 실행 시 복원. 카메라를 옮기거나 장치를 바꿨으면 ROI를 다시 지정한다. 카메라 번호는 장치 고유 ID가 아니므로 USB 경로 사용을 권장한다.
- Space: 후보 출력 일시정지/재개. `q`/Esc: 종료. 편집 중에는 후보0.
- 4구역을 모두 설정해야 출력한다. 기본 우선순위 A>B>C>D. `--priority DCBA` 등으로 변경한다.
- 빨강/노랑 HSV 검출 면적이 구역의8% 이상이고0.3초 연속 같은 판정일 때 후보가 된다. `--min-ratio 0.08 --stable-seconds 0.3 --saturation 90 --brightness 60`으로 조정한다. 빨강 H0..10/170..179, 노랑 H18..38 (OpenCV H 범위0..179).
- `MIXED`: 두 색상이 모두 기준 면적을 넘음. `NO_COLOR`: 유효한 빨강/노랑을 검출하지 못함. 빈 구역이라는 보장은 없으며 회색/다른색 물체도 이 상태다. `WAIT`: 안정화 대기. 모두 선택에서 제외한다.
- 화면에 각 구역 색상/색상 면적 비율, 선택 구역/색상/코드를 표시한다. 여러 동색 물체, 배경색, 팔에 의한 가림은 자동 구분하지 못한다. 고정 카메라·중립색 배경·구역당 한 물체에서 먼저 검증한다.
- 결과는 `outputs/sorting_station/hcr_preview/state.json`, ROI는 같은 폴더의 `zones.json`. 기본은 네트워크 없는 더미 출력이다. 같은 state 경로로 두 UI를 동시에 실행하지 않는다.

터미널 2 — HCR에 실제 후보값 전달(선택): 기존123/310 서버를 Ctrl+C로 종료한 후 실행한다.

```bash
cd /home/ubuntu/manyfarm_ws/sorting
sudo /usr/bin/python3 src/sorting_station/hcr/zone_modbus_bridge.py
```

PC192.168.3.2/24 보조IP가 있어야 한다. 기존 PC_TEST 설정(unit1, 주소0, Register Input, 수량1, 10Hz)을 그대로 사용한다. HCR이 PC 서버를 주기적으로 읽는 방식이며 PC가 HCR에 직접 쓰기 명령을 보내는 구조는 아니다.

| 구역 | 빨강 | 노랑 |
|---|---:|---:|
| A | 11 | 12 |
| B | 21 | 22 |
| C | 31 | 32 |
| D | 41 | 42 |

선택없음/편집/정지/카메라 종료/JSON오류/데이터1초만료이면0. UI가 멈추거나 강제 종료되어도 서버는 만료된 후보를0으로 제공한다. 서버 자체가 종료되면 HCR에는 통신 오류가 발생하므로 펜던트에 남아 있는 이전값을 새 데이터로 해석하지 않는다.

추가 읽기 레지스터: 주소1=zone,2=color,3=valid,4=프레임카운터. 한 요청으로 주소0부터 수량5를 읽으면 같은 snapshot이다. 별도 신호로 읽으면 갱신 사이 값이 섞일 수 있다. FC03/04 지원, 모든 쓰기 거절. GUI의 LIVE는 카메라 후보 갱신 상태이지 HCR 수신 확인이 아니다. 통신 서버의 request/response 로그와 펜던트 값을 함께 확인한다.

**이 값은 시각적으로 확인할 현재 후보이며 실제 동작 START가 아니다.** 물체가 남아 있으면 같은 후보가 유지되며 완료/자동 재시도/작업 latch/중복작업 방지 handshake는 아직 없다. 실물 시퀀스에 연결하기 전 별도 작업 프로토콜이 필요하다.

카메라 없이 UI 연습:

```bash
/usr/bin/python3 src/sorting_station/hcr/zone_preview.py --demo --config outputs/sorting_station/hcr_preview/demo/zones.json --state outputs/sorting_station/hcr_preview/demo/state.json
```

데모는 합성 A빨강/B노랑, C/D색상없음. 실제 기본 state와 분리되며, 기본 통신 서버로 데모 데이터가 전달되지 않는다.

검증:

```bash
/usr/bin/python3 -m unittest discover -s src/sorting_station/hcr -p 'test_zone_preview.py' -v
```

5개 테스트: 색상/혼합, 안정화/우선순위, ROI 경계/겹침, TTL/깨진파일, 실제 loopback TCP 읽기 및 쓰기 거절. 합성15프레임 UI 렌더링 확인, 실카메라0에서3프레임 취득 성공. GUI 마우스 조작 및 새 후보값의 HCR 수신은 현장 확인 대상.

HSV 구현 참고: https://docs.opencv.org/4.x/da/d97/tutorial_threshold_inRange.html
