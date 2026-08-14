# 뉴스한입 📰

미국/영어권 뉴스(NYT, BBC, NPR, Guardian, CNBC RSS)를 매일 자동으로 가져와서,
**쉬운 영어 요약**과 **한국어 설명**을 나란히 보여주는 뉴스레터 스타일 웹페이지예요.
'뉴닉'처럼 편하게 읽으면서 동시에 영어 공부도 할 수 있게 만들었어요.

## 어떻게 동작하나요

1. `feeds.py`에 등록된 RSS 피드에서 매일 최신 기사(제목 + 짧은 요약)를 가져와요.
2. 각 기사를 Claude API에 보내서:
   - 쉬운 영어 요약 (3~5문장, 쉬운 단어만 사용)
   - 친근한 한국어 설명 (뉴닉 스타일)
   - 핵심 단어 3~5개 + 뜻 + 예문
   을 만들어요.
3. DB에 저장하고, 웹페이지에서 카드 형태로 보여줘요.
4. 앱 안에 내장된 스케줄러가 매일 정해진 시각(기본 KST 오전 7시)에 자동으로 1~3번을 실행해요.
5. 만약 서버가 잠들어 있다가 방문자가 생기면, 오늘자 다이제스트가 없을 경우 그 자리에서 자동으로 생성을 시작해요.

## 로컬에서 먼저 테스트하기

```bash
cd news-digest
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

copy .env.example .env
# .env 파일을 열어서 ANTHROPIC_API_KEY=발급받은키 를 채워넣기
# (DATABASE_URL은 로컬에서는 비워두면 SQLite를 자동으로 씁니다)

python app.py
```

브라우저에서 http://localhost:5000 접속.
API 키를 넣지 않고 실행하면 "API 키가 설정되지 않았어요" 안내만 뜨고, 페이지 자체는 정상적으로 동작해요.

수동으로 한 번 수집+요약을 돌려보고 싶다면:

```bash
python fetch_and_summarize.py
```

## Anthropic API 키 발급받기

1. https://console.anthropic.com 접속 후 가입/로그인
2. 왼쪽 메뉴 API Keys → Create Key
3. 발급된 키를 `.env`의 `ANTHROPIC_API_KEY`에 붙여넣기
4. Billing 메뉴에서 소액 크레딧 충전 (기사 1개 요약당 비용은 매우 저렴해요, 하루 15~20개 기준 월 1~2달러 수준)

## 외부에서 접속 가능하게 배포하기 (Render, 무료 티어)

### 1) 데이터 저장용 Postgres 준비 (무료)

Render 무료 웹 서비스는 재배포 시 디스크가 초기화될 수 있어서, SQLite 대신 외부 Postgres를 쓰는 걸 추천해요.

- [Supabase](https://supabase.com) 또는 [Neon](https://neon.tech)에서 무료 프로젝트 생성
- 연결 문자열(Connection string, `postgresql://...` 형태) 복사해두기

### 2) GitHub에 이 폴더 올리기

```bash
git init
git add .
git commit -m "뉴스한입 초기 버전"
# GitHub에 새 저장소 만든 뒤
git remote add origin <저장소 URL>
git push -u origin main
```

### 3) Render에서 배포

1. https://render.com 가입 후 New → Blueprint 선택
2. 방금 올린 GitHub 저장소 연결 (이 폴더의 `render.yaml`을 자동으로 인식해요)
3. 배포 중 물어보는 환경변수에 입력:
   - `ANTHROPIC_API_KEY`: 위에서 발급받은 키
   - `DATABASE_URL`: Supabase/Neon에서 복사한 연결 문자열
4. Deploy 클릭 → 몇 분 후 `https://news-digest-xxxx.onrender.com` 같은 주소가 생성돼요

### 4) 확인

배포된 주소로 접속하면, 그날 다이제스트가 없을 경우 자동으로 생성이 시작돼요 (1~2분 소요).
이후로는 매일 오전 7시(KST)에 자동으로 새 기사가 쌓여요.

## 커스터마이징

- **뉴스 소스 추가/변경**: `feeds.py`의 `FEEDS` 리스트 수정
- **하루에 가져오는 기사 수**: `feeds.py`의 `MAX_PER_FEED`
- **요약 자동 실행 시각**: `.env`의 `DIGEST_HOUR`, `DIGEST_MINUTE` (Render라면 환경변수로 설정)
- **디자인**: `static/style.css`
- **요약 톤/난이도**: `summarizer.py`의 `TOOL_SCHEMA` description 문구 수정

## 참고

- RSS 피드가 제공하는 제목 + 짧은 요약(스니펫)만 사용하고, 유료화된 기사 본문을 긁어오지는 않아요.
- 스케줄러는 앱 프로세스 안에서 돌아가므로, Render에서 여러 워커로 배포하면 스케줄이 중복 실행될 수 있어요.
  `render.yaml`에 이미 `--workers 1`로 설정해뒀으니 그대로 두면 안전해요.
