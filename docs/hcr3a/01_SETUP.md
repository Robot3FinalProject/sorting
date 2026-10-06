# HCR-3A 작업공간·설치·네트워크

## 코드 배치와 이관

노트북 루트 `/home/ubuntu/manyfarm_ws/sorting`, 원본 clone `/home/ubuntu/manyfarm_ws/manyfarm_robotarm`. robotarm에서 HCR 관련 파일을 추려 standalone sorting 저장소로 옮겼고 기존 OMX 수집기·보정 프로필을 유지했다. SO-ARM101 수확 코드는 HCR 실행 경로에 넣지 않았다.

|위치|역할|
|---|---|
|src/sorting_station/hcr|카메라 GUI·Modbus 도구·실행 스크립트|
|src/sorting_station/hcr_sorting/hcr_sorting|ROS 노드, 상태기계, Modbus 서버, 더미 관제, mock|
|src/smartfarm_interfaces|SortBatch.action / SorterStatus.msg|
|config/cyclonedds_local.xml|같은 PC에서 사용할 DDS 설정|
|docs/hcr3a|최신 구현 문서|
|outputs/sorting_station/hcr_preview|ROI zones.json, 최신 state.json|
|outputs/sorting_station/hcr_runtime|runtime.json, journal.sqlite3|
|outputs/sorting_station/ros2|build/install/log 생성물|

GitHub에는 소스·문서를 올리고 outputs/venv/환경 비밀값을 올리지 않는다. 설치 명령과 데스크탑 이관 순서는 [데스크탑 인수인계](../HCR3A_DESKTOP_HANDOFF.md)의 2절을 따른다. ROS Jazzy 설치 후 colcon build를 수행하며 rmw_cyclonedds_cpp 패키지도 필요하다.

## 유선망

|장치|설정|
|---|---|
|PC|192.168.3.2/24, Modbus TCP 서버 502|
|HCR|192.168.3.100/24, Unit ID1, 클라이언트|
|HCR 현장 gateway|192.168.3.1; 동일서브넷 통신에 gateway는 필요 없음|
|과거 LS|192.168.3.80; 장치 정체/연결 미확인, 현재 그리퍼 경로로 사용하지 않음|

노트북 유선 enp3s0에 NetworkManager 영구 정적주소를 설정하고 WiFi 기본 경로를 유지했다. 데스크탑에서는 실제 인터페이스로 별도 설정한다. 이름·프로필 UUID를 그대로 복사하지 않는다.

```bash
ip -br addr
ping -I 192.168.3.2 -c 4 192.168.3.100
```

PC에 `.2`가 없으면 서버 bind가 실패한다. 502는 낮은 포트라 현재 실행 예시는 sudo를 사용한다. HCR이 PC로 접속하는 구조이므로 HCR502에 접속되는지만 검사해서 현재 프로토콜을 검증할 수는 없다.

## DDS 환경

`run_sorter.sh`와 `run_dummy_control.sh`는 ROS/install setup 뒤 ros_local_env.sh를 source한다. RMW=rmw_cyclonedds_cpp, 도메인 기본24, CYCLONEDDS_URI=저장소의 cyclonedds_local.xml, lo 인터페이스/127.0.0.1 peers, multicast=false. ROS_LOCALHOST_ONLY는 unset한다.

과거 tailscale0 바인딩으로 노드 생성 실패, FastDDS 별도 프로세스 상태 미수신을 겪었고 현재 loopback Cyclone 설정으로 사용자 연결 성공을 확인했다. `fastdds_udp_only.xml`은 당시 실험 파일로 현재 비활성이다.

외부 데스크탑 관제를 노트북 실행기에 연결할 때는 루프백 전용 설정을 바꾸고 양쪽 DDS·도메인·네트워크를 검증해야 한다. 현재 same-PC 성공을 다중 PC 성공으로 표현하지 않는다.
