# HCR-3A 노트북 작업 순서

2026-10-01. Ubuntu 24.04 + ROS 2 Jazzy 기준. HCR-3A 선별 작업이며 SO-ARM101 수확/OMX 시연 수집과 별개다.

## 1. 최신 코드 받기

처음 받는 노트북:

```bash
git clone https://github.com/Robot3FinalProject/sorting.git
cd sorting
```

이미 받은 노트북은 해당 sorting 폴더에서:

```bash
git status --short
git pull --ff-only
```

로컬 수정 때문에 pull이 실패하면 덮어쓰지 말고 수정 내용을 먼저 보존한다. 아래 모든 명령은 sorting 저장소 루트 기준이다. 기존 OMX의 scripts/setup.sh는 HCR ROS 설치 스크립트가 아니다.

## 2. ROS 환경과 빌드

Ubuntu 24.04에서 ROS 2 Jazzy가 설치되어 있어야 한다. 설치가 없다면 공식 안내 https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html 를 먼저 따른다. Ubuntu 22.04에 Jazzy 명령을 그대로 적용하지 않는다.

```bash
source /opt/ros/jazzy/setup.bash
sudo apt update
sudo apt install -y python3-colcon-common-extensions python3-opencv python3-numpy ros-jazzy-rclpy ros-jazzy-rosidl-default-generators ros-jazzy-std-srvs
bash src/sorting_station/hcr/build_sorter.sh
```

빌드 결과는 outputs/sorting_station/ros2에 생성된다. 다른 PC의 venv/build/install을 복사하지 않는다. 웹캠은 시스템 Python/OpenCV를 사용한다.

## 3. 먼저 로봇 없이 시험

Rodi 작성 가이드 8절의 터미널 4개를 순서대로 실행한다: 웹캠 → localhost 실행기 → mock_hcr → 더미 관제. a/b/c/d로 사각형을 지정하고 s로 저장한다. 더미 관제에서는 p로 ready 확인 후 s+Enter로 시작한다. 영상 창의 s는 구역 저장, 관제 터미널의 s는 작업 시작이므로 구분한다.

A 빨강을 보여 명령11과 BUSY/완료 횟수를 확인한다. mock은 물체를 실제로 치우지 않으므로 계속 보이면 반복한다. 물체를 치우면 3초 미검출 후 SUCCESS다. c는 새 작업을 막고 진행 중 1회가 끝난 뒤 취소한다.

## 4. Rodi 작성

함께 제공하는 가이드의 2~7절을 따라 신호 → 변수 → 티칭 위치 → PICK_A/B/C/D → PLACE_AND_RETURN → MAIN을 만든다. 표기된 트리는 설명용이며 붙여넣기 스크립트가 아니다. 그리퍼는 미구현으로 남겨 둔다. 주기 쓰기/실제 이동을 검증하기 전 실물 동작을 시작하지 않는다.

## 5. 실물 연결로 전환

```bash
ip -br addr
# 아래 NIC_NAME은 랜선이 연결된 실제 유선 인터페이스 이름으로 바꾼다.
sudo ip addr add 192.168.3.2/24 dev NIC_NAME
ping -I 192.168.3.2 -c 4 192.168.3.100
```

이미 .2 주소가 있으면 추가 명령을 반복하지 않는다. 이는 임시 IP이므로 재부팅 후 확인한다. 로컬 mock 실행기와 mock_hcr를 종료하고 실제 실행기를 시작한다:

```bash
sudo -E bash src/sorting_station/hcr/run_sorter.sh
```

웹캠과 더미 관제는 그대로 사용한다. 이때 관제 s는 실제 HCR 작업 요청이다. 실제 운반 결과는 그리퍼와 놓기 성공 확인까지 구현한 뒤 확인한다.

## 6. 완료 확인과 기록

관제 Result의 red_count+yellow_count가 운반 횟수다. 실패/취소에도 이미 완료한 횟수는 유지된다. 빈 영상은 레인 상류가 비었다는 센서 보장이 아니다. 카메라 정지/미설정은 빈 영상 성공으로 처리하지 않는다.

PC 오류는 물리 비상정지가 아니다. 실물 상태를 확인하고 복구한 뒤 reset_fault를 사용한다. 저널을 삭제해 오류를 숨기거나 불확실한 작업을 자동 재시도하지 않는다.

소프트웨어 검증: 런타임 단위 테스트 17개, 카메라 테스트 6개, ROS/Modbus 통합 시험. Rodi 실제 동작과 그리퍼는 별도 현장 검증 대상이다.
