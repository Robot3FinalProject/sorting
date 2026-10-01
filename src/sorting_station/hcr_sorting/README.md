# HCR-3A 웹캠 선별 배치 실행기

2026-10-01. 선별 로봇팔=HCR-3A. 관제 Goal → 웹캠 A/B/C/D 후보 → Modbus 요청 → BUSY → 정상 놓기·초기위치복귀 DONE → READY → 새 영상 재선택. SO101 및 수확 RL 모듈을 사용하지 않는다.

## 현재 구현 및 실제 사용 전 조건

PC 실행기와 ROS/Modbus 통합 테스트가 구현됐다. **실제 Rodi에 아래 handshake를 작성해야 동작한다.** 예전 PC_TEST 읽기 신호만 있는 상태로는 READY 응답이 없어 Goal이 거절된다. PC 코드는 모션 좌표나 그리퍼 동작을 생성하지 않는다. Rodi의 DONE은 '정상 놓기와 초기위치복귀 성공'을 의미해야 한다. 그리퍼 없는 경로시험은 실제 운반 개수 검증이 아니다.

Confluence [선별장 프로토콜](https://robot3final.atlassian.net/wiki/spaces/3/pages/12746755) v6의 필드를 따른다. 이 구현은 실제 ROS 타입을 smartfarm_interfaces로 정했다. 관제 측도 동일 action/msg 정의를 빌드해야 한다. 기존 문서에서 보류였던 종료 기준은 이번 사용자 요청에 따라 '4구역 빨강/노랑 연속 미검출'로 구현했다.

## 설치와 실행 (Ubuntu / ROS 2 Jazzy 검증)

저장소 루트에서 실행한다. 필요한 시스템 패키지는 ROS2 rclpy/rosidl/colcon 및 python3-opencv/python3-numpy/python3-venv다. 웹캠에는 pyrealsense2가 필요 없다. 다른 노트북에서는 기존 venv를 복사하지 않는다.

```bash
bash src/sorting_station/hcr/build_sorter.sh
```

터미널1 — 웹캠 영상, ROI 설정:

```bash
bash src/sorting_station/hcr/run_webcam_preview.sh --camera 0
```

`--camera /dev/v4l/by-id/...`도 가능하다. `a/b/c/d` 누른 뒤 드래그, `s` 저장, Space 미리보기 일시정지, `q` 종료. 4구역 지정 후 Goal을 보낸다. 구역 파일은 outputs/sorting_station/hcr_preview/zones.json이다. 런타임이 활성화된 동안 편집/일시정지/카메라 종료는 카메라 준비 실패로 Action을 FAILED 처리한다. 이는 물리 로봇 정지 명령이 아니므로 실제 운반 중 GUI를 편집하지 않는다.

터미널2 — 실제 로봇팔용 PC 서버. 이전 modbus_test_server/zone_modbus_bridge는 종료한다:

```bash
sudo -E bash src/sorting_station/hcr/run_sorter.sh
```

기본 PC192.168.3.2:502, 허용 로봇팔192.168.3.100. PC IP가 존재해야 한다. 502포트 권한 때문에 sudo를 사용하는 예시다. 서버 GUI는 없으며 웹캠은 일반 사용자로 실행한다. 관제와 ROS_DOMAIN_ID/RMW설정이 같아야 한다. sudo -E는 설정 환경을 전달한다.

```bash
sudo -E bash src/sorting_station/hcr/run_sorter.sh --ros-args \
  -p modbus_host:=192.168.3.2 -p modbus_peer:=192.168.3.100 \
  -p empty_seconds:=3.0 -p settle_seconds:=0.5
```

반입 준비는 센서 자동 인증이 아니다. 운영자가 반입가능 조건을 확인한 뒤 `-p receive_enabled:=true`를 지정해야 /status의 receive_ready가 장치준비 상태와 함께 true가 된다. 기본false. ready는카메라4ROI/최신영상/HCR READY/무오류/무작업일때true다.

터미널3 — 관제 개발자용 Goal 예시(동일 Task ID 재사용 금지):

```bash
source /opt/ros/jazzy/setup.bash
source outputs/sorting_station/ros2/install/setup.bash
ros2 action send_goal /sorter_01/sort_batch smartfarm_interfaces/action/SortBatch \
  '{robot_id: sorter_01, task_id: SORT_TEST_001, batch_id: BATCH_TEST_001, timestamp: "2026-10-01T12:00:00+09:00"}' --feedback
```

관제는 bucket_unload SUCCESS(하역+운송로봇 안전이격)와최신ready=true를확인한뒤Goal을보낸다. 이 노드는하역Action을구독하지않으며그순서보장은관제책임이다. 실행만으로동작요청을내지않는다.

## ROS 계약

- Action `/sorter_01/sort_batch`: Goal은robot_id/task_id/batch_id/timestamp. Feedback은phase/red_count/yellow_count와식별자/시간. Result는SUCCESS/FAILED/CANCELED,누적red_count/yellow_count,error_code/error_message와식별자/시간. **총 운반 횟수=red_count+yellow_count**.
- Topic `/sorter_01/status`: 1Hz, state/current_task_id/current_batch_id/receive_ready/ready/error/boot_id/sequence/timestamp. Feedback은1Hz및phase·개수변경시추가발행.
- 취소: 새 요청 중단, 이미 발행한 한 작업은 일치 BUSY/DONE/READY까지 마친 후 CANCELED. 이 과정 timeout은FAILED. 이미 완료된 수량은보존한다.
- 오류: 새작업중단,명령0,에러latch. 실제로움직이는로봇을정지시키는명령은포함하지않는다. Rodi는PC heartbeat정지/통신오류시신규수락차단과별도오류처리를구현해야한다.
- 복구: 실물 상태 확인과 HCR READY 복구, 카메라 정상화 후 `ros2 service call /sorter_01/reset_fault std_srvs/srv/Trigger '{}'`. 재시작만으로고장latch를해제하지않는다.
- SQLite journal은 outputs/sorting_station/hcr_runtime/journal.sqlite3. task ID와누적개수/결과,job sequence와오류를보존. 동일task재전달은거절하며재실행·카운트초기화하지않는다. 미완료재시작은FAILED/PROCESS_RESTART와latch. 불확실한이전동작은자동재시도하지않는다. SQLite를지우는방식으로복구하지않는다.

## 레지스터 / Rodi 작성 규칙

기존 구역·색상값은 유지: **A빨강11/A노랑12, B21/22, C31/32, D41/42**. 0=요청없음. 실행용맵의주소1..4는옛preview와다르므로혼용하지않는다. HCR이PC서버에연결하는Modbus클라이언트다. Slave ID1, 읽기FC03/04, 쓰기FC06/16.

|주소|펜던트 신호 타입|추천 이름|의미|
|---|---|---|---|
|0|Register Input|PC_COMMAND|명령11..42|
|1|Register Input|PC_JOB_ID|운반1회의고유번호|
|2|Register Input|PC_REQUEST|1=수락요청,수락후0|
|3|Register Input|PC_BATCH_ACTIVE|배치작업활성|
|4|Register Input|PC_HEARTBEAT|PC tick카운터|
|100|Register Output|HCR_STATE|1READY/2BUSY/3DONE/4ERROR/0미준비|
|101|Register Output|HCR_ACK_JOB|수락한작업번호|
|102|Register Output|HCR_DONE_JOB|완료한작업번호|
|103|Register Output|HCR_ERROR|정상0/오류비영|

펜던트 Input/Output은이장비화면의명칭이다. 실제Rodi버전에서Output쓰기가지원되고정확한function을내보내는지먼저이동없이확인한다. 입력/출력모두주기갱신하며 **STATE100은최소1Hz로반복쓰기** 한다. 변경될때만쓰는구성으로는3초heartbeat timeout이발생한다.

Rodi 블록 논리(붙여넣기용 스크립트 문법 아님):

1. 초기화/실물대기위치확인후 ERROR=0, STATE=READY. PC통신정상및heartbeat변화확인.
2. READY에서 BATCH_ACTIVE=1 AND REQUEST=1,유효COMMAND,새JOB_ID를기다린다.
3. active_job/active_command에복사하고JOB_ID/REQUEST를다시읽어변화없는지확인한다. **ACK_JOB을먼저쓰고 STATE=BUSY를마지막에쓴다.** (FC16으로상태블록원자쓰기또는순차쓰기에따른commit규칙.)
4. PC REQUEST=0 응답을확인한다. 그전BUSY를유지한다. 기다림에는timeout/오류분기를둔다.
5. active_command만사용해티칭된선별운반시퀀스를한번실행한다. 카메라실시간명령을재참조하지않는다. BUSY/heartbeat는이동중에도주기갱신한다.
6. 정상놓기및초기위치복귀후 DONE_JOB=active_job을먼저쓰고 STATE=DONE을마지막에쓴다.
7. PC가 COMMAND=0,REQUEST=0으로완료를확인할때까지DONE을유지한다. 이후STATE=READY로돌아가다음요청을기다린다.
8. 고장시ERROR비영,STATE=ERROR. READY로건너뛰어복귀하면PC는READY_WITHOUT_DONE으로실패한다.

PC는BUSY와DONE의동일작업번호를확인해한번만집계한다. A를처리한뒤에도A에다음물체가보이면새job ID로다시A를선택한다. 반드시EMPTY를한프레임봐야재선택하는규칙은없다. job ID는16bit범위에서재사용하지않으며65535소진시JOB_ID_EXHAUSTED. 장기운용시세션확장프로토콜을합의해야한다.

## 종료 및 영상 규칙

복귀READY후0.5초(settle_seconds) 이후취득된새프레임부터재판정한다. 모두NO_COLOR가연속3초(empty_seconds)일때SUCCESS. 시작시빈영상도같은시간후0회SUCCESS. MIXED/WAIT/미설정/정지/프레임1초이상멈춤을빈영상으로처리하지않는다. unresolved상태60초는VISION_UNRESOLVED. HCR상태3초갱신중단,수락10초,운반120초,복귀READY10초,배치1800초가각각기본timeout이며ROS파라미터로설정한다.

이완료조건은사용자가요청한색상미검출기준이다. 위쪽레인에물체가걸렸거나조명때문에색을못보는경우도종료될수있으므로레인상류잔량까지확인한성공을뜻하지않는다. DONE의물리적정상놓기보장도Rodi측센서/프로그램책임이다.

## 로봇 없이 테스트

웹캠 GUI는같이실행하되서버는loopback/1502, 별도journal을사용한다:

```bash
bash src/sorting_station/hcr/run_sorter.sh --ros-args \
  -p modbus_host:=127.0.0.1 -p modbus_port:=1502 -p modbus_peer:=127.0.0.1 \
  -p journal:=outputs/sorting_station/hcr_runtime/mock_journal.sqlite3
```

다른터미널에서ROS환경과install을source한후:

```bash
ros2 run hcr_sorting mock_hcr --host 127.0.0.1 --port 1502 --cycle-seconds 2
```

이mock은모션없이2초뒤DONE을주므로,물체를계속두면A를반복처리하고카운트가계속증가한다. 다음물체/종료시험은카메라앞물체를직접옮겨진행한다. 실제운반개수로해석하지않는다.

```bash
PYTHONPATH=src/sorting_station/hcr_sorting /usr/bin/python3 -m unittest discover -s src/sorting_station/hcr_sorting/tests -v
/usr/bin/python3 -m unittest discover -s src/sorting_station/hcr -p 'test_zone_preview.py' -v
source /opt/ros/jazzy/setup.bash
source outputs/sorting_station/ros2/install/setup.bash
ROS_DOMAIN_ID=87 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST /usr/bin/python3 src/sorting_station/hcr_sorting/tests/ros_integration.py
```

ROS통합시험은합성관측+실제ROS메시지+localhostTCP. 실제카메라/Rodi/그리퍼를조작하지않는다. 실제장비의BUSY/DONE쓰기,ROS관제상호운용,물체선별은현장검증이남아있다.

## Rodi 순서별 가이드와 더미 관제

[Rodi 2.009.000 사진 기준 작성 가이드](RODI_PROGRAMMING_GUIDE_KR.md)에 신호 등록, 변수, 티칭점, PICK 4개, 운반/복귀, 메인 분기, 통신 시험 순서를 정리했다. 사진의 빌드는 008_G2이며 상세 UI와 주기 쓰기는 실물 확인 대상이다.

관제 대신 `bash src/sorting_station/hcr/run_dummy_control.sh`를 실행하고 `p` 상태, `s` 시작, `c` 취소, `q` 종료를 사용한다(각각 Enter). 먼저 build_sorter.sh로 다시 빌드한다. 실제 실행기에 연결하면 실제 작업을 요청한다. 로봇을 흉내내는 mock_hcr와는 역할이 다르다. ROS 인터페이스는 바꾸지 않았다.
