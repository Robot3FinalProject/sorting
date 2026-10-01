# HCR-3A 선별장 인계 — 2026-10-01

다른 노트북의 Codex가 이 파일부터 읽도록 작성했다. 이 문서는 **현장 확인값**, **현재 코드**, **미확정 설계**를 구분한다. 저장소 경로는 새 노트북의 checkout 위치에 맞춰 바꾼다. 프로젝트 공통 지침은 루트 `AGENTS.md`, `docs/PROJECT_CONTEXT.md`, `docs/TEAM_ROLES.md`, `docs/DECISIONS.md`를 따른다. 이전 기획은 `HCR3A_SORTING_HANDOFF.md`, 실행 세부사항은 `hcr/README.md`에 있다. **이전 기획 문서에 적힌 HCR IP `192.168.3.1`은 오래된 오기이며 아래 실측 IP가 맞다.**

## 목표와 작업 경계

- 실제 선별 로봇은 Hanwha Robotics **HCR-3A**. 기존 OMX 시뮬레이션·시연 수집 코드는 보존한다.
- D435 컬러 영상에 사용자가 지정한 고정 사각형 A/B/C/D를 분석한다. 각 구역의 빨강·노랑 판정에서 기본 우선순위 **A > B > C > D**의 후보 하나를 고른다.
- 최종 목표는 HCR의 Rodi 프로그램에 구역별 Pick pose, 색상별 배출 pose, 그리퍼 동작을 티칭하고 PC와 작업 수락·완료 handshake를 연결하는 것이다. **현재 구현은 후보 미리보기와 읽기 전용 통신까지만**이다. 관절 구동, START, 완료 판정은 구현되지 않았다.
- 실물 구역에는 물체 하나가 반복 가능한 Pick 위치에 놓이는 기구 또는 공급 방식이 필요하다. 단순 색상 판정은 물체의 3D 파지 자세를 제공하지 않는다.

## 현장에서 확인한 장치와 통신

| 항목 | 확인 내용 |
|---|---|
| HCR IP | `192.168.3.100`, 서브넷 `255.255.255.0`, 펜던트에 표시된 기본 게이트웨이 `192.168.3.1` |
| 기존 PC 시험용 IP | 유선 `eno1`에 임시 보조 IP `192.168.3.2/24` 추가. HCR ping 4/4 성공, 평균 약 0.261 ms |
| HCR Rodi Modbus 장치 | 이름 `PC`, IP `192.168.3.2`, Slave ID `1`로 등록 |
| HCR Rodi Modbus 신호 | `PC_TEST`, Signal Address `0`, `Register Input`, 수량 `1`, 갱신 `10 Hz` |
| 읽기 시험 | PC 서버가 제공한 숫자 `123`, 이후 `310`이 펜던트에 표시됨. 앞의 `0`을 보존하는 문자열 `0310`이 아니라 정수 `310` |

**새 노트북은 `192.168.3.2`를 그대로 가진다고 가정하지 않는다.** 랜선 연결 후 해당 주소가 다른 장치에 쓰이지 않는지 확인하고 PC IP를 설정한다. PC IP를 바꾸면 HCR Rodi의 `PC` 디바이스 IP와 서버 bind 주소도 함께 바꿔야 한다. 임시 `ip addr add` 설정은 재부팅 후 사라질 수 있다. 기존 PC에서 쓴 명령 예시는 `sudo ip addr add 192.168.3.2/24 dev eno1`과 `ping -I 192.168.3.2 -c 4 192.168.3.100`이다. 새 노트북에서는 NIC 이름을 `ip -br addr`로 먼저 확인한다.

현재 검증한 방향은 **HCR이 PC의 Modbus TCP 서버를 읽는 방향**이다. PC가 HCR에 쓰거나 HCR이 PC에 BUSY/DONE을 쓰는 경로는 아직 검증하지 않았다. `LS / 192.168.3.80`은 펜던트에 이미 있던 별도 Modbus 장치로 보이며 용도 미확인이다. 기존 `LS` 설정을 수정하지 않는다.

## 현재 코드와 실행

파일은 모두 `src/sorting_station/hcr/`에 있다.

