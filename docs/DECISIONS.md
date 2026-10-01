# HCR-3A DECISIONS

원본 저장소 docs/DECISIONS.md에서 HCR 관련 절만 발췌했습니다.

## 2026-09-29 — HCR 4구역 카메라 판정 및 읽기 전용 후보 PoC

- 기존안: HCR에서 PC의 상수123/310을 읽는 테스트. 변경안: 독립 HCR 도구에서 수동 사각형A~D와 HSV 빨강/노랑 면적·0.3초 안정화로 A>B>C>D 후보를 생성한다. 기본 더미JSON, 선택형 Modbus bridge로 후보만 노출한다. 이유: 사용자 요청에 따른 시각적 구역·우선순위·통신 확인.
- PC192.168.3.2, HCR192.168.3.100/24, gateway192.168.3.1이 현장 확인값이다. 과거 handoff의 HCR .1은 잘못된 이전 기록이다. 사용자123/310 읽기 확인; HCR→PC 쓰기는 검증/구현하지 않았다.
- 테스트 주소0은 구역*10+색상, 주소1..4는 구역/색상/유효/프레임 카운터. 모든 쓰기 거절, START/실물 동작/handshake 없음. 기본 state는1초 TTL, 중단/편집/미설정은0. 완성된 선별 실행기나 ROS팀 간 확정 계약이 아니다.
- 두색 동시검출은보류. NO_COLOR는빈칸확정이아니다. 현재후보는완료처리가없으며남은물체를자동작업하지않는다. 실물시퀀스연결전job latch/완료/가림/실패후재시도정책을별도구현한다.
- 검증: 단위/loopback5개 통과, 합성영상15프레임 미리보기 렌더 확인, 카메라0에서3프레임 취득. 새프로그램 GUI실조작/실제HCR동적후보수신은현장확인대상. 수확/OMX코드와원본자산은변경없음.

## 2026-09-29 — HCR 구역 판정 카메라를 D435 SDK로 명시

- 기존안: OpenCV 카메라0을 읽어 실제장치 식별이 불명확. 변경안: 기본 backend를 RealSense SDK로 바꾸고 D435를 시리얼로 선택한다. 1대일때만자동선택,여러대는명시적serial필수. RGB전용640×480@30, depth미사용. 이유: 사용자가현재USB연결한D435로확실히실행하도록요청.
- 기존OpenCV는명시적backend옵션으로보존. D435 ROI는별도d435_zones.json과시리얼/스트림source키로저장해웹캠ROI자동재사용을막는다. HCR통신주소/후보의미/실물무동작원칙은유지.
- 전용venv에pyrealsense2 2.58.4.10922설치,시스템/수확Python환경변경없음. 실제D435 920312070027 USB2.1에서BGR8 640×480@30의60프레임취득성공. 명시선택/미연결/다중카메라회귀포함6개테스트통과. 현장ROI재지정과실제색상튜닝은사용자가수행한다.


## 2026-10-01 — HCR 웹캠 ROS 배치 실행 및 완료 handshake

- 기존안: 읽기 전용 후보11..42를실시간표시,ROS Goal/완료없음. 변경안: HCR전용hcr_sorting 패키지와smartfarm_interfaces SortBatch/SorterStatus를구현. 사용자의관제시작→단일운반→복귀후재선택→미검출완료요청에따른다. HCR은수확SO101과분리.
- 기본웹캠은기존ROI GUI를재사용해ready/zone_states/monotonic/session을JSON에추가. Rodi의READY/BUSY/DONE과영속JOB_ID로명령고정/중복집계방지. 같은A색도다음JOB으로반복가능. 초기위치복귀DONE후READY와0.5초후새프레임필수.
- 종료보류였던기존기획을사용자요청으로변경:4구역모두NO_COLOR가連속3초(설정가능)면SUCCESS. WAIT/MIXED/프레임끊김/미설정은성공아님. 상류레인막힘/색미검출물체까지비었다는센서검증은아니다.
- 통신맵:0command,1job,2request,3batch_active,4heartbeat;100state,101ack,102done,103error. 11..42유지,주소1..4의옛preview맵은호환안됨. FC06/16쓰기허용은100..103만. Rodi상태commit·heartbeat·완료유지규칙은실행README참고;실제Rodi프로그래밍/그리퍼동작미구현.
- 카운트는동일job의BUSY→DONE에서한번,정상놓기+복귀를Rodi가보장해야함. Cancel은발행된1회완료후CANCELED,고장은FAILED+latch. journal에task중복/누적수/재시작미완료/오류보존. 전체transport횟수는red+yellow. 시작전하역·운송안전이격은관제책임. receive_ready는운영자receive_enabled와장치ready의결합(기본false).
- 검증: ROS Jazzy 2패키지빌드성공,런타임17+기존카메라6 테스트통과. 실제ROS Action/Feedback/Result/Status와localhost TCP로A빨강2회→B노랑1회→미검출SUCCESS(red2/yellow1),중복task거절,진행중취소후1회보존통과. 합성카메라15프레임새JSON/미리보기실행성공. 실물HCR/웹캠색판정/관제PC상호운용시험은아직미실행.
- 코드 src/sorting_station/hcr_sorting, 실행문서 동README. 생성물 outputs/sorting_station/ros2 및 hcr_runtime. 기존원본URDF/수확RL/학습변경없음.


### 2026-10-01 — HCR Rodi 버전 기록 및 더미 관제

- 기존안: ROS CLI로 선별 Action 수동 전송, 추상적인 Rodi handshake 안내.
- 변경안: 첨부 사진의 Rodi 2.009.000 / 008_G2, CLINK v2.009.000.008을 기록하고 별도 순서별 가이드 추가. 기존 SortBatch/SorterStatus를 사용하는 대화형 더미 관제(s/p/c/q) 추가. ROS 계약 변경 없음.
- 이유: 실제 관제 미완성 상태에서 같은 Action 경로로 시험하고 펜던트 프로그램을 단계별로 작성하기 위함.
- 경계: 실물 Rodi 명령 문법/병렬 통신 기능은 미검증. 그리퍼 미구현 구간은 실운반 성공으로 처리할 수 없음. 더미 관제는 모션 simulator가 아니며 실제 실행기에 Goal을 보내면 실제 동작 요청이 됨.
- 검증: smartfarm_interfaces/hcr_sorting 빌드 성공, 기존 단위 테스트 17개 통과. 실제 ROS+localhost Modbus 통합 시험에서 더미 관제의 Goal 전송, 활성 중 중복 시작 차단, Feedback 수신, 취소 후 1회 완료 CANCELED Result 수신 확인. 실물 동작 미시험.
