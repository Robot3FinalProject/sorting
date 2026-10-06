# HCR-3A 문제 해결 기록

|문제|확인한 원인/범위|조치|
|---|---|---|
|tailscale0 does not match an available interface|기존 CycloneDDS 설정이 사용 불가 인터페이스에 바인딩|repo cyclonedds_local.xml로 lo/명시적 peer 사용|
|관제 p에 status 없음|동일 도메인만으로 root서버/user관제 discovery 문제가 해결되지 않았음|두 스크립트에 공통 ros_local_env 적용, 별도프로세스 통신·사용자 연결 성공 확인|
|펜던트 HCR_STATE1인데 ready=False|주소100 쓰기가1회뿐이면3초 뒤 신선도 소실|READY 대기 루프 및 이동 중 STATE_TX로 같은 값도 반복쓰기|
|BUSY 약3초 후 HCR_COMM_TIMEOUT|긴 WAIT/모션 동안 상태쓰기 중단|STATE_TX 병렬 반복 송신; PC timeout만 늘려 숨기지 않음|
|CAMERA_UNAVAILABLE, 영상은 정상|편집/일시정지/신선도/관측구조 오류 또는 시간읽기 경합 가능|ready·age·counter 확인, node.tick 순서 수정|
|카메라창에서 c 후 ready 해제|c는 C구역편집 단축키|취소는 더미 관제 터미널에 입력|
|LS grip=1 오류45611/code4|사진의 Slave device failure; 정확한 LS장치/배선 미확인|주소만 바꿔 그리퍼 제어로 단정하지 않음; 현재 Tool I/O 방향 확인|
|그리퍼 열림 후 닫힘 안됨|출력0열기/1닫기 확인. 원인은 미확정|열기LOW→간격→닫기HIGH로 분리, Reverse/실제 출력 확인 제안|
|서버 재시작해도 error 유지|SQLite fault latch 보존 설계|정상 조건 확인 후 reset_fault|

## 카메라 시간 경합 수정

이전 코드: monotonic 시각을 먼저 샘플링 → camera state.json 읽기. 사이에 새프레임이 저장되면 age=now-frame_time이 음수가 되어 camera_good이 false가 될 수 있었다.

수정 코드: Modbus 이벤트 drain → 카메라 파일 읽기 → monotonic 샘플링 → 상태기계 tick. 미래 데이터 거절 자체를 없애거나 camera_timeout을 늘리지 않았다. runtime에 camera_ready/camera_age_seconds를 추가했다. 경합을 재현한 actual tick 검증 및 core/Modbus시험을 수행했다. 당시 사용자 오류의 단일 원인은 상세 이력이 없어 확정하지 않았다.

## 진단 명령

```bash
cd /home/ubuntu/manyfarm_ws/sorting
python3 -m json.tool outputs/sorting_station/hcr_runtime/runtime.json
python3 -m json.tool outputs/sorting_station/hcr_preview/state.json
```

runtime: phase/error/robot_state/robot_connected/camera_ready/camera_age_seconds. camera: ready/monotonic/counter/session/zone_states. 카메라정상이어도 robot_connectedfalse면ready는false다. error는복구 후명시 해제해야 한다.

## 오류 코드와 제한시간 — 실제 코드

카메라1초, HCR3초, ACK10초, 운반120초, READY10초, scene60초, 배치1800초. ROS파라미터 변경 가능하나 장애를 숨기려고 무조건 늘리지 않는다.

코드에 CAMERA_UNAVAILABLE/CAMERA_SESSION_CHANGED/HCR_COMM_TIMEOUT/READY_WITHOUT_DONE/WAIT_ACK_TIMEOUT/BUSY_TIMEOUT/WAIT_READY_TIMEOUT/BATCH_TIMEOUT/VISION_UNRESOLVED/PROCESS_RESTART/JOB_ID_EXHAUSTED/MODBUS_EVENT_OVERFLOW 및 HCR_ERROR_<번호>가 있다. 공통 운영 규약의 추상 오류와 같은 코드라고 임의 매핑하지 않는다.

PC가 FAILED를 반환하면 신규 요청을 끊고 fault를 저장하지만 물리 비상정지 신호는 포함하지 않는다. 현장 정지/물체 유지 확인 후 복구한다.
