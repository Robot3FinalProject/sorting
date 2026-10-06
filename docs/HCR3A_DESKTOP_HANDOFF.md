# HCR-3A 선별장 — 데스크탑 인수인계

정리일: 2026-10-06. 사용자는 선별장 작업 완료를 보고했다. 이 문서는 노트북에서 진행한 코드·통신·펜던트 작업을 데스크탑에서 이어받기 위한 현재 기준이다. 이전 문서의 “그리퍼 미구현 / 실물 미시험”은 당시 기록이며 최신 상태는 아래 근거 구분을 따른다.

## 1. 바로 알아야 할 구성

- 대상은 HCR-3A 선별장이다. 기존 OMX/LeRobot 수집 코드와 수확 SO-ARM101 제어는 별도다.
- PC: Ubuntu 24.04, ROS 2 Jazzy, Python 3.12. 노트북 작업 루트는 `/home/ubuntu/manyfarm_ws/sorting`.
- 저장소: https://github.com/Robot3FinalProject/sorting . 원본 전체 참고 저장소: https://github.com/Robot3FinalProject/robotarm . 원본 클론은 노트북의 `/home/ubuntu/manyfarm_ws/manyfarm_robotarm`.
- PC 유선 IP `192.168.3.2/24`, HCR `192.168.3.100/24`. PC가 Modbus TCP 서버 `:502`, HCR이 클라이언트, Slave/Unit ID `1`이다. PC에서 로봇으로 관절 좌표를 직접 보내지 않는다.
- 카메라가 A~D 고정 구역의 빨강·노랑을 판정하고 PC가 명령을 고정한다. Rodi가 티칭 경로로 집기 → 배출 → HOME 복귀를 수행하고 ACK/DONE을 PC에 보고한다.
- 현재 실행 스크립트는 CycloneDDS / ROS_DOMAIN_ID=24 / 명시적 loopback peer를 사용한다. 이 설정은 같은 PC의 더미 관제 시험용이다. 다른 PC의 실제 관제 연결은 이 loopback 설정 그대로는 되지 않는다.
- Tool I/O는 사용자 현장 확인으로 `D_TOOL_OUT_0=열기`, `D_TOOL_OUT_1=닫기`. 마지막 닫힘 문제의 최종 해결 설정·파지 센서 조건은 전달받은 기록에 없어 임의로 확정하지 않는다.

## 2. 데스크탑으로 가져오는 방법

데스크탑에서 작업공간으로 사용할 폴더로 이동한 다음:

```bash
git clone https://github.com/Robot3FinalProject/sorting.git
cd sorting
```

이미 클론했다면 그 저장소에서 `git status --short`로 수정 여부를 확인한 후 `git pull --ff-only`한다. 로컬 수정을 덮어쓰지 않는다. 데스크탑의 경로가 다르면 아래 절대 경로를 자신의 저장소 경로로 바꾼다.

노트북의 빌드·venv를 복사하지 말고 ROS Jazzy를 설치한 데스크탑에서 새로 빌드한다.

```bash
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions python3-opencv python3-numpy ros-jazzy-rclpy ros-jazzy-rosidl-default-generators ros-jazzy-std-srvs ros-jazzy-rmw-cyclonedds-cpp
bash src/sorting_station/hcr/build_sorter.sh
```

빌드 결과는 `outputs/sorting_station/ros2/`이다. 실제 NIC 이름은 `ip -br addr`로 확인하고 데스크탑 유선 연결에 `192.168.3.2/24`를 설정한다. 노트북과 데스크탑을 같은 망에서 동시에 `.2`로 켜지 않는다. 노트북의 NetworkManager 프로필 UUID는 데스크탑에서 재사용하지 않는다.

```bash
ip -br addr
ping -I 192.168.3.2 -c 4 192.168.3.100
```

## 3. 실행 — 터미널 3개와 펜던트

아래 명령은 노트북의 경로다. 데스크탑에서는 각 `cd`를 실제 클론 위치로 바꾼다.

터미널 1 — PC 서버:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
sudo -E env ROS_DOMAIN_ID=24 bash src/sorting_station/hcr/run_sorter.sh
```

`Modbus listening on 192.168.3.2:502`가 나오면 그대로 둔다. 과거 `modbus_test_server.py`나 `zone_modbus_bridge.py`, mock 서버와 동시에 실행하지 않는다.

터미널 2 — USB 카메라:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
bash src/sorting_station/hcr/run_webcam_preview.sh
```

자동 선택은 노트북에서 확인한 sysfs 이름 `Wed Camera: Wed Camera`이고 index=0인 장치 1개에 한정한다. 데스크탑에서 다른 웹캠을 사용하면 다음처럼 명시한다. `/dev/videoN` 번호는 고정이 아니다.

