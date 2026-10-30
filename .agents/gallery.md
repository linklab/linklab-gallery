# 갤러리 유지관리

- `scripts/update_gallery.py`는 한국 날짜를 기준으로 iCloud 사진 네 장을 선택하고 `site/`에 생성한다.
- `site/`와 다운로드한 사진을 Git에 추가하지 않는다.
- `python -m pip install -r requirements-dev.txt`로 고정 버전 도구를 설치한다.
- `ruff check --fix --no-unsafe-fixes .`, `ruff format .`, `python -m unittest discover -s tests -v`로 검증한다.
- `.github/workflows/deploy.yml`은 원본 Python의 안전한 수정만 커밋하고, 이미지 생성·배포 작업에는 저장소 읽기 권한만 부여한다.
- 사진 네 장의 다운로드와 JPEG 검증을 모두 통과한 결과만 배포한다.
- 갤러리 생성이나 테스트가 실패하면 배포를 중단해 마지막 성공 이미지를 유지한다.
- 린트 잔여 오류는 경고로 남기되, 실제 이미지 생성·검증·배포 오류를 숨기지 않는다.
- `ICLOUD_ALBUM_TOKEN` 저장소 변수로 기본 공유 앨범을 바꿀 수 있다.
- `workflow_dispatch`로 즉시 실행하며, 선택적 `date` 입력으로 특정 날짜의 사진 선택을 재현한다.
- 예약 실행은 매일 03:00 UTC이고 GitHub 상황에 따라 지연될 수 있다.
- 공개 저장소의 비활동에 따른 예약 중지를 예방하도록 별도 `actions: write` 작업에서 활성 상태를 갱신한다.
- 활성 상태 갱신은 API만 호출하며 더미 커밋을 만들지 않는다.
- 같은 날 재실행은 앨범 내용이 같으면 같은 사진을 선택한다.
- 홈페이지는 `/linklab-gallery/1.jpg`~`4.jpg`를 직접 사용하므로 파일 이름을 변경할 때 함께 수정한다.
- 임시 검증 자료와 운영 지침은 README에 추가하지 않는다.
