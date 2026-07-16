# Discord 음료 주문 추출기

Discord에서 복사한 음료 주문 메시지를 분석해, 주문자·메뉴·온도·사이즈·수량·옵션·디카페인 여부를 자동으로 정리해주는 Python GUI 도구입니다.

## 주요 기능

- Discord 메시지에서 주문 정보 자동 추출
  - 주문자
  - 메뉴
  - 온도(ICE/HOT)
  - 사이즈
  - 수량
  - 옵션
  - 디카페인 수량
  - 비고/확인 상태
- 미확인 주문 분리 표시
  - 확인되지 않은 주문은 별도 섹션으로 구분해 요약합니다.
- 기본 온도 처리
  - 명시적으로 HOT가 없으면 기본값으로 ICE로 처리합니다.
- 메뉴/별칭 설정
  - 콘솔에서 설정 가능
  - GUI에서 메뉴와 별칭을 바로 수정 가능
- CSV 내보내기
  - 추출 결과를 CSV로 저장할 수 있습니다.
- 요약 복사
  - 분석 결과 요약문을 클립보드에 바로 복사할 수 있습니다.

## 실행 방법

Python 3가 설치된 환경에서 다음 명령으로 실행합니다.

```bash
python discord_drink_order_extractor.py
```

## 설정 방법

### 콘솔에서 메뉴/별칭 수정

```bash
python discord_drink_order_extractor.py --configure
```

### 현재 설정 확인

```bash
python discord_drink_order_extractor.py --show-config
```

## 설정 파일

실행 중 메뉴/별칭 설정은 다음 파일에 저장됩니다.

- menu_aliases.json

파일이 없으면 기본 메뉴/별칭 세트가 사용됩니다.

## 프로젝트 구조

- discord_drink_order_extractor.py: 메인 프로그램
- README.md: 프로젝트 설명
- menu_aliases.json: 사용자 설정 파일(실행 시 생성)

## 참고

이 도구는 외부 패키지 없이 Python 표준 라이브러리만 사용합니다.