| 파일 | 역할 |
|---|---|
| `modbus_test_server.py` | 상수 `123` 또는 `--value 310` 제공, FC03/04 읽기 전용 |
| `zone_preview.py` | A~D ROI 지정, HSV 빨강/노랑, 우선순위, 시각화, JSON state 출력 |
| `realsense_camera.py` | D435 시리얼 확인 후 BGR8 컬러 스트림 취득. Depth 미사용 |
| `run_d435_preview.sh` | D435 미리보기 실행기 |
| `zone_modbus_bridge.py` | JSON 후보를 Modbus 읽기 레지스터로 제공, 모든 쓰기 거절 |
| `test_zone_preview.py` | 색상·우선순위·ROI·D435 선택·TTL·loopback TCP 검사 |

기존 PC에서 확인된 D435는 시리얼 **`920312070027`**, USB 2.1 연결, 컬러 BGR8 **640×480 @ 30 fps**다. RealSense SDK를 사용하는 전용 venv는 `outputs/sorting_station/hcr_preview/venv`에 만들었고 `pyrealsense2==2.58.4.10922`를 설치했다. `outputs/`는 생성물 경로이므로 다른 노트북에 설치된 venv가 있다고 가정하지 않는다. 새 노트북에서는 `hcr/README.md`의 환경 생성 절차를 따른다. D435가 여러 대면 `--serial`을 지정하며, D435가 없으면 다른 웹캠으로 자동 대체하지 않는다.

```bash
cd <새 checkout 경로>
bash src/sorting_station/hcr/run_d435_preview.sh
```

창에서 `a`를 누르고 A 사각형을 마우스로 지정한다. `b`, `c`, `d`도 같은 방식이다. `s`로 저장, Space로 일시정지, `q`로 종료한다. D435 ROI 파일은 `outputs/sorting_station/hcr_preview/d435_zones.json`, 현재 후보 JSON은 `outputs/sorting_station/hcr_preview/state.json`이다. 새 노트북으로 ROI 파일을 복사할 수 있지만 **카메라의 위치·각도·해상도가 같을 때만** 사용하고 실제 화면에서 구역을 다시 확인한다. 소스 키에는 D435 시리얼과 스트림 설정이 포함된다.

HCR에서 후보를 보려면 기존 상수 테스트 서버를 종료하고 별도 터미널에서 다음을 실행한다. Modbus 기본 포트 `502` bind에 sudo가 필요했던 PC 기준이다.

```bash
cd <새 checkout 경로>
sudo /usr/bin/python3 src/sorting_station/hcr/zone_modbus_bridge.py
```

새 노트북에 PC IP를 다르게 설정했다면 bridge의 `--host <PC IP>`를 지정한다. HCR IP를 바꿨다면 `--peer <HCR IP>`도 지정한다. 실제 프로세스 실행 전에 `ss -ltn '( sport = :502 )'`로 옛 서버가 남았는지 확인한다. `sudo` 없이 카메라 GUI를 실행하고 bridge에만 필요한 권한을 준다.

테스트용 Modbus 주소 0은 다음 정수 후보를 반환한다.

| 구역 | 빨강 | 노랑 |
|---|---:|---:|
| A | 11 | 12 |
| B | 21 | 22 |
| C | 31 | 32 |
| D | 41 | 42 |

`0`은 현재 유효한 후보가 없다는 뜻이다. 주소 1=구역 번호(1..4), 2=색상(빨강1/노랑2), 3=유효 여부, 4=프레임 카운터다. 한 요청에서 주소 0~4를 함께 읽으면 동일 snapshot이다. UI 편집·정지·종료, JSON 오류, 1초 이상 갱신 중단은 후보 0으로 처리한다. **이 값은 작업 실행 요청이 아니다.** 물체가 그대로 보이면 후보도 계속 유지되므로 현재 값에 Rodi 이동 시퀀스를 바로 연결하면 중복 실행될 수 있다.

현재 HSV 기준은 빨강 H0..10/170..179, 노랑 H18..38, 채도 90 이상, 밝기 60 이상, ROI 면적 8% 이상, 0.3초 동일 판정이다. 두 색상 동시 검출은 `MIXED`, 검출 실패는 `NO_COLOR`, 안정화 중은 `WAIT`로 선택에서 제외한다. `NO_COLOR`가 빈 구역을 증명하지 않는다. 현장 조명·배경·실제 파프리카 모형에서 기준을 조정해야 한다. 물체 여러 개, 가림, 그리퍼/팔이 색상 영역에 들어오는 상황은 아직 검증되지 않았다.

