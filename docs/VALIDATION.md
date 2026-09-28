# 배포 준비 검증 — 2026-09-28

- 원본: manyfarm_robotarm/src/sorting_station 실물 전용 수집기.
- 변경: 개인 Python 절대 경로 제거, 저장소 내부 보정 디렉터리 지정, 고정 LeRobot 버전, GUI OpenCV 설치, USB 고유 경로, 모터 비접속 doctor, 종료 카메라 예외 정리, arming 직전 관측 신선도/유한값 확인.
- 별도 소스 수정 없이 follower 위치 읽기에 num_retry=2 사용(기존 PC의 LeRobot 로컬 수정과 동일 취지).
- 단위4개 PASS: 급격한 초기 명령 제한, 추종 오차 제한, NaN 거부, 저장 수 기준 색상 교대.
- native LeRobot 통합 PASS: 폐기한 시연 제외, top/wrist 합성 RGB3프레임 저장, finalize, 재로드, 이미지 디코딩 및 action 일치.
- Python/Bash/JSON 구문 PASS.
- 설치된 LeRobot0.4.4 / torch2.10.0 환경으로 데이터셋 통합 시험. 완전히 빈 PC의 전체 setup 설치는 미실행. 의존성 전체의 hash lock은 아니며 LeRobot 소스 커밋/주요 패키지 버전을 고정한 구성이다.
- 실제 모터 구동, 실제 두 카메라 동시 스트리밍, 장기간30Hz 유지, 네트워크에 배포한 후 clone 검증은 미실행. 장치 준비 후2개 에피소드로 먼저 점검한다.
- RGB만 지원; depth/카메라 하드웨어 타임스탬프/자동 성공 판정/기존 세션 이어쓰기는 미지원.
