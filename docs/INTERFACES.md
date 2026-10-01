# HCR-3A INTERFACES

원본 저장소 docs/INTERFACES.md에서 HCR 관련 절만 발췌했습니다.

## 2026-09-29 HCR 카메라 구역 판정 PoC (운용 계약 아님)

독립 카메라 진단 UI가 A~D ROI를 HSV로 판정하고 A>B>C>D 기본 우선순위의 선택 후보를 출력한다. 기본 더미 JSON 출력이며 선택형 PC Modbus 서버를 HCR이 읽는다. 동작 START/작업 실행/완료 handshake는 구현하지 않는다.

테스트용 unit1, FC03/04 읽기 전용: 주소0=구역*10+색상(0=선택없음, A빨강11/A노랑12/.../D노랑42), 1=구역(0..4), 2=색상(0/빨강1/노랑2), 3=유효여부, 4=프레임 카운터(mod65536). 다중 레지스터는 한 요청에서 읽어야 일관된 snapshot이다. 원본영상 갱신이1초 이상 멈추거나 UI 편집/정지/미설정이면 후보0. 모든 쓰기 거부. 현재 후보는 작업 요청이 아니며 실물 시퀀스와 연결하지 않는다.


## 2026-10-01 — HCR 선별 배치 실행 인터페이스 v1

사용자 지시에 따라 `/sorter_01/sort_batch` Action Server와 `/sorter_01/status` Topic을 구현한다. 참조는 Confluence page12746755 v6(2026-10-01). 실제 타입은 이 저장소의 `smartfarm_interfaces/action/SortBatch`, `smartfarm_interfaces/msg/SorterStatus`로 구체화하며 관제도 같은 패키지를 사용해야 한다. Goal의robot_id/task_id/batch_id/timestamp, Result의result_code/red_count/yellow_count/error_code/error_message, Feedback의phase/누적개수와식별자를 보존한다. 총운반횟수는 red_count+yellow_count. 상태1Hz, Feedback1Hz및상태/개수변경시. 동일task_id는영속기록으로중복수락거부. 선별중receive_ready/ready=false. 반입준비는운영자가설정한receive_enabled와장치준비조건으로계산하며실물반입센서검증은아니다.

종료정책은 사용자요청으로 변경: 복귀 후 새 영상에서4구역모두 NO_COLOR가연속3초(설정가능)일때SUCCESS. WAIT/MIXED/미설정/정지/카메라오류는종료근거가아니다. 이정책은상류레인막힘이나색상미검출물체까지비었음을증명하지않는다. 배치시작후에도같은미검출시간을적용한다. 안정화대기기본0.5초. A완료후A재선택가능. 계수는일치하는BUSY수락과DONE(정상놓기+초기위치복귀)의작업번호당한번.

### Modbus 실행용 맵 (기존 preview 서버와 동시 사용 금지)

PC서버/HCR클라이언트,port502/unit1. FC03/04읽기,FC06/16은100..103만쓰기허용. HCR프로그램수정필수. 주소0은기존11/12/21/22/31/32/41/42값유지. 주소1..4는preview의미와호환되지않는다.

| 주소 | 소유자 | 의미 |
|---|---|---|
|0|PC|COMMAND: 대기0, 구역*10+색상. 요청/운반중고정 |
|1|PC|JOB_ID: 1..65535, SQLite에영속증가,재사용없음,소진시오류 |
|2|PC|REQUEST: 수락전1,일치BUSY수신후0 |
|3|PC|BATCH_ACTIVE: Goal처리중1 |
|4|PC|PC heartbeat: 제어tick별증가,통신정지시HCR측신규수락차단에사용 |
|100|HCR|STATE: 0미준비,1READY,2BUSY,3DONE,4ERROR |
|101|HCR|ACK_JOB_ID: 로컬에복사해수락한작업번호 |
|102|HCR|DONE_JOB_ID: 정상놓기및초기위치복귀를완료한작업번호 |
|103|HCR|ERROR_CODE: 정상0,장치오류비영 |

HCR은101/102/103을먼저갱신하고100을마지막에써서상태를commit한다(또는100..103 FC16원자쓰기). 상태100을최소1Hz로반복쓰기;PC는3초미갱신을통신고장으로판정. BUSY는PC가REQUEST=0을보일때까지유지해야한다. DONE은PC COMMAND=0/REQUEST=0확인까지유지한후READY. PC는READY확인및복귀후새영상안정화후다음작업. 로봇은REQUEST를대기중에만수락,active_command/active_job에복사한값으로실행. 현재PC서버는HCR관절/그리퍼이동을구현하지않는다.

취소는새작업을막고이미발행한요청/운반의DONE과READY를기다린뒤CANCELED. 완료된운반개수보존. timeout/통신고장은FAILED와오류latch;물리정지명령은아니므로HCR측오류정리필요. `/sorter_01/reset_fault` Trigger는현장복구후READY/카메라준비가확인될때만latch해제. PC재시작시미완료작업은재실행하지않고중단기록/오류latch. 최초서버가동만으로작업을발행하지않는다.
