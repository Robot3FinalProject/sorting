# HCR-3A Rodi 프로그램·위치 티칭·그리퍼

사진 기준 Rodi2.009.000 / Build008_G2, CLINK v2.009.000.008. 아래는 펜던트 블록으로 작성하는 논리 설계이며 import 가능한 네이티브 프로젝트나 Rodi Script 문법 보증이 아니다. 정확한 완성 프로그램·좌표는 펜던트에서 별도 백업한다.

## 변수와 티칭

active_job/active_command는 수락한 작업 고정값, last_job은 중복 방지, is_red는 색분기, wait_count는 제한 대기 카운터, state_out은 송신 상태다. 쓰레드와 공유하는 state_out은 같은 변수여야 하며 이름만 같은 별도 지역변수를 만들면 안 된다.

Position에는 XYZ와 Rx/Ry/Rz 등 전체 TCP 자세를 저장한다. Joint에는6관절 전체를 저장한다. P_HOME/Q_HOME, P_A~D_UP/P_A~D_PICK, 배출 P_LEFT/P_RIGHT, 경유 Q_3/Q_34/Q_345를 티칭했다. Q_345/P_RIGHT는 같은 실제 자세, P_HOME/Q_HOME도 일치 여부를 확인한다. 예전 문서의 숫자는 참고값이며 현재 실제 좌표로 복제하지 않는다.

## 서브프로그램

PICK_A: P_A_UP → P_A_PICK → 그리퍼 닫기 → 파지 확인 → P_A_UP → P_HOME. B/C/D는 해당 구역 Position으로 같은 구조다. PLACE_AND_RETURN: Q_3 → Q_34 → Q_345(오른쪽), 빨강이면 P_LEFT, 열기·놓기 확인, 빨강이면 P_RIGHT, Q_34 → Q_3 → Q_HOME. 실제 구조·장애물에 맞춘 추가 경유점이 필요하면 티칭으로 저장한다. J이동 TCP 경로는 직선이 아니므로 구간별 확인이 필요하다.

## 상태 쓰레드

STATE_TX를 쓰레드 프로그램으로 만들고 반복 실행 체크, 기준 주기100ms로 설정한다. 사진에는50ms 설정도 있었다. 쓰레드 안에는 `SET HCR_STATE = state_out`을 넣는다. 무한 LOOP나 MOVE를 넣는 대신 쓰레드의 반복 옵션을 사용한다.

메인 안의 `SET HCR_STATE=0/1/2/3/4`는 위치·값을 유지하고 `SET state_out=...`으로 변경한다. 쓰레드의 `HCR_STATE=state_out`은 변경하지 않는다. ACK/DONE/ERROR를 state_out으로 바꾸지 않는다. 메타데이터와 상태의 패킷 일관성은 실제 구현 확인 대상이다.

## 메인 블록 순서

```text
초기화·통신·실물 HOME 및 잔여 요청 없음 확인
state_out=1
LOOP 항상
  IF PC_BATCH_ACTIVE==1 && PC_REQUEST==1
    active_job=PC_JOB_ID / active_command=PC_COMMAND
    유효명령·새JOB·요청일관성 확인
    HCR_ACK_JOB=active_job
    state_out=2
    PC_REQUEST==0 대기 (10초 제한)
    IF PC_REQUEST==0 && PC_BATCH_ACTIVE==1
       && PC_COMMAND==active_command && PC_JOB_ID==active_job
      IF 유효명령
        is_red=0
        IF (active_command==11 || active_command==21) || (active_command==31 || active_command==41)
          is_red=1
        IF active_command==11 || active_command==12: PICK_A
        IF active_command==21 || active_command==22: PICK_B
        IF active_command==31 || active_command==32: PICK_C
        IF active_command==41 || active_command==42: PICK_D
        PLACE_AND_RETURN  ← 네 구역 IF 밖, 유효명령 IF 안에서 한 번
        놓기·HOME복귀 확인
        last_job=active_job
        HCR_DONE_JOB=active_job
        state_out=3
        PC_COMMAND==0 && PC_REQUEST==0 대기 (10초 제한)
        완료응답 정상: state_out=1
        시간초과: 오류 유지
      ELSE: 오류 유지
    ELSE: 오류 유지
  WAIT 0.1초
```

조건 편집기에서 두 OR묶음을 다시 OR로 묶어도 논리는 같다. 무효명령·기존job·응답시간초과를 모션으로 통과시키지 않는다. 오류는 HCR_ERROR 비영과 state_out4로 유지한다. PCHeartbeat 감시와 이동 중 물리 정지 정책이 작성됐는지는 펜던트 백업 대조 없이 확정하지 않는다.

## 그리퍼: 확인 사실과 최종 설정 미확인 항목

사용자가 D_TOOL_OUT_0은 열기, D_TOOL_OUT_1은 닫기라고 확인했다. 사진에서는 Tool Power24V였다. LS Modbus grip/release121/122 설정을 통한 제어와 별개로 Rodi SET→I/O→Tool I/O 출력을 사용한다.

사용자는 1LOW/0HIGH에서는 열리지만,1초 후1HIGH/0LOW로 한 SET에서 바꾸면 닫히지 않는다고 보고했다. 원인은 확정하지 않았다. 두 신호가 겹치는지, Reverse가0.1초 뒤 출력을 끄는지, 닫기 신호 배선/입력 상태가 정상인지 구분하도록 안내했다.

진단용 제안 순서(최종 해결 사실이 아님):

```text
SET OUT0 LOW
SET OUT1 LOW
WAIT .5초
SET OUT0 HIGH
WAIT 2초
SET OUT0 LOW
WAIT .5초
SET OUT1 HIGH
WAIT 2초
SET OUT1 LOW
WAIT .5초
```

각SET은 출력 하나만 설정하고 Reverse를 해제한다. 사진의 “Reverse ...0.1s” 표기만으로 기능 활성 여부를 확정할 수 없다. 닫기 대기 동안 Tool I/O에서0LOW/1HIGH 유지 여부를 확인한다. 중간 정지 시 마지막 LOW가 실행되지 않았을 수 있다. 두 출력HIGH 동시 활성화는 테스트하지 않는다.

사용자가 전체 작업 완료를 보고했으나 최종 Reverse·펄스/유지시간·파지센서·닫힘 해결 방법은 미전달이다. 센서 없이 대기만 사용한 경우 그 사실을 기록하고 실제 파지 완료 인증과 구분해야 한다.
