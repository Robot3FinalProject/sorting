# HCR-3A 선별장 전환 및 PC 연동 핸드오프

> 최신 인수인계 (2026-10-06): [데스크탑 실행·복구·현장 상태](../../docs/HCR3A_DESKTOP_HANDOFF.md)를 먼저 확인하세요. 아래는 작성 당시 기록이며 상태 쓰레드·그리퍼·DDS·카메라 설정은 최신 인수인계를 우선합니다.

## 1. 변경 배경

기존 선별장은 ROBOTIS OMX 계열 로봇팔을 기준으로 구성되어 있었으나, 현재 실제 선별 로봇을 **Hanwha Robotics HCR-3A 협동로봇**으로 변경해야 한다.

기존 선별장 기능 중 다음은 유지한다.

- 빨간색 파프리카용 미끄럼틀
- 노란색 파프리카용 미끄럼틀
- 카메라 기반 색상 판정
- 파프리카를 지정 위치에서 집어서 색상별 배출 위치에 놓는 Pick & Place

변경이 필요한 부분은 다음이다.

- OMX 기반 로봇팔 제어/티칭 구조 → HCR-3A 기반 티칭 시퀀스
- 여러 파프리카를 쏟았을 때 HCR이 집을 수 있도록 **1개씩 분리(singulation) 또는 고정 슬롯 배치**
- 카메라 판정 결과를 HCR-3A에 전달하는 인터페이스
- 기존 PLC 아이디어 대신 가능하면 **PC/ROS2 코드가 PLC 역할을 수행**하도록 구성

---

## 2. 목표 동작 개념

선별장에는 여러 개의 고정 구역(Zone)을 두고, 각 구역은 HCR-3A에서 미리 Pick Pose를 티칭한다.

예시:

- Zone 1
- Zone 2
- Zone 3
- Zone 4

카메라는 각 Zone에 대해 다음 상태를 판정한다.

```text
Zone 1 : EMPTY
Zone 2 : RED
Zone 3 : YELLOW
Zone 4 : RED
```

PC/ROS2 쪽에서 우선순위를 적용하여 하나의 작업만 선택한다.

예:

```text
우선순위
Zone 1 > Zone 2 > Zone 3 > Zone 4
```

위 상태에서는 Zone 2가 먼저 선택된다.

PC가 HCR에 전달할 논리 명령은 다음 정도로 단순화한다.

```text
ZONE_ID = 2
COLOR   = RED
START   = 1
```

HCR 내부에서는 실제 로봇 동작을 수행한다.

```text
START 수신
↓
ZONE_ID 확인
↓
Zone 2 접근
↓
Pick
↓
COLOR 확인
↓
RED → Red Slide
YELLOW → Yellow Slide
↓
Release
↓
Home
↓
DONE
```

핵심 원칙:

> PC는 어떤 작업을 할지만 결정하고, 실제 Joint/Trajectory/티칭 동작은 HCR 내부 프로그램에서 수행한다.

PC가 HCR 관절을 프레임 단위로 직접 제어하는 구조는 현재 목표에 필요하지 않다.

---

## 3. 추천 소프트웨어 구조

```text
RGB / D435 Camera
        ↓
pepper_detector_node
        ↓
Zone별 상태
        ↓
grading_task_manager_node
        ↓
우선순위 결정
        ↓
hcr_interface_node
        ↓
Ethernet / Modbus TCP
        ↓
HCR-3A Controller
        ↓
Rodi / 티칭 시퀀스
        ↓
Pick
        ↓
RED Slide / YELLOW Slide
```

권장 역할 분리:

### pepper_detector_node

- 고정 카메라 영상 취득
- Zone ROI 정의
- 각 Zone에 파프리카가 있는지 판정
- RED / YELLOW 분류
- 결과 publish

예시 논리 데이터:

```python
[
    {"zone": 1, "state": "EMPTY"},
    {"zone": 2, "state": "OCCUPIED", "color": "RED"},
    {"zone": 3, "state": "OCCUPIED", "color": "YELLOW"},
    {"zone": 4, "state": "OCCUPIED", "color": "RED"},
]
```

### grading_task_manager_node

PLC Ladder 대신 PC에서 동작하는 상태머신이다.

담당:

- Zone 우선순위
- 한 번에 작업 하나만 선택
- 작업 latch
- HCR busy/done 상태 확인
- 동일 파프리카 중복 작업 방지
- timeout/error 처리
- 작업 완료 후 재촬영 또는 상태 갱신

예시 상태:

```text
IDLE
→ SELECT_TARGET
→ SEND_JOB
→ WAIT_ACCEPT
→ WAIT_DONE
→ REFRESH_VISION
→ IDLE
```

