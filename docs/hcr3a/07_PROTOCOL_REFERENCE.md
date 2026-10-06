# HCR-3A ROS / Modbus 실제 구현 명세

2026-10-06 소스 대조. 기존 선별장 통신 초안의 공통 필드를 유지하고 현 구현의 조건·값을 명시한다. 공통 규약 전체를 구현했다는 뜻은 아니다.

## ROS 엔드포인트와 타입

|방식|경로|타입|주기|
|---|---|---|---|
|Action|/sorter_01/sort_batch|smartfarm_interfaces/action/SortBatch|Goal요청, Feedback1Hz+단계/횟수변화, Result종료|
|Topic|/sorter_01/status|smartfarm_interfaces/msg/SorterStatus|1Hz|
|Service|/sorter_01/reset_fault|std_srvs/srv/Trigger|복구확인후수동호출|

Goal 필드는 robot_id/task_id/batch_id/timestamp, 모두string. Feedback은 robot_id/task_id/batch_id/phase/timestamp(string), red_count/yellow_count(int32). Result는 robot_id/task_id/batch_id/result_code/error_code/error_message/timestamp(string), red_count/yellow_count(int32).

Status는 robot_id/current_task_id/current_batch_id/state/error_code/error_message/boot_id/timestamp(string), receive_ready/ready(bool), sequence(uint64). current_task/batch는 비활성 때 빈 문자열.

## 실제 발행 값

- Status.state: ERROR(고장 latch), SORTING(활성작업), 그 밖에는 IDLE. 초안의 RECEIVING은 이 코드에서 발행하지 않는다.
- Feedback.phase: SCANNING, WAIT_ACK, BUSY, WAIT_READY 및 취소 중 CANCEL_PENDING_ 접두사. 끝에는 SUCCEEDED/CANCELED/ERROR가 보고될 수 있다.
- Result.result_code: SUCCESS/FAILED/CANCELED, ROS 종료 상태 SUCCEEDED/ABORTED/CANCELED와 함께 확인한다.
- ready: 활성작업/고장 없음, 카메라1초내·ready·4ROI유효, HCR주소100쓰기3초내·state1·error0.
- receive_ready: ready && receive_enabled. receive_enabled 기본false이며 실제 반입센서를 자동 인증하지 않는다.
- count는 동일JOB의BUSY→DONE에 한 번 증가. Rodi의DONE이 실제 놓기와복귀를 보장해야 한다. 모션시험/센서없는구성의count를 실물운반검증으로 바꾸지 않는다.

## 요청·완료 핸드셰이크

PC_COMMAND11..42, JOB_ID고정, REQUEST1, BATCH_ACTIVE1 → Rodi ACK_JOB동일+STATE2 → PC REQUEST0 → Rodi동작 → DONE_JOB동일+STATE3 → PC COMMAND0/REQUEST0 → Rodi STATE1. 이후 .5초 뒤 새프레임에서 재판정한다.

PC서버주소192.168.3.2:502, 허용peer192.168.3.100, Unit1. 읽기FC03/04, 쓰기FC06/16. 쓰기는100..103만허용. 주소0~4의Input,100~103의Output명칭은펜던트기준이다. 주소40001을더하지않는다.

|주소|이름|내용|
|---:|---|---|
|0|PC_COMMAND|A11/12 B21/22 C31/32 D41/42|
|1|PC_JOB_ID|운반번호1..65535, 재사용하지않음|
|2|PC_REQUEST|수락요청|
|3|PC_BATCH_ACTIVE|배치활성|
|4|PC_HEARTBEAT|PCtick카운터|
|100|HCR_STATE|0미준비/1READY/2BUSY/3DONE/4ERROR|
|101|HCR_ACK_JOB|수락번호|
|102|HCR_DONE_JOB|완료번호|
|103|HCR_ERROR|0정상/비영오류|

주소100쓰기마다HCR최신성과상태이벤트를갱신한다. 값변경시에만쓰기하면안된다. ACK/DONE/ERROR를먼저,상태를마지막commit으로맞추며쓰레드주기와패킷일관성은펜던트시험으로확인한다. 초기가시후보PoC의주소1~4와호환되지않는다.

## 완료·취소·저널

네구역NO_COLOR연속3초→SUCCESS. WAIT/MIXED/미준비/오래된프레임은성공아님. 이것은색상미검출기준이며상류잔량센서보장이아니다. 취소는발행된1회를DONE/READY까지처리후CANCELED. 오류/timeout은FAILED,기완료개수보존.

SQLite가task중복·결과·개수·jobsequence·fault를보존한다. 같은task재전달은거절하며결과조회/재반환서비스는이패키지에구현되지않았다. 재시작시RUNNING은FAILED/PROCESS_RESTART와고장latch. 정상조건이확인된뒤reset_fault. 저널삭제로재시도하지않는다.

## 관제 연동 경계

bucket_unload SUCCESS와안전이격은관제에서확인한다. 이노드는하역Action이나/control/heartbeat를구독하지않는다. 공통get_task_state서비스·다중PCDDS·물리비상정지·그리퍼파지센서인증을현재코드의완료기능으로기재하지않는다. 동일PCloopback구성은외부관제연결시별도네트워크검증이필요하다.

근거: core.py/node.py/modbus.py, SortBatch.action/SorterStatus.msg. 기존 문서 https://robot3final.atlassian.net/wiki/spaces/3/pages/12746755 .
