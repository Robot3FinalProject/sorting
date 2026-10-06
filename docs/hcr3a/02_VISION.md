# HCR-3A 카메라와 A~D 색상 인식

## USB 웹캠 선택

`run_webcam_preview.sh`는 OpenCV backend를 사용한다. 자동 선택은 sysfs name=`Wed Camera: Wed Camera` 및 index0 장치가 정확히1개일 때만 한다. 내부 ATIV 카메라를 기본0으로 잘못 선택하던 문제를 해결했다. `/dev/video3`는 당시 번호이며 재연결로 바뀔 수 있다. 다른 장치는 `--camera /dev/v4l/by-id/...`로 지정한다.

RealSense D435 SDK 경로는 run_d435_preview.sh에 보존했다. 과거 D435 RGB640×480@30 시험을 진행했지만 현재 웹캠 실행에 pyrealsense2는 필요 없다. D435와 OpenCV ROI는 별도 설정 파일을 사용한다.

## GUI 사용

1. 카메라를 작업대에 고정한다. 촬영 위치와 레인·티칭점 관계를 확인한다.
2. 카메라 창에서 a → A영역 드래그, b/c/d도 같은 방식으로 지정한다.
3. s로 저장한다. 네 ROI가 모두 있어야 ready 상태다.
4. 빨강·노랑을 각 구역에 넣고 표시 상태를 확인한다.
5. 작업 중에는 편집/Space 일시정지/q 종료를 하지 않는다.

ROI 파일 `outputs/sorting_station/hcr_preview/zones.json`은 source·프레임 크기를 함께 저장한다. 다른 source/해상도와 맞지 않으면 의도적으로 재사용을 거절한다. 무조건 source만 바꿔 우회하지 말고 재설정한다.

카메라 창의 s=ROI저장, c=C구역 편집이다. 더미 관제 터미널의 s=작업 시작, c=취소다. Enter를 포함한 명령은 관제 터미널에 입력한다.

## 판정과 관측 데이터

OpenCV HSV에서 saturation/brightness 필터와 색상 면적비, 안정화 시간을 적용한다. 기본 min_ratio=.08, saturation90, brightness60, stable_seconds=.3이다. 임계값은 설치 조명과 대상에 맞춰 현장 튜닝한다.

|상태|의미|
|---|---|
|RED / YELLOW|안정화된 색 후보|
|NO_COLOR|설정 기준을 만족하는 빨강/노랑 미검출|
|WAIT|안정화 대기|
|MIXED|두색 혼합으로 자동 대상 선택 보류|

관측 JSON에는 monotonic·camera_session·counter·ready·zone_states(A~D)와 후보 zone/color가 있다. 원자적 파일 교체로 읽기 중 반쪽 JSON을 피한다. ready=false는 편집·일시정지·미설정·종료 등에서도 발생하므로 화면이 보이는 것만으로 사용 가능을 확정하지 않는다.

## 대상 선택과 종료

PC는 A→B→C→D 순서에서 RED/YELLOW를 선택한다. command=구역번호×10+색번호(RED1/YELLOW2)다. BUSY 중 카메라 후보가 바뀌어도 발행한 command/job은 유지한다.

DONE·READY 이후 settle_seconds=.5 뒤 새 프레임부터 재선택한다. 같은A에 대상이 남아 있으면 새JOB으로 A를 다시 실행한다. 모든 구역 NO_COLOR 연속 empty_seconds=3이면 SUCCESS, WAIT/MIXED는 빈 영상 성공이 아니다. 후보가 해결되지 않으면 기본60초 VISION_UNRESOLVED.

카메라 데이터는1초 이내여야 한다. 카메라 세션이 작업 중 바뀌면 CAMERA_SESSION_CHANGED, 최신성·준비·구조가 유효하지 않으면 CAMERA_UNAVAILABLE이다. NO_COLOR는 상류 레인까지 물체가 없다는 센서 보장이 아니다.