### hcr_interface_node

- ROS2 내부 명령을 HCR 통신 형식으로 변환
- Modbus TCP 연결 관리
- Zone / Color / Start 전송
- Busy / Done / Error 수신
- 통신 끊김/timeout 처리

---

## 4. PLC를 사용하지 않는 이유와 대체 구조

처음에는 다음 구조를 검토했다.

```text
Camera PC
→ PLC
→ 24 V Digital I/O
→ HCR
```

하지만 별도 PLC 하드웨어를 준비하면 배선, PLC 프로그램, I/O 극성, 24 V 인터페이스 작업이 추가된다.

현재 프로젝트에서는 아래 구조를 우선한다.

```text
Camera / ROS2 PC
       │
       │ Ethernet
       │
       ↓
    HCR-3A
```

PC 내부 Python/ROS2 노드가 PLC의 다음 역할을 대신한다.

- 입력 상태 관리
- 우선순위 판단
- 작업 latch
- handshake
- timeout
- error state
- 다음 작업 선택

즉 소프트웨어 PLC/state machine 방식이다.

---

## 5. Modbus TCP 개념

Modbus TCP는 PC와 산업 장비가 Ethernet 위에서 정해진 주소의 데이터 값을 읽고 쓰기 위한 산업 통신 방식으로 이해하면 된다.

개념적으로는 양쪽이 공유하는 번호가 붙은 변수/레지스터를 정의하는 방식이다.

예:

```text
100 : ZONE_ID
101 : COLOR
102 : START

200 : BUSY
201 : DONE
202 : ERROR
```

예를 들어 PC가 다음 값을 전달한다.

```text
ZONE_ID = 3
COLOR   = RED
START   = 1
```

HCR은 해당 값을 읽고 미리 저장된 Zone 3 Pick 시퀀스를 실행한 후 상태를 돌려준다.

```text
BUSY = 1
...
BUSY = 0
DONE = 1
```

주의:

- 실제 HCR-3A의 Modbus Client/Server 역할
- Rodi에서 사용하는 정확한 Modbus 설정 절차
- register/digital I/O mapping 방법

은 **사용 중인 HCR-3A 컨트롤러 및 소프트웨어 버전의 공식 매뉴얼을 다시 확인한 뒤 구현**해야 한다. 현재 문서의 register 주소는 설계 예시이며 실제 확정 주소가 아니다.

---

## 6. 권장 Handshake

PC와 HCR 사이에서는 단순히 START 신호만 계속 유지하지 말고 handshake를 둔다.

예시:

```text
PC                          HCR

ZONE/COLOR 설정
START = 1
          ───────────────→

                            명령 수신
                            BUSY = 1

          ←───────────────

BUSY 확인
START = 0
          ───────────────→

                            Pick & Place 실행
                            ↓
                            Home
                            ↓
                            BUSY = 0
                            DONE = 1

          ←───────────────

DONE 확인
상태 갱신 / 재촬영
다음 작업 선택
```

이 구조를 사용해야 같은 파프리카를 반복해서 집는 현상을 줄일 수 있다.

---

## 7. HCR 내부 티칭 구조

HCR에는 Zone별 Pick 위치와 색상별 Place 위치를 미리 티칭한다.

예시 Pose:

```text
HOME

Z1_PRE
Z1_PICK

Z2_PRE
Z2_PICK

Z3_PRE
Z3_PICK

Z4_PRE
Z4_PICK

SAFE

RED_PLACE
YELLOW_PLACE
```

HCR 내부 프로그램의 개념:

```text
Wait START

BUSY ON

Read Zone
Read Color

Switch Zone
    1 → Z1_PRE → Z1_PICK
    2 → Z2_PRE → Z2_PICK
    3 → Z3_PRE → Z3_PICK
    4 → Z4_PRE → Z4_PICK

Gripper Close
Move SAFE

If Color == RED
    Move RED_PLACE
Else
    Move YELLOW_PLACE

Gripper Open
Move HOME

BUSY OFF
DONE ON
```

구체적인 Rodi 명령/문법은 실제 HCR 소프트웨어 버전 확인 후 작성한다.

---

## 8. 파프리카 1개씩 공급하는 메커니즘 검토

문제:

> 이송 로봇이나 트레이에서 여러 파프리카 모형을 한 번에 쏟았을 때 각 Pick 구역에는 하나씩만 들어가야 한다.

단순 격자 칸막이만으로는 특정 구역에 2~3개가 몰릴 가능성이 있어 1개 공급을 보장하기 어렵다.

검토한 후보는 다음과 같다.

### A. Star Wheel

