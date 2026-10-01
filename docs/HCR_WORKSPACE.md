# HCR-3A 선별장 작업공간

원본 저장소는 `../manyfarm_robotarm`에 전체 클론했습니다. 이 작업공간에는 HCR-3A 관련 파일만 선별 복사했으며, 코드 경로 계산을 유지하기 위해 원래 디렉터리 구조를 보존했습니다.

## 읽을 문서

- [현재 인계](src/sorting_station/HCR3A_CURRENT_HANDOFF.md): 실측값·현재 구현·미확정 사항과 다음 작업. 우선 기준 문서입니다.
- [실행 안내](src/sorting_station/hcr/README.md): D435 환경 생성, 후보 미리보기, 읽기 전용 Modbus 서버와 테스트.
- [이전 기획](src/sorting_station/HCR3A_SORTING_HANDOFF.md): 역사적 참고. HCR IP 192.168.3.1은 오기이며 실측 IP는 192.168.3.100입니다.
- [설계 결정](docs/DECISIONS.md), [임시 인터페이스](docs/INTERFACES.md): 원본의 HCR 관련 절 발췌.
- [복사 목록](docs/IMPORT_MANIFEST.json): 원본 커밋과 복사 당시 파일 SHA256. 실행 안내의 작업경로만 이 PC에 맞춰 수정했습니다.

## 포함한 코드

`src/sorting_station/hcr/`의 Modbus 상수 서버, D435 컬러 입력, A/B/C/D 색상 후보 미리보기, 읽기 전용 bridge, 실행 스크립트, 기존 테스트를 포함합니다. 수확 SO-ARM101/RL, OMX 시뮬레이션·시연 수집, 모델·메시는 전체 클론에 보존됩니다. HCR 코드에는 해당 모듈 의존성이 없습니다.

현재 구현은 후보 미리보기와 읽기 전용 통신입니다. 후보 코드는 START가 아니며 로봇 이동·그리퍼 구동·작업 완료 handshake는 미구현입니다. 새 PC의 IP, NIC, D435 시리얼과 ROI는 현장에서 확인해야 합니다.

## 실행

```bash
cd /home/ubuntu/manyfarm_ws/sorting
bash src/sorting_station/hcr/run_d435_preview.sh
```

첫 실행 전에 실행 안내의 전용 venv 설치 절차를 따릅니다. 생성물은 `outputs/sorting_station/hcr_preview/`에 저장되며 원본 PC의 venv·ROI·state는 가져오지 않았습니다.

```bash
/usr/bin/python3 -m unittest discover -s src/sorting_station/hcr -p 'test_zone_preview.py' -v
```

## 정리 후 검증 (2026-10-01)

기존 테스트 6개(색상, 안정화·우선순위, D435 선택, ROI, TTL, loopback TCP 읽기·쓰기 거절)와 실행 스크립트 구문 검사를 통과했습니다. 실행 안내를 제외한 복사 파일은 원본 SHA256과 일치합니다. 실제 D435 GUI 및 HCR 연결은 실행하지 않았습니다.
