# HCR-3A 검증 결과·산출물·변경 이력

## 완료 상태와 증거 구분

2026-10-06 사용자가 선별장 작업 완료를 보고했다. 문서는 완료 인수인계를 목적으로 한다. 아래 시험은 실제 기록이 있는 범위만 기재하며, 최종 통합시험 전 항목 PASS나 성공률을 추정하지 않는다.

|범위|기록|
|---|---|
|PC↔HCR 네트워크|PC .2정적설정 후 ping4/4, Modbus 통신·펜던트 신호 등록 사용자 확인|
|READY|주기쓰기 수정 후 관제 ready=True 사용자 확인|
|핸드셰이크·취소|BUSY→취소 수락→CANCEL_PENDING_WAIT_READY→CANCELED red1/yellow0/total1/errorNONE 로그|
|펜던트 작성|로컬변수·위치·서브프로그램·메인 작성 완료 사용자 보고/사진|
|Tool I/O|0열기/1닫기 사용자 확인; 닫힘 전환 문제 최종 해결 설정 미전달|
|최종 장비|완료 보고와 현장 사진. 마지막8조합·파지센서·사이클시간 로그는 제공되지 않음|
|코드|core14+Modbus3=17, 카메라6, ROS+localhost Action/Status/Feedback/Result통합 기록|
|카메라race 수정|읽기순서 경합 재현, 실제tick 신규프레임20회 검증, 빌드/source설치 일치 확인|

## 이력

- 9/29: 상수읽기 통신에서 A~D HSV후보 PoC로 확장. 처음에는 읽기전용, 실제 작업요청 없음. 과거 HCR.1 기록을 .100으로 정정.
- 9/29: D435 SDK/시리얼 선택·RGB스트림·별도ROI 시험. 현재 OpenCV웹캠경로와 구분.
- 10/1: sorting저장소에 HCR ROS실행기, 영속JOB, 배치Action, 더미관제·Rodi가이드 동기화. 로컬mock통합시험.
- 10/1~2: 노트북 유선IP, 외장웹캠선택, DDS loopback, 펜던트신호·변수·티칭·서브프로그램·메인 작성. READY/BUSY주기쓰기와 STATE_TX 해결.
- 10/2: 취소 후1회 완료카운트 보존 현장 확인. 카메라 시간비교race 수정 및 진단필드 추가.
- 10/6: Tool I/O0열기/1닫기 확인. 출력전환·Reverse 진단 안내. 사용자 선별장 완료 보고 후 Confluence/데스크탑인수인계/GitHub반영 승인.

## 산출물

|산출물|위치/설명|
|---|---|
|ROS 인터페이스|src/smartfarm_interfaces/action/SortBatch.action, msg/SorterStatus.msg|
|상태기계·저널|hcr_sorting/core.py|
|ROS·진단|hcr_sorting/node.py|
|Modbus TCP|hcr_sorting/modbus.py|
|관제 시험·로봇 mock|dummy_control.py / mock_hcr.py, 역할 구분|
|카메라|hcr/zone_preview.py, realsense_camera.py, 실행 sh|
|최신문서|docs/HCR3A_DESKTOP_HANDOFF.md, docs/hcr3a/|
|이전PDF|docs/HCR3A_MAIN_PROGRAM_STEP_BY_STEP_KR.pdf, HCR3A_RODI_WORKBOOK_KR.pdf|
|그리퍼 초기시험|hcr/gripper_tool_io_test.txt, 네이티브프로그램아님|
|현장 사진|docs/hcr3a/assets/sorting_station_completed.jpg|
|실행기록·ROI|outputs/는git제외. 현장별 별도백업|
|실제 Rodi프로젝트|펜던트별도백업. 이repo의설계도만으로완전복원불가|

## 시험 재실행

```bash
PYTHONPATH=src/sorting_station/hcr_sorting python3 -m unittest discover -s src/sorting_station/hcr_sorting/tests -v
python3 -m unittest discover -s src/sorting_station/hcr -p test_zone_preview.py -v
```

ROS통합시험은Jazzy와install setup 뒤 tests/ros_integration.py를 실행한다. 실제로봇을 흉내내는 localhost시험이며 실물시험과 혼동하지 않는다. 이번 문서게시 자체는 로봇을 구동하지 않는다.

## 장기 운영/연동 시 확인

같은PC loopback설정을실제외부관제DDS로전환, 관제하역·안전이격 확인연동, receive_enabled 기본false와 반입조건, 물리그리퍼완료확인, 저널이관·고장복구를 확인한다. JOB16bit는1~65535를재사용하지않으므로소진시프로토콜확장검토가필요하다. 이것은 완료된현장데모와별개운영범위다.