```text
Bulk Hopper
    ↓
좁은 Chute
    ↓
Star Wheel
    ↓
1개씩 배출
    ↓
Inspection / Pick Position
```

장점:

- 게이트보다 비교적 단순한 구조 가능
- 일정 각도 회전마다 1개씩 공급
- 최종 Pick 위치를 하나로 고정 가능
- HCR은 하나의 Pick Pose만 사용할 수도 있음

모형 크기가 비교적 일정할 때 유리하다.

### B. 회전 Pocket Disk

원판 가장자리에 파프리카 한 개가 들어가는 포켓을 여러 개 만든다.

```text
Hopper
 ↓
Pocket Disk
 ↓
Inspection
 ↓
고정 Pick Position
```

장점:

- 1개 분리 신뢰성 높음
- HCR Pick 위치를 고정하기 좋음

단점:

- 회전판, 베어링, 모터, 원점센서 등 기구 제작량 증가

### C. V-shaped Chute / Zigzag Chute

경사로와 벽 형상만으로 파프리카를 한 줄로 정렬한다.

장점:

- 모터가 없어 가장 단순
- 폼보드/3D 프린팅으로 빠르게 제작 가능

단점:

- 파프리카 두 개가 입구에서 wedging/jamming 될 수 있음
- 정확한 1개 분리를 보장하기 어려움

### D. 2단 Escapement Gate

```text
● ● ●
  ↓
G1
  ●
G2
  ↓
Pick Pocket
```

G1과 G2를 번갈아 열어 한 개만 공급한다.

가능하면 서보 1개와 링크를 이용해 두 Gate가 반대로 움직이도록 설계한다.

장점:

- 1개씩 공급 신뢰성이 높음
- 센서와 조합하면 제어하기 쉬움

단점:

- Gate 기구 설계와 actuator 제어 필요

현재 검토 우선순위:

1. **Star Wheel 기반 단일 공급**
2. **2단 Escapement Gate**
3. 회전 Pocket Disk
4. 단순 V/Zigzag Chute

프로젝트 일정과 제작성을 고려하면 Star Wheel 또는 단순 Gate 방식부터 실제 파프리카 모형으로 테스트하는 것이 좋다.

---

## 9. 여러 고정 Zone 방식과 단일 Pick 위치 방식 비교

### 여러 Zone

```text
[P1] [P2] [P3] [P4]
```

각 Zone에 물체를 하나씩 배치한 뒤 HCR이 Zone별로 접근한다.

장점:

- 동시에 여러 파프리카 대기 가능
- 카메라로 여러 Zone을 한 번에 판단 가능

단점:

- 각 Zone에 1개씩 넣어주는 분배 구조 필요
- HCR에 Zone별 Pose를 모두 티칭해야 함

### 단일 Pick 위치

```text
Bulk
 ↓
Singulator
 ↓
[Fixed Pick Position]
 ↓
HCR
```

파프리카를 무조건 한 개씩 동일한 위치에 공급한다.

장점:

- HCR Pick pose 1개
- Vision ROI 1개
- 제어 로직이 크게 단순화

현재 HCR-3A로 변경된 상황에서는 **단일 Pick Position 방식도 적극 검토할 가치가 있다.**

---

## 10. HCR 컨트롤러 네트워크 현재 확인 상태

2026-09-28 현장에서 HCR 티칭펜던트의 네트워크 설정을 확인했다.

확인된 값:

```text
Network Mode : Static IP
HCR IP       : 192.168.3.1
```

티칭펜던트 화면에서 고정 IP가 `192.168.3.1`로 확인되었다.

HCR 컨트롤러 내부에는 RJ45 형태의 포트가 2개 보이며 한쪽은 사용 중이고 한쪽은 비어 있었다. 단, **비어 있는 RJ45가 외부 사용자 Ethernet 포트인지 최종 확인은 아직 필요하다.**

컨트롤러 내부에는 EtherCAT 관련 표기도 있으므로, RJ45 모양만 보고 내부 EtherCAT 포트에 연결하지 않도록 주의한다.

---

## 11. 다음 네트워크 테스트 절차

외부 Ethernet 포트가 확인되면 PC와 HCR을 LAN 케이블로 직접 연결한다.

권장 테스트 PC IP 예:

```text
HCR
IP : 192.168.3.1

Ubuntu PC
IP : 192.168.3.2
```

Subnet Mask는 티칭펜던트에 설정된 값을 그대로 사용한다. 아직 사진상 Subnet Mask는 확실하게 판독하지 못했으므로 추측해서 설정하지 않는다.

PC에서 먼저:

```bash
ip addr
```

그다음:

```bash
ping 192.168.3.1
```