```bash
ls -l /dev/v4l/by-id/
bash src/sorting_station/hcr/run_webcam_preview.sh --camera /dev/v4l/by-id/실제_웹캠_경로
```

카메라 창에서 a/b/c/d로 구역 선택 → 드래그 → s로 저장. Space는 일시정지, q는 종료. 반드시 네 구역을 지정한다. 다른 카메라/해상도에서는 ROI를 다시 설정한다. 작업 중 ROI 편집·일시정지·종료는 오류가 될 수 있다.

터미널 3 — 더미 관제:

```bash
cd /home/ubuntu/manyfarm_ws/sorting
env ROS_DOMAIN_ID=24 bash src/sorting_station/hcr/run_dummy_control.sh
```

펜던트에서는 티칭한 HOME과 작업공간을 확인하고 완성한 메인 프로그램 및 STATE_TX를 실행한다. 관제 터미널에서 `p`+Enter → `ready=True`·`error=NONE` 확인 → `s`+Enter로 시작한다. `c`+Enter는 진행 중 1회 완료·복귀 후 취소, `q`는 비활성 상태에서 관제 종료다. 카메라 창의 c는 취소가 아니라 C구역 편집이다.

`s`는 실제 로봇 작업 요청이다. 하역·운송로봇 안전 이격은 운영자/실제 관제가 확인해야 한다. PC 오류·취소는 물리 비상정지 명령이 아니다.

## 4. Modbus와 Rodi 핵심

|주소|펜던트 이름|타입|역할|
|---:|---|---|---|
|0|PC_COMMAND|Register Input|11/12 A, 21/22 B, 31/32 C, 41/42 D; 끝자리 1빨강/2노랑|
|1|PC_JOB_ID|Register Input|한 번 운반의 고유 번호|
|2|PC_REQUEST|Register Input|1요청, BUSY/ACK 확인 후 PC가 0으로 변경|
|3|PC_BATCH_ACTIVE|Register Input|배치 작업 활성|
|4|PC_HEARTBEAT|Register Input|PC 생존 카운터|
|100|HCR_STATE|Register Output|0미준비/1READY/2BUSY/3DONE/4ERROR|
|101|HCR_ACK_JOB|Register Output|수락한 active_job|
|102|HCR_DONE_JOB|Register Output|완료한 active_job|
|103|HCR_ERROR|Register Output|0정상/비영 오류|

Rodi 메인의 상태 설정 대상은 `state_out`이다. 쓰레드 `STATE_TX`는 반복 실행으로 `HCR_STATE = state_out`을 주기 전송한다. 안내 기준 주기는 100ms이며 사진에서 50ms도 확인했다. 메인과 쓰레드는 같은 변수를 참조해야 한다. ACK/DONE/ERROR 신호는 상태 변수와 혼동하지 않는다. 주소100은 값이 같아도 계속 써야 하며 3초 미갱신이면 PC가 통신 오류로 처리한다.

메인은 `PC_BATCH_ACTIVE==1 && PC_REQUEST==1`에서 active_job/active_command를 고정한다. ACK를 쓰고 BUSY, REQUEST=0 확인 후 PICK_A/B/C/D 중 하나와 PLACE_AND_RETURN 실행, 놓기·복귀 후 DONE_JOB을 쓰고 DONE, PC_COMMAND=0과 REQUEST=0 확인 후 READY로 돌아간다. 실제 패킷 순서·공유변수·센서 보장은 펜던트 구현과 대조한다.

## 5. 이번 노트북 작업에서 변경한 코드

|파일|변경|
|---|---|
|src/sorting_station/hcr/run_webcam_preview.sh|USB 웹캠 명시 자동 선택, 내부 카메라로 조용히 대체하지 않음|
|src/sorting_station/hcr/ros_local_env.sh|서버·더미 관제의 동일 CycloneDDS/도메인/loopback 설정|
|config/cyclonedds_local.xml|lo 인터페이스, multicast 끔, 127.0.0.1 peer, auto participant|
|src/sorting_station/hcr/run_sorter.sh, run_dummy_control.sh|ROS setup 뒤 ros_local_env.sh 적용|
|src/sorting_station/hcr_sorting/hcr_sorting/node.py|카메라 파일 읽기 후 monotonic 시각 취득으로 정상 새 프레임의 음수 age 오판 방지; runtime에 camera_ready/camera_age_seconds 추가|
|src/sorting_station/hcr/gripper_tool_io_test.txt|초기 출력별 방향 확인 시험 안내; 최종 현장 설정 파일이 아님|
|docs/HCR3A_MAIN_PROGRAM_STEP_BY_STEP_KR.pdf|이전 단계별 메인 프로그램 안내; 최신 쓰레드·그리퍼 기준은 본 문서 우선|
|config/fastdds_udp_only.xml|실험했던 FastDDS 설정. 현재 실행 스크립트는 사용하지 않음|

## 6. 오류 복구

