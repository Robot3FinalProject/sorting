# HCR-3A 선별장 작업공간

2026-10-01 갱신. 현재 실행 기준은 [노트북 시작 안내](HCR_LAPTOP_START.md)와 [Rodi 가이드](../src/sorting_station/hcr_sorting/RODI_PROGRAMMING_GUIDE_KR.md)다.

HCR 웹캠/ROS/Modbus 실행기를 src/sorting_station/hcr 및 hcr_sorting에, ROS 타입을 src/smartfarm_interfaces에 둔다. OMX 코드는 기존대로 보존한다. 수확 SO-ARM101 코드는 포함하지 않는다.

예전 읽기 전용 후보 도구와 실행용 handshake는 주소1~4 의미가 다르므로 함께 사용하지 않는다. outputs의 가상환경, ROI, 저널, 녹화물은 복사하지 않는다. 새 노트북에서 설치하고 ROI를 다시 지정한다. 기존 IMPORT_MANIFEST.json은 이전 반입 시점의 기록이며 이번 변경 파일의 해시가 아니다.