성공하면 다음 단계로 진행한다.

```text
LAN physical link
↓
IP ping
↓
HCR Modbus 설정 확인
↓
Python에서 값 1개 read/write
↓
HCR Rodi에서 해당 값 확인
↓
START/BUSY/DONE handshake
↓
Zone/Color 명령 연결
↓
실제 Pick & Place
```

처음부터 로봇 이동 명령을 연결하지 않는다.

**ping → register/digital 값 1개 통신 확인 → 실제 티칭 시퀀스** 순서로 진행한다.

---

## 12. 구현 시 안전 원칙

- 통신 테스트 단계에서는 HCR 자동 이동 시퀀스를 바로 실행하지 않는다.
- Ethernet 연결과 register read/write를 먼저 확인한다.
- HCR의 움직임을 트리거하는 START 값은 통신이 검증된 뒤 연결한다.
- 통신 끊김/timeout에서는 새 작업을 실행하지 않고 안전 상태로 간다.
- PC에서 같은 START 요청을 반복 전송해도 작업이 중복 실행되지 않도록 job latch/handshake를 구현한다.
- 작업 중 Vision 결과가 바뀌어도 현재 job의 Zone/Color는 완료될 때까지 고정한다.
- HCR 내부 통신용 EtherCAT 인터페이스와 외부 Ethernet 포트를 구분한다.

---

## 13. 기존 sorting_station 코드와의 관계

현재 `src/sorting_station`은 OMX-F/OMX-L 기반 simulation, teleoperation, 실물 시연 수집 코드가 상당량 존재한다.

이번 HCR-3A 전환 시 기존 코드를 무작정 삭제하거나 덮어쓰지 않는다.

권장:

```text
src/sorting_station/
├── 기존 OMX simulation / data collection 코드 유지
│
├── hcr/
│   ├── hcr_interface_node.py
│   ├── grading_task_manager_node.py
│   ├── config/
│   │   └── hcr_modbus.yaml
│   └── README.md
│
└── ...
```

또는 기존 ROS2 package 구조를 확인한 후 별도 `grading_station` package가 이미 있으면 그쪽에 HCR runtime 코드를 두는 것도 가능하다.

**먼저 현재 workspace 구조와 ROS2 package 구성을 확인한 뒤 위치를 확정한다.**

---

## 14. 다음 Codex 작업 우선순위

### P0 — 현장 네트워크 확인

1. HCR 외부 Ethernet 포트 확인
2. HCR Subnet Mask 확인
3. Ubuntu PC 고정 IP 설정
4. `ping 192.168.3.1`
5. HCR의 Modbus TCP 메뉴 및 Client/Server 역할 확인

### P1 — 최소 통신 PoC

1. HCR 매뉴얼 기준 Modbus 설정 확인
2. PC Python에서 Modbus read/write 최소 예제 구현
3. 단일 test value 교환
4. HCR Rodi에서 해당 value 읽기/쓰기 확인

### P2 — Handshake

통신 필드 초안:

```text
PC → HCR
ZONE_ID
COLOR
START
JOB_ID

HCR → PC
READY
BUSY
DONE
ERROR
LAST_JOB_ID
```

정확한 register/address는 실제 HCR 설정 후 확정한다.

### P3 — ROS2 integration

- pepper detector output 정의
- task manager 구현
- hcr interface 구현
- timeout/error/retry
- duplicate job 방지

### P4 — 실제 선별 시퀀스

- Zone 또는 Single Pick Pose 티칭
- RED_PLACE
- YELLOW_PLACE
- gripper open/close
- collision 없는 SAFE/HOME pose
- 저속 dry-run
- 실제 파프리카 모형 테스트

### P5 — 기구 최종 선택

Star Wheel / Gate / Pocket Disk 중 실제 모형 기준으로 jam, repeatability, 제작 난이도 테스트 후 최종 확정한다.

---

## 15. 핵심 결정사항 요약

현재 방향:

```text
별도 PLC 하드웨어 사용하지 않음

Camera
 ↓
ROS2 / Python
 ↓
Vision
 ↓
Software State Machine
 ↓
Ethernet / Modbus TCP
 ↓
HCR-3A
 ↓
미리 티칭한 Pick & Place 실행
```

HCR-3A 네트워크 고정 IP:

```text
192.168.3.1
```

로봇 작업 인터페이스의 핵심 데이터:

```text
ZONE_ID
COLOR
START
BUSY
DONE
ERROR
```

가장 먼저 할 일:

> **PC ↔ HCR Ethernet 연결 및 ping 성공 여부 확인 후 Modbus TCP 최소 통신 PoC를 만든다.**
