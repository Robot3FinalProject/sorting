# HCR-3A 실행·테스트·종료 안내

## 실행 준비

랜선 PC↔HCR, USB웹캠, PC `.2`, 펜던트 프로그램/HOME, 작업공간을 확인한다. 처음에는 낮은 속도로 시험한다. 그리퍼 미구현 복사본의 경로시험 횟수를 실제 파프리카 운반 실적으로 해석하지 않는다.

터미널1 서버:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
sudo -E env ROS_DOMAIN_ID=24 bash src/sorting_station/hcr/run_sorter.sh
```

터미널2 카메라:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
bash src/sorting_station/hcr/run_webcam_preview.sh
```

터미널3 관제:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
env ROS_DOMAIN_ID=24 bash src/sorting_station/hcr/run_dummy_control.sh
```

펜던트에서 메인·STATE_TX 실행. 터미널3에서 p+Enter:

```text
state=IDLE ready=True ... error=NONE local_active=False
```

ready=True 확인 후 s+Enter. 요청 수락 → SCANNING → WAIT_ACK → BUSY → WAIT_READY → 재판정 순서. 짧은 단계는 출력 사이에 지나갈 수 있다. PCHeartbeat가 증가하는 것만으로 전체ready를 보장하지 않는다.

## 단일 경로 시험

A에만 빨강이 보이게 준비하고 s. 첫BUSY에서 관제 터미널에 c를 입력하면 진행중1회와 복귀를 마친다. 이것은 한 회 전용 모드가 아니다. c가 늦으면 다음회가 이미 시작됐을 수 있다. 색이 남아 있으면 자동 재선택한다.

정상 취소 기록 예:

```text
CANCEL_PENDING_BUSY
CANCEL_PENDING_WAIT_READY: 빨강=1 노랑=0 합계=1
CANCELED: 빨강=1 노랑=0 총=1 error=NONE
```

A11/12, B21/22, C31/32, D41/42를 각각 시험한다. 같은 구역 연속 대상, 우선순위, 두색MIXED, 빈영상3초, 취소 후 카운트 보존을 확인한다. 최종 8조합 성공 로그는 전달받은 자료에 없으므로 실제 결과표를 운영자가 보완한다.

## 완료와 취소

네구역 NO_COLOR3초는 SUCCESS. 관제는 누적 Feedback을 매번 더하지 말고 최신값으로 교체, 최종 Result로 확정한다. total은red+yellow. CANCELED/FAILED에서도 이미 DONE확인한 개수는 보존한다. Goal수락/Cancel수락/최종Result는 서로 다른 시점이다.

진행중에는 c → 복귀·최종Result → q 순서로 관제를 종료한다. 이후 펜던트 정지, 카메라 종료, 서버Ctrl+C. 서버를 종료했다고 로봇이 물리적으로 정지했다는 뜻은 아니다.

## 복구

로봇 실물 상태·HOME·카메라·HCR READY를 확인한 뒤 reset_fault를 호출한다. 정확한 명령은 [인수인계](../HCR3A_DESKTOP_HANDOFF.md)의 6절을 따른다. success=False면 조건을 먼저 해결한다. 이전 작업을 자동 재실행하거나 저널을 삭제하지 않는다.

## 로봇 없이 시험

실물 서버를 종료하고 아래 loopback 서버와 별도mock journal을 사용한다.

```bash
bash src/sorting_station/hcr/run_sorter.sh --ros-args -p modbus_host:=127.0.0.1 -p modbus_port:=1502 -p modbus_peer:=127.0.0.1 -p journal:=outputs/sorting_station/hcr_runtime/mock_journal.sqlite3
```

다른 터미널에 ROS환경을 맞춘 뒤 mock_hcr를 실행한다. 실제 HCR 테스트에서는 mock을 실행하지 않는다.

```bash
source /opt/ros/jazzy/setup.bash
source outputs/sorting_station/ros2/install/setup.bash
export ROS_DOMAIN_ID=24
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/config/cyclonedds_local.xml"
ros2 run hcr_sorting mock_hcr --host 127.0.0.1 --port 1502 --cycle-seconds 2
```

웹캠과 더미 관제는 별도 터미널에서 실행한다. mock은 과일을 치우지 않으므로 계속 보이면 시험 카운트가 증가한다.