카메라와 HCR이 실제 대기 상태로 정상화된 후 아래를 실행한다. 오류 해제는 동작 재개 명령이 아니다.

```bash
cd /home/ubuntu/manyfarm_ws/sorting
source /opt/ros/jazzy/setup.bash
source outputs/sorting_station/ros2/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$PWD/config/cyclonedds_local.xml"
export ROS_DOMAIN_ID=24
export ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
unset ROS_LOCALHOST_ONLY
ros2 service call /sorter_01/reset_fault std_srvs/srv/Trigger '{}'
```

`success=True`와 `Fault cleared`를 확인하고 관제에서 p를 다시 입력한다. 실패하면 최신 카메라/HCR READY/무오류/활성 작업 없음 조건을 확인한다. 저널을 삭제해 해결하지 않는다.

진단:

```bash
python3 -m json.tool outputs/sorting_station/hcr_runtime/runtime.json
python3 -m json.tool outputs/sorting_station/hcr_preview/state.json
```

## 7. 데스크탑에서 반드시 확보할 현장 자료

GitHub에 저장되지 않는 `outputs/`에는 ROI, 저널, 빌드가 있다. 코드 클론만으로 펜던트 프로그램과 티칭 좌표는 복원되지 않는다.

1. 완성한 Rodi 메인·STATE_TX·서브프로그램 및 전체 Position/Joint/TCP 설정을 펜던트에서 별도 백업한다. 안내 텍스트를 네이티브 프로젝트로 오인하지 않는다.
2. 카메라 고정 위치·해상도·ROI `outputs/sorting_station/hcr_preview/zones.json`를 백업하되 새 시점이면 재티칭한다.
3. 기존 운영 저널 `outputs/sorting_station/hcr_runtime/journal.sqlite3`은 task/횟수/고장/job sequence를 보존한다. 이관은 서버 정지 후 일관된 SQLite 백업으로 수행하며 실행 중 db파일만 복사하지 않는다. 서버 두 개가 같은 로봇을 제어하지 않도록 한다.
4. 최종 그리퍼 Reverse 설정, 신호 유지/해제 시간, 닫힘 문제 해결 방법과 파지·놓기 확인 조건을 현장 기록에서 확보한다. 아래 테스트 가설을 완료 사실로 바꾸지 않는다.

## 8. 검증 근거와 문서 목차

확인된 현장 기록: PC↔HCR 통신, 펜던트 신호 등록, READY 확인, BUSY→DONE→READY 및 취소 후 red=1/total=1/error=NONE 보고, 변수·서브프로그램·메인 작성 보고, Tool I/O 방향 확인. 사용자는 최종 선별장 완료를 보고했다. 최종 8조합 시험 로그·정확한 좌표·그리퍼 해결 조건은 별도 기록이 없어 새로 꾸며 넣지 않았다.

소프트웨어 기록: 런타임17/카메라6 및 ROS+localhost Modbus 시험. 10/2 카메라 race 수정 검증에서 core14 및 Modbus3 통과, 실제 tick의 새 프레임 경합 재현 검증 통과. 이는 물리 파지 성공률 시험이 아니다.

- [전체 문서 인덱스](hcr3a/00_OVERVIEW.md)
- [설치·네트워크](hcr3a/01_SETUP.md)
- [카메라·색상 판정](hcr3a/02_VISION.md)
- [Rodi·티칭·그리퍼](hcr3a/03_RODI_GRIPPER.md)
- [실행·테스트·종료](hcr3a/04_OPERATIONS.md)
- [문제 해결](hcr3a/05_TROUBLESHOOTING.md)
- [검증·산출물·이력](hcr3a/06_VALIDATION_HISTORY.md)

Confluence 페이지 주소는 [게시 결과](hcr3a/CONFLUENCE_PAGES.json)에 기록한다.

## Confluence 게시 자료

- [HCR-3A 선별장 구현 완료 및 운영 인수인계](https://robot3final.atlassian.net/wiki/spaces/3/pages/30343169)
- [HCR-3A 작업공간·설치·네트워크](https://robot3final.atlassian.net/wiki/spaces/3/pages/29884432)
- [HCR-3A 카메라와 A~D 색상 인식](https://robot3final.atlassian.net/wiki/spaces/3/pages/29884461)
- [HCR-3A Rodi 프로그램·위치 티칭·그리퍼](https://robot3final.atlassian.net/wiki/spaces/3/pages/29720603)
- [HCR-3A 실행·테스트·종료 안내](https://robot3final.atlassian.net/wiki/spaces/3/pages/29949967)
- [HCR-3A 문제 해결 기록](https://robot3final.atlassian.net/wiki/spaces/3/pages/30081029)
- [HCR-3A 검증 결과·산출물·변경 이력](https://robot3final.atlassian.net/wiki/spaces/3/pages/29949996)