2026-09-29 검증: 단위·loopback TCP 테스트 6개 통과, 합성 미리보기 15프레임, 기존 OpenCV 카메라 3프레임, **실제 D435 SDK 컬러 60프레임 취득**. D435 GUI에서 실제 ROI 마우스 설정, 실제 색상 튜닝, 동적 후보 11..42가 HCR 펜던트에 반영되는지까지는 아직 현장 확인이 필요하다. 사용자 확인은 상수 123/310 읽기까지다.

## Rodi와 그리퍼 조사

- HCR의 프로그래밍 환경은 **Rodi**다. 한화 공식 자료실에 HCR-3A 사용자 매뉴얼과 Rodi Script Programming Guide가 있다: https://hanwharobotics.com/en/newsroom/download?menuSeq=85
- **RODI Off-Line Simulator**라는 Windows PC용 제품이 공급업체에 소개되어 있다. 로봇 없이 PC에서 작성·시뮬레이션 가능하다는 설명이지만, 현재 장비 버전 호환성·설치파일·라이선스·Linux 지원 여부는 미확인: https://corobotics.pl/produkty/oprogramowanie/rodi-off-line/
- RoboDK는 한화용 오프라인 프로그램 생성과 선택형 실시간 드라이버를 안내한다. 문서에는 Rodi `2.001.003.012` 이상 조건 및 드라이버/플러그인 문의가 적혀 있다. 이 장비의 Rodi 버전은 아직 읽지 못했다: https://robodk.com/doc/ko/Robots-Hanwha.html
- `.file` 예제 프로그램과 `.script` 파일을 사용하는 HCR 연동 사례가 있다. 이것만으로 임의 작성 파일이 현장 Rodi에 바로 import된다고 확정하지 않는다: https://docs.pickit3d.com/en/latest/robots/robot-brands/hanwha/hanwha_installation_and_setup.html
- **티칭펜던트 원격 화면 접속/원격 편집은 아직 지원 여부와 접속 경로를 확인하지 못했다.** Modbus 연결은 화면 편집 경로가 아니다. 실제 pose는 현장 티칭·충돌 확인이 필요하다.
- 사진의 그리퍼 라벨은 JRT **`JEGH-3520P-A-Y003`**, S/N `Z02004`로 보였다. JEGH-3520 계열 제조사 카탈로그는 DC24V, 내장 드라이브, Digital Input 4개/Output 3개, 속도·힘·스트로크 설정을 기재한다. 그러나 `P-A-Y003`의 정확한 핀맵과 HCR 배선, Rodi DO/DI 매핑은 미확인이다: https://www.hannovermesse.de/apollo/hannover_messe_2026/obs/Binary/A1516375/JRT_ELECTRIC%20GRIPPER_ENG.pdf
- 사용자는 **그리퍼 제어는 나중에 진행**하기로 했다. 현재 펜던트 수동 제어의 6 joint 목록에 그리퍼가 보이지 않는 것은 별도 I/O 구동 액추에이터라면 자연스럽다. 확인되지 않은 DO 번호나 전압 극성으로 시험하지 않는다.

## 이어서 할 일

1. 새 노트북에서 저장소와 D435, HCR LAN 연결을 확인하고 위 명령으로 미리보기를 실행한다. ROI 저장 후 실제 빨강·노랑 물체로 오검출을 확인한다.
2. 읽기 전용 bridge와 펜던트의 `PC_TEST`로 0, 11..42 변화가 일치하는지 확인한다. 기본 state 파일이 동일 경로인지 확인한다.
3. 펜던트의 **Rodi 버전**, 프로그램 **내보내기/가져오기 메뉴**, 가능한 경우 작은 **이동 없는 예제 프로그램 파일**을 확보한다. 이를 바탕으로 PC 작성 형식을 판단한다.
4. 실제 시퀀스 전에 PC↔HCR READY/BUSY/DONE/JOB_ID handshake, 타임아웃, 구역 재촬영, 중복 작업 방지를 설계하고 시험한다. 주소 0의 현재 후보 코드를 START로 해석하지 않는다.
5. 구역별 Pick/안전 이탈 pose와 빨강·노랑 배출 pose를 실물에서 티칭하고, 그리퍼 배선/매뉴얼 확인 후 별도로 통합한다.

기획 초안의 예시 register 주소 100/101/102 등은 **확정 주소가 아니다**. ROS 2 상위 인터페이스도 미확정이다. 새 인터페이스를 도입한다면 `docs/INTERFACES.md`를 먼저 갱신하고, 결정 변경은 `docs/DECISIONS.md`에 기록한다.
