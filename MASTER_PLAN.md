# 네이버 블로그 자동화 에이전트 시스템 -- 마스터 플랜

> 초기 사용자를 위한 완전 가이드
> 최종 업데이트: 2026-02-17

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [사전 요구사항](#2-사전-요구사항)
3. [초기 설정 단계별 가이드](#3-초기-설정-단계별-가이드)
4. [설정 파일 커스터마이징](#4-설정-파일-커스터마이징)
5. [기본 사용법](#5-기본-사용법)
6. [고급 사용법](#6-고급-사용법)
7. [트러블슈팅](#7-트러블슈팅)
8. [추천 워크플로우](#8-추천-워크플로우)

---

## 1. 프로젝트 개요

### 1.1 시스템이 무엇을 하는가

**blog-agents**는 한국 미술 전시 정보를 자동으로 수집하고, AI가 전문적인 전시 비평 블로그 글을 작성하여 네이버 블로그에 발행하는 멀티 에이전트 자동화 시스템입니다.

3개의 AI 에이전트가 협업하여 하나의 블로그 포스트를 만들어냅니다:

```
[리서치 에이전트] --> [작가 에이전트] --> [편집장 에이전트]
   전시 정보 수집       블로그 글 작성       품질 검토 & 피드백
   토픽 제안            마크다운 생성         점수 평가 (1~10점)
   리서치 브리핑 작성                        수정 지시 / 승인
```

전체 파이프라인은 다음 순서로 진행됩니다:

1. **리서치**: RSS 피드, 미술관 웹사이트 스크래핑, 뉴스 검색을 통해 최신 전시 정보를 수집
2. **토픽 선택**: 수집된 데이터를 AI가 분석하여 블로그 토픽 3개를 제안
3. **글 작성**: 선택된 토픽에 대해 1,500~3,000자 분량의 전문적 전시 비평 글 작성
4. **편집 검토**: 6개 차원(사실 정확성, 미술 지식, 가독성, SEO, 구성, 비평적 깊이)으로 평가
5. **수정 루프**: 기준 점수 미달 시 피드백을 반영하여 재작성 (최대 설정 횟수만큼 반복)
6. **발행**: 최종 승인된 글을 네이버 블로그에 자동 발행


### 1.2 왜 유용한가

- **시간 절약**: 전시 리서치 + 글 작성에 보통 3~5시간 걸리는 작업을 10~15분으로 단축
- **일관된 품질**: AI 편집장이 6개 차원으로 매번 동일한 기준으로 검토
- **전문성 유지**: 미술 비평 전문가 수준의 프롬프트로 단순 감상평이 아닌 비평적 분석 글 생성
- **자동화 가능**: GitHub Actions 등으로 주 3회 자동 발행 가능
- **무료 운영**: Google Gemini 무료 티어로 운영 가능 (API 비용 0원)


### 1.3 주요 기능

| 기능 | 설명 |
|------|------|
| **자동 리서치** | RSS 피드(아트인사이트, Google News) + 미술관 웹사이트 스크래핑(국립현대미술관, 서울시립미술관, 국립중앙박물관) |
| **4개 카테고리** | 미술관 전시, 갤러리 전시, 아트페어/비엔날레, 특별전/기획전 |
| **자동 로테이션** | 카테고리를 순환하며 다양한 주제의 글을 균형 있게 생성 |
| **품질 관리** | AI 편집장의 점수 기반 승인/수정 시스템 (기본 임계값: 8.0/10) |
| **네이버 발행** | Playwright 브라우저 자동화를 통한 네이버 블로그 직접 발행 |
| **마크다운 -> HTML** | 네이버 SmartEditor ONE 호환 HTML 자동 변환 (테이블 기반 스타일 보존) |
| **이미지 지원** | 마크다운 이미지 마커를 통한 자동 이미지 업로드 |
| **임시저장** | 바로 공개하지 않고 네이버 블로그 임시저장으로 발행 가능 |

---

## 2. 사전 요구사항

### 2.1 필요한 도구/서비스

| 도구 | 버전 | 용도 | 필수 여부 |
|------|------|------|-----------|
| **Python** | 3.9 이상 | 시스템 실행 환경 | 필수 |
| **pip** | 최신 | Python 패키지 관리 | 필수 |
| **Git** | 최신 | 소스코드 관리 | 권장 |
| **네이버 계정** | - | 블로그 발행용 | 발행 시 필수 |
| **네이버 블로그** | - | 발행 대상 블로그 | 발행 시 필수 |

### 2.2 필요한 API 키

| API | 발급처 | 비용 | 용도 |
|-----|--------|------|------|
| **Google Gemini API Key** | [Google AI Studio](https://aistudio.google.com/apikey) | 무료 | AI 에이전트 (리서치, 작성, 편집) |

> Gemini 무료 티어는 모델별로 별도 쿼터가 적용됩니다.
> 기본 설정인 `gemini-2.5-flash` 모델 하나로 모든 에이전트를 운영하면 쿼터 관리가 수월합니다.

### 2.3 시스템 요구사항

- **OS**: macOS, Linux, Windows (macOS에서 테스트됨)
- **메모리**: 최소 4GB RAM (Playwright 브라우저 실행 시)
- **디스크**: 500MB 이상 여유 공간
- **네트워크**: 인터넷 연결 필수 (RSS 피드 수집, API 호출, 웹 스크래핑)

---

## 3. 초기 설정 단계별 가이드

### 3.1 Python 환경 설정

#### Step 1: Python 버전 확인

```bash
python3 --version
# Python 3.9 이상이어야 합니다
```

Python이 설치되지 않았다면:
- **macOS**: `brew install python3`
- **Ubuntu/Debian**: `sudo apt install python3 python3-pip python3-venv`
- **Windows**: [python.org](https://www.python.org/downloads/)에서 다운로드

#### Step 2: 프로젝트 클론 (또는 디렉토리 이동)

```bash
# Git으로 클론하는 경우
git clone <저장소-URL> naver-blog-agents
cd naver-blog-agents

# 이미 있는 경우
cd /path/to/naver-blog-agents
```

#### Step 3: 가상 환경 생성 및 활성화

```bash
# 가상 환경 생성
python3 -m venv .venv

# 활성화
# macOS/Linux:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

> 가상 환경이 활성화되면 터미널 프롬프트 앞에 `(.venv)`가 표시됩니다.


### 3.2 의존성 설치

#### 기본 설치 (글 생성만 사용하는 경우)

```bash
pip install -e .
```

이 명령어로 설치되는 패키지:

| 패키지 | 용도 |
|--------|------|
| `google-genai` | Google Gemini AI API 클라이언트 |
| `pydantic`, `pydantic-settings` | 데이터 모델 & 환경 설정 관리 |
| `pyyaml` | YAML 설정 파일 파싱 |
| `feedparser` | RSS 피드 파싱 |
| `httpx` | HTTP 클라이언트 (스크래핑, API 호출) |
| `beautifulsoup4`, `lxml` | 미술관 웹사이트 HTML 파싱 |
| `rich` | 터미널 UI (컬러 출력, 테이블, 프로그레스 바) |
| `typer` | CLI 인터페이스 |
| `jinja2` | 프롬프트 템플릿 엔진 |
| `python-dotenv` | .env 환경 변수 로드 |
| `googlenewsdecoder` | Google News RSS URL 디코딩 |

#### 네이버 발행까지 사용하는 경우 (권장)

```bash
pip install -e ".[naver]"
playwright install chromium
```

> `playwright install chromium`은 Chromium 브라우저를 다운로드합니다 (약 150MB).
> 네이버 블로그 자동 발행에 필요합니다.

#### 개발 도구 포함 (기여자용)

```bash
pip install -e ".[naver,dev]"
playwright install chromium
```


### 3.3 환경 변수 설정

#### Step 1: .env 파일 생성

```bash
cp .env.example .env
```

#### Step 2: .env 파일 편집

```bash
# 선호하는 에디터로 열기
nano .env
# 또는
code .env
```

`.env` 파일 내용:

```env
# Google Gemini API Key (무료)
# https://aistudio.google.com/apikey 에서 발급
GEMINI_API_KEY=여기에-실제-API-키를-입력하세요

# Naver Blog (Playwright 자동화)
NAVER_BLOG_ID=여기에-네이버-아이디를-입력하세요
```

> **GEMINI_API_KEY**: [Google AI Studio](https://aistudio.google.com/apikey)에서 "Create API Key" 클릭 후 복사
>
> **NAVER_BLOG_ID**: 네이버 블로그 URL이 `blog.naver.com/myid123`이라면 `myid123`이 블로그 ID입니다.
> 네이버 발행을 사용하지 않을 경우 비워둘 수 있습니다.


### 3.4 네이버 블로그 연결

네이버 블로그 발행을 사용하려면 최초 1회 로그인이 필요합니다.

#### Step 1: 네이버 로그인 세션 저장

```bash
blog-agents naver-login
```

이 명령어를 실행하면:
1. Chromium 브라우저가 열리고 네이버 로그인 페이지로 이동합니다
2. **직접 네이버 계정으로 로그인**합니다 (ID/PW 입력 또는 QR 코드)
3. 로그인이 완료되면 세션이 `~/.blog-agents/naver-session/` 에 자동 저장됩니다
4. 이후 발행 시에는 재로그인 없이 저장된 세션을 사용합니다

> 세션은 일정 기간(보통 수일~수주) 후 만료될 수 있습니다.
> 발행 실패 시 `blog-agents naver-login`을 다시 실행하면 됩니다.

#### Step 2: 연결 확인

```bash
blog-agents status
```

정상적으로 설정되었다면 현황 정보가 표시됩니다.

---

## 4. 설정 파일 커스터마이징

### 4.1 config/settings.yaml -- 핵심 설정

이 파일은 시스템 전반의 동작을 제어합니다.

```yaml
# 블로그 에이전트 설정
project:
  name: "전시 가이드"          # 블로그 이름
  language: "ko"              # 언어 (현재 한국어만 지원)
  timezone: "Asia/Seoul"      # 시간대

# 모델 배분 (Gemini 무료 티어 -- 모델별 별도 쿼터)
models:
  research: "gemini-2.5-flash"   # 리서치 에이전트 모델
  writer: "gemini-2.5-flash"     # 작가 에이전트 모델
  editor: "gemini-2.5-flash"     # 편집장 에이전트 모델
  metadata: "gemini-2.5-flash"   # 메타데이터 추출 모델

# 품질 기준
quality:
  approval_threshold: 8.0    # 편집장 승인 점수 (1~10, 기본 8.0)
  max_revision_rounds: 1     # 최대 수정 횟수 (높을수록 품질 up, 시간/쿼터 소비 up)
  min_word_count: 1500       # 최소 글자 수
  max_word_count: 3000       # 최대 글자 수

# 콘텐츠 설정
content:
  posts_per_week: 3          # 주간 발행 횟수 (자동화 시 참고)
  categories:                # 사용할 카테고리 목록
    - museum                 # 미술관 전시
    - gallery                # 갤러리 전시
    - art_fair               # 아트페어/비엔날레
    - special                # 특별전/기획전
  rotation: "round_robin"    # 로테이션 방식 (순환)

# 저장
storage:
  base_path: "./output"                        # 출력 디렉토리
  filename_template: "{date}_{category}_{slug}" # 파일명 패턴
```

**주요 조정 포인트:**

| 설정 | 권장값 | 설명 |
|------|--------|------|
| `approval_threshold` | 7.0~8.5 | 낮출수록 통과하기 쉬움. 처음에는 7.5 정도로 시작 권장 |
| `max_revision_rounds` | 1~3 | 1이면 빠르지만 품질 편차 있음. 2~3이면 안정적이지만 API 쿼터 소비 증가 |
| `models.research` | `gemini-2.5-flash` | 무료 티어 내에서 빠른 모델. 필요 시 `gemini-2.5-pro`로 변경 가능 |


### 4.2 config/sources.yaml -- 데이터 소스 설정

이 파일은 전시 정보를 어디서 가져올지 정의합니다.

```yaml
# RSS 피드 -- 미술 매체
institution_rss:
  아트인사이트:
    all: "https://www.artinsight.co.kr/rss/allArticle.xml"

# 미술관/박물관 웹사이트 스크래핑
exhibition_scrape:
  국립현대미술관:
    url: "https://www.mmca.go.kr/exhibitions/exhibitionList.do"
    list_selector: "ul.list_exhibition li"
    title_selector: ".txt_info .tit"
    date_selector: ".txt_info .date"
  서울시립미술관:
    url: "https://sema.seoul.go.kr/kr/whatson/exhibition/list"
    # ...
  국립중앙박물관:
    url: "https://www.museum.go.kr/site/main/exhi/special/list"
    # ...

# Google News RSS 검색
art_media_rss:
  Google_News_전시:
    all: "https://news.google.com/rss/search?q=미술+전시+when:14d&hl=ko&gl=KR&ceid=KR:ko"
  Google_News_아트페어:
    all: "https://news.google.com/rss/search?q=아트페어+OR+비엔날레+when:14d&hl=ko&gl=KR&ceid=KR:ko"
  Google_News_갤러리:
    all: "https://news.google.com/rss/search?q=갤러리+전시+개인전+when:14d&hl=ko&gl=KR&ceid=KR:ko"

# 카테고리별 소스 매핑
category_source_mapping:
  museum:
    institutions: ["국립현대미술관", "서울시립미술관", "국립중앙박물관"]
    search_keywords: ["미술관 전시", "국립현대미술관", ...]
  gallery:
    institutions: []
    search_keywords: ["갤러리 전시", "개인전", ...]
  art_fair:
    institutions: []
    search_keywords: ["아트페어", "키아프", "프리즈 서울", ...]
  special:
    institutions: ["국립현대미술관", "서울시립미술관", "국립중앙박물관"]
    search_keywords: ["특별전", "기획전", "회고전", ...]
```

#### 새로운 데이터 소스 추가하기

**RSS 피드 추가:**

```yaml
institution_rss:
  아트인사이트:
    all: "https://www.artinsight.co.kr/rss/allArticle.xml"
  # 새로운 매체 추가
  네오룩:
    all: "https://neolook.com/rss"
```

**미술관 스크래핑 추가:**

```yaml
exhibition_scrape:
  # 새로운 미술관 추가
  리움미술관:
    url: "https://www.leeum.org/exhibitions"
    list_selector: ".exhibition-list .item"    # CSS 셀렉터: 전시 목록의 각 항목
    title_selector: ".title"                    # CSS 셀렉터: 전시 제목
    date_selector: ".date"                      # CSS 셀렉터: 전시 기간
```

> 스크래핑 소스를 추가하려면 해당 미술관 웹사이트의 HTML 구조를 확인하고
> 적절한 CSS 셀렉터를 지정해야 합니다. 브라우저 개발자 도구(F12)를 활용하세요.

**키워드 추가:**

```yaml
category_source_mapping:
  museum:
    institutions: ["국립현대미술관", "서울시립미술관", "국립중앙박물관", "리움미술관"]
    search_keywords: ["미술관 전시", "리움미술관", "아모레퍼시픽미술관"]
```


### 4.3 프롬프트 커스터마이징

프롬프트 파일은 `config/prompts/` 디렉토리에 마크다운 형식으로 저장되어 있습니다.

```
config/prompts/
  research_agent.md      # 리서치 에이전트 시스템 프롬프트
  writer_agent.md        # 작가 에이전트 기본 프롬프트
  writer_museum.md       # 미술관 전시 카테고리 스타일 가이드
  writer_gallery.md      # 갤러리 전시 카테고리 스타일 가이드
  writer_artfair.md      # 아트페어/비엔날레 카테고리 스타일 가이드
  writer_special.md      # 특별전/기획전 카테고리 스타일 가이드
  editor_agent.md        # 편집장 에이전트 프롬프트
```

#### 프롬프트 구조 이해

프롬프트는 Jinja2 템플릿 엔진으로 렌더링되므로 변수를 사용할 수 있습니다:

```markdown
<!-- research_agent.md 에서 사용 가능한 변수 -->
{{ category }}   <!-- 현재 카테고리: museum, gallery, art_fair, special -->
{{ today }}      <!-- 오늘 날짜: "2026년 02월 17일" 형식 -->

<!-- writer_agent.md 에서 사용 가능한 변수 -->
{{ revision_instructions }}  <!-- 편집장의 수정 요청 (수정 시에만) -->
{{ line_edits }}             <!-- 편집장의 구체적 수정 제안 목록 -->

<!-- editor_agent.md 에서 사용 가능한 변수 -->
{{ today }}      <!-- 오늘 날짜 -->
```

#### 글 스타일 변경하기

작가 에이전트의 문체를 변경하고 싶다면 `config/prompts/writer_agent.md`를 편집합니다.

**예시: 더 캐주얼한 톤으로 변경**

`writer_agent.md`의 "톤과 문체" 섹션을 수정:

```markdown
### 톤과 문체
- 친구에게 설명하듯 편안한 말투
- ~요/~죠 체를 기본으로 사용
- 미술을 전혀 모르는 사람도 이해할 수 있게
```

**예시: 새로운 카테고리 스타일 추가**

`config/prompts/writer_photography.md` 파일을 만들고, 코드에서 매핑을 추가하면 됩니다.

#### 평가 기준 조정하기

편집장의 평가 가중치를 변경하고 싶다면 `config/prompts/editor_agent.md`를 편집합니다.

현재 가중치:
- 사실 정확성: 25%
- 가독성/문체: 25%
- 구성/논리 흐름: 15%
- 비평적 깊이: 15%
- SEO 최적화: 10%
- 미술 지식: 10%

---

## 5. 기본 사용법

### 5.1 첫 번째 글 생성하기

#### 방법 1: 수동 모드 (토픽을 직접 선택)

```bash
blog-agents generate museum
```

이 명령어를 실행하면:

1. 리서치 에이전트가 미술관 전시 관련 최신 정보를 수집합니다
2. 수집된 정보를 분석하여 토픽 3개를 제안합니다
3. **터미널에서 원하는 토픽 번호를 선택합니다**
4. 선택한 토픽으로 글이 작성됩니다
5. 편집장이 검토하고, 기준에 미달하면 수정을 요청합니다
6. 최종 승인된 글이 `output/published/` 에 저장됩니다

출력 예시:

```
╭──────── blog-agents generate ────────╮
│ 미술 전시 블로그 에이전트             │
│ 카테고리: 미술관 전시                 │
│ 모드: 수동 (토픽 선택)               │
╰──────────────────────────────────────╯

Phase 1: 리서치 - 이슈 수집 및 토픽 제안
  RSS 피드 수집 중...
  전시 목록 확인 중...
  전시 뉴스 검색 중...

토픽을 선택하세요:

  1. 국현 《소멸의 시학》, 사라지는 예술이 던지는 질문
     관점: 매체 실험과 미술관 기획의 방향성
     시의성: 전시 종료 2주 전, 마감 임박
     ...

  2. ...

번호 선택 [1]:
```

#### 방법 2: 자동 모드 (사용자 입력 없이 실행)

```bash
blog-agents generate --auto
```

- 카테고리를 지정하지 않으면 자동 로테이션 (museum -> gallery -> art_fair -> special -> ...)
- `--auto` 플래그로 가장 관심도가 높은 토픽이 자동 선택됩니다
- 완전 무인 실행 가능 (GitHub Actions 등 자동화에 적합)

#### 방법 3: 자동 생성 + 네이버 발행

```bash
blog-agents generate --auto --publish
```

- 글 생성 후 네이버 블로그에 자동으로 공개 발행합니다

```bash
blog-agents generate --auto --draft
```

- 글 생성 후 네이버 블로그에 **임시저장**합니다 (바로 공개하지 않음)
- 직접 확인 후 수동으로 발행하고 싶을 때 사용합니다


### 5.2 토픽 선택하기 (리서치만 실행)

글 작성 전에 어떤 토픽이 제안되는지 먼저 확인하고 싶다면:

```bash
blog-agents research museum      # 미술관 전시 토픽 조사
blog-agents research gallery     # 갤러리 전시 토픽 조사
blog-agents research artfair     # 아트페어 토픽 조사
blog-agents research special     # 특별전 토픽 조사
```

각 토픽에 대해 다음 정보를 확인할 수 있습니다:
- **제목**: 제안된 블로그 포스트 제목
- **관점**: 이 주제를 다루는 독특한 각도
- **시의성**: 지금 이 주제를 다뤄야 하는 이유
- **키워드**: SEO 타겟 키워드
- **관심도**: 예상 독자 관심도 (별 1~5개)


### 5.3 발행하기

#### 이미 생성된 글 발행

```bash
blog-agents publish
```

이 명령어를 실행하면:
1. `output/published/` 에서 발행 가능한 글 목록을 표시합니다
2. 발행할 글을 번호로 선택합니다
3. 네이버 블로그에 발행합니다

#### 특정 파일 지정하여 발행

```bash
blog-agents publish output/published/2026-02-17_museum_국현-소멸의시학_final.md
```

#### 임시저장으로 발행

```bash
blog-agents publish --draft
```


### 5.4 현황 확인

```bash
blog-agents status
```

출력 예시:

```
╭── 블로그 에이전트 현황 ──╮

  최근 발행 글
  날짜          파일명
  2026-02-17    2026-02-17_museum_국현-소멸의시학_final.md

  리서치 브리핑: 3개
  초안: 5개
  리뷰: 4개
  발행: 2개
```

---

## 6. 고급 사용법

### 6.1 자동화 설정

#### cron 으로 로컬 자동화 (macOS/Linux)

```bash
# crontab 편집
crontab -e
```

```cron
# 매주 월/수/금 오전 9시에 자동 생성 + 임시저장
0 9 * * 1,3,5 cd /path/to/naver-blog-agents && .venv/bin/blog-agents generate --auto --draft
```

#### Python 스크립트로 실행

```python
from blog_agents.models.config import AppConfig
from blog_agents.models.research import ContentCategory
from blog_agents.orchestrator import BlogOrchestrator

config = AppConfig()
orchestrator = BlogOrchestrator(config)

# 특정 카테고리로 실행
result = orchestrator.run_full_pipeline(
    ContentCategory.MUSEUM,
    auto_select=True,
)

orchestrator.cleanup()
```


### 6.2 GitHub Actions 연동

프로젝트 루트에 `.github/workflows/blog-publish.yml` 파일을 생성합니다:

```yaml
name: Auto Publish Blog

on:
  schedule:
    # 매주 월/수/금 한국시간 오전 9시 (UTC 0시)
    - cron: '0 0 * * 1,3,5'
  workflow_dispatch:  # 수동 실행 버튼

jobs:
  publish:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .

      - name: Generate blog post
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          blog-agents generate --auto --project-dir .

      - name: Save rotation state
        run: |
          git config user.name "Blog Bot"
          git config user.email "bot@example.com"
          git add config/rotation_state.json output/
          git diff --cached --quiet || git commit -m "Auto: 새 블로그 포스트 생성"
          git push
```

> **GitHub Secrets 설정 필요:**
> Repository Settings -> Secrets and variables -> Actions 에서:
> - `GEMINI_API_KEY`: Gemini API 키
>
> 네이버 자동 발행은 Playwright 브라우저가 필요하므로 GitHub Actions에서는
> 글 생성까지만 자동화하고, 네이버 발행은 로컬에서 `blog-agents publish`로 하는 것을 권장합니다.


### 6.3 커스텀 카테고리 추가

새로운 카테고리(예: "사진전")를 추가하려면 다음 파일들을 수정합니다:

#### Step 1: 모델에 카테고리 추가

`src/blog_agents/models/research.py`:

```python
class ContentCategory(str, Enum):
    MUSEUM = "museum"
    GALLERY = "gallery"
    ART_FAIR = "art_fair"
    SPECIAL = "special"
    PHOTOGRAPHY = "photography"   # 새로 추가

    @property
    def display_name(self) -> str:
        names = {
            "museum": "미술관 전시",
            "gallery": "갤러리 전시",
            "art_fair": "아트페어·비엔날레",
            "special": "특별전·기획전",
            "photography": "사진전",   # 새로 추가
        }
        return names[self.value]
```

#### Step 2: CLI에 매핑 추가

`src/blog_agents/cli.py`의 `CATEGORY_MAP`에 추가:

```python
CATEGORY_MAP = {
    ...
    "photography": ContentCategory.PHOTOGRAPHY,
    "사진전": ContentCategory.PHOTOGRAPHY,
}
```

#### Step 3: 스타일 프롬프트 추가

`config/prompts/writer_photography.md` 파일 생성:

```markdown
## 사진전 카테고리 전문 가이드

### 글의 핵심 가치
사진이라는 매체의 특수성을 고려하여...
```

#### Step 4: 작가 에이전트에 매핑 추가

`src/blog_agents/agents/writer.py`의 `STYLE_PROMPTS`에 추가:

```python
STYLE_PROMPTS = {
    ...
    ContentCategory.PHOTOGRAPHY: "writer_photography.md",
}
```

#### Step 5: sources.yaml에 소스 추가

```yaml
category_source_mapping:
  photography:
    institutions: []
    search_keywords: ["사진전", "포토 전시", "사진 작가"]
```

#### Step 6: settings.yaml에 카테고리 추가

```yaml
content:
  categories:
    - museum
    - gallery
    - art_fair
    - special
    - photography
```

---

## 7. 트러블슈팅

### 7.1 흔한 오류와 해결 방법

#### 오류: "GEMINI_API_KEY가 비어 있습니다" 또는 API 인증 실패

```
google.genai.errors.ClientError: 403 ...
```

**원인**: Gemini API 키가 설정되지 않았거나 잘못됨

**해결**:
1. `.env` 파일에 `GEMINI_API_KEY=...`가 올바르게 입력되었는지 확인
2. [Google AI Studio](https://aistudio.google.com/apikey)에서 키가 유효한지 확인
3. 키를 재발급하고 `.env` 파일 갱신

---

#### 오류: "일일 쿼터 소진"

```
[red]gemini-2.5-flash 일일 쿼터 소진. 다른 모델로 전환하거나 내일 재시도하세요.
```

**원인**: Gemini 무료 티어의 일일 요청 한도 초과

**해결**:
1. 다음 날까지 대기 (무료 쿼터는 매일 초기화)
2. `config/settings.yaml`에서 모델을 다른 것으로 변경하여 별도 쿼터 사용:
   ```yaml
   models:
     research: "gemini-2.0-flash"     # 다른 모델로 변경
     writer: "gemini-2.5-flash"
     editor: "gemini-2.5-flash"
   ```
3. `max_revision_rounds`를 줄여 API 호출 횟수 최소화

---

#### 오류: "Rate limit" 반복 발생

```
[yellow]Rate limit - 30초 대기 후 재시도 (1/2)...
```

**원인**: Gemini 분당 요청 한도 초과

**해결**: 시스템이 자동으로 대기 후 재시도합니다. 별도 조치 불필요.
자주 발생한다면 실행 간격을 늘려주세요.

---

#### 오류: "토픽을 찾지 못했습니다"

**원인**: RSS 피드나 웹 스크래핑에서 데이터 수집에 실패

**해결**:
1. 인터넷 연결 상태 확인
2. `config/sources.yaml`의 RSS URL이 유효한지 확인
3. 미술관 사이트의 HTML 구조가 변경되었을 수 있음 -> CSS 셀렉터 업데이트 필요

---

#### 오류: 네이버 발행 실패 - "네이버 발행 의존성 미설치"

```
pip install blog-agents[naver] && playwright install chromium
```

**해결**: 위 명령어 실행 후 재시도

---

#### 오류: 네이버 발행 실패 - "로그인 시간 초과"

**원인**: 네이버 로그인 세션 만료

**해결**:
```bash
blog-agents naver-login
```
브라우저에서 다시 로그인하면 세션이 갱신됩니다.

---

#### 오류: "JSON 파싱 실패"

**원인**: AI 모델이 유효하지 않은 JSON을 반환

**해결**: 시스템이 자동으로 재시도 및 JSON 복구를 시도합니다.
반복 발생 시 `config/settings.yaml`에서 다른 모델로 변경해보세요.

---

### 7.2 로그 확인 방법

이 시스템은 Rich 라이브러리를 사용하여 터미널에 실시간으로 상세 로그를 출력합니다.

#### 로그 색상 의미

| 색상 | 의미 |
|------|------|
| **파란색** | Phase 시작, 리서치 에이전트 활동 |
| **초록색** | 작가 에이전트 활동, 성공 메시지 |
| **보라색** | 편집장 에이전트 활동 |
| **노란색** | 경고, 수정 요청, 비치명적 오류 |
| **빨간색** | 오류, 실패 |
| **회색(dim)** | 진행 상황 상세 (API 호출, 파일 저장 등) |

#### 출력 파일 확인

```
output/
  research/     # 리서치 브리핑 JSON 파일
    2026-02-17_museum_국현-소멸의시학_brief.json
  drafts/       # 초안 마크다운 파일 (버전별)
    2026-02-17_museum_국현-소멸의시학_v1.md
    2026-02-17_museum_국현-소멸의시학_v2.md
  reviews/      # 편집장 검토 결과 JSON 파일
    2026-02-17_museum_국현-소멸의시학_review_v1.json
  published/    # 최종 발행 마크다운 파일
    2026-02-17_museum_국현-소멸의시학_final.md
```

**리서치 브리핑 확인** (AI가 수집한 정보):
```bash
cat output/research/2026-02-17_museum_*_brief.json | python3 -m json.tool
```

**편집 검토 결과 확인** (점수, 피드백):
```bash
cat output/reviews/2026-02-17_museum_*_review_v1.json | python3 -m json.tool
```

---

## 8. 추천 워크플로우

### 8.1 처음 시작할 때

아래 순서대로 진행하면 시스템을 안전하게 익힐 수 있습니다.

#### Day 1: 환경 설정 + 첫 테스트

```bash
# 1. 환경 설정 (3.1~3.3절 참고)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
# .env 파일에 GEMINI_API_KEY 입력

# 2. 리서치만 먼저 테스트 (글 생성 없이 토픽만 확인)
blog-agents research museum

# 3. 결과를 확인하고, 토픽 품질이 만족스러운지 평가
```

#### Day 2: 글 생성 테스트

```bash
# 4. 수동 모드로 첫 글 생성 (토픽을 직접 선택)
blog-agents generate museum

# 5. 생성된 글 확인
cat output/published/*.md

# 6. 검토 결과 확인
cat output/reviews/*.json | python3 -m json.tool
```

#### Day 3: 네이버 연동

```bash
# 7. 네이버 의존성 설치
pip install -e ".[naver]"
playwright install chromium

# 8. 네이버 로그인
blog-agents naver-login

# 9. 임시저장으로 발행 테스트
blog-agents publish --draft

# 10. 네이버 블로그에서 임시저장된 글 확인 후 수동 발행
```

#### Day 4~: 자동화 전환

```bash
# 11. 자동 모드 테스트
blog-agents generate --auto --draft

# 12. 만족스러우면 완전 자동 발행
blog-agents generate --auto --publish
```


### 8.2 주간 운영 루틴

**주 3회 발행** 기준 추천 루틴:

| 요일 | 작업 | 명령어 |
|------|------|--------|
| **월요일** | 자동 생성 + 임시저장 | `blog-agents generate --auto --draft` |
| **화요일** | 월요일 글 검토 후 수동 발행 | 네이버 블로그 관리에서 임시저장 글 확인 -> 발행 |
| **수요일** | 자동 생성 + 임시저장 | `blog-agents generate --auto --draft` |
| **목요일** | 수요일 글 검토 후 수동 발행 | 네이버 블로그 관리에서 확인 -> 발행 |
| **금요일** | 자동 생성 + 임시저장 | `blog-agents generate --auto --draft` |
| **토요일** | 금요일 글 검토 + 현황 확인 | `blog-agents status` |
| **일요일** | 휴식 / 프롬프트 개선 | 필요 시 프롬프트 수정 |

> **팁**: 처음 2~3주는 임시저장(`--draft`) 모드로 운영하면서 글 품질을 확인한 후,
> 만족스러운 수준이 되면 즉시 발행(`--publish`) 모드로 전환하세요.


### 8.3 품질 관리 방법

#### 1. 편집 검토 결과 주기적 모니터링

```bash
# 최근 검토 결과 확인
ls -la output/reviews/

# 특정 리뷰 상세 확인
cat output/reviews/2026-02-17_museum_*_review_v1.json | python3 -m json.tool
```

주요 확인 포인트:
- `overall_score`: 종합 점수 (8.0 이상이 이상적)
- `dimensions`: 6개 차원별 점수와 피드백
- `strengths`: 잘된 점
- `revision_instructions`: 수정 필요 사항

#### 2. 품질 기준 튜닝

초기에는 낮은 기준으로 시작하고 점차 올리는 것을 권장합니다:

```yaml
# 초기 (첫 2주)
quality:
  approval_threshold: 7.0
  max_revision_rounds: 1

# 안정화 후 (3주차~)
quality:
  approval_threshold: 7.5
  max_revision_rounds: 2

# 고품질 운영 (익숙해진 후)
quality:
  approval_threshold: 8.0
  max_revision_rounds: 2
```

#### 3. 프롬프트 개선 사이클

1. **생성된 글 10개 정도 축적**
2. **공통적으로 나타나는 문제점 파악** (예: "도입부가 너무 딱딱하다", "미술 용어 풀이가 부족하다")
3. **해당 프롬프트 파일 수정** (예: `config/prompts/writer_agent.md`)
4. **다시 글 생성하여 개선 확인**
5. **반복**

#### 4. 카테고리 로테이션 상태 확인

```bash
cat config/rotation_state.json
```

```json
{
  "last_category": "museum",
  "last_generated": "2026-02-17 17:29"
}
```

다음 자동 생성 시에는 `gallery` 카테고리가 선택됩니다.
(순서: museum -> gallery -> art_fair -> special -> museum -> ...)

---

## 부록: 프로젝트 구조 맵

```
naver-blog-agents/
│
├── .env                          # 환경 변수 (API 키, 블로그 ID)
├── .env.example                  # 환경 변수 예시
├── .gitignore                    # Git 무시 파일
├── pyproject.toml                # Python 프로젝트 설정 & 의존성
│
├── config/
│   ├── settings.yaml             # 핵심 설정 (모델, 품질 기준, 콘텐츠)
│   ├── sources.yaml              # 데이터 소스 (RSS, 스크래핑, 검색)
│   ├── rotation_state.json       # 카테고리 로테이션 상태
│   ├── naver-blog-skin.css       # 네이버 블로그 스킨 CSS
│   ├── naver-design-preview.html # 디자인 미리보기
│   └── prompts/                  # AI 에이전트 프롬프트 (Jinja2 템플릿)
│       ├── research_agent.md     #   리서치 에이전트 (정보 수집)
│       ├── writer_agent.md       #   작가 에이전트 (글 작성 기본)
│       ├── writer_museum.md      #   미술관 전시 스타일
│       ├── writer_gallery.md     #   갤러리 전시 스타일
│       ├── writer_artfair.md     #   아트페어 스타일
│       ├── writer_special.md     #   특별전 스타일
│       └── editor_agent.md       #   편집장 에이전트 (품질 검토)
│
├── src/blog_agents/
│   ├── __init__.py               # 패키지 초기화
│   ├── __main__.py               # python -m blog_agents 진입점
│   ├── cli.py                    # CLI 명령어 (typer)
│   ├── orchestrator.py           # 파이프라인 오케스트레이터
│   ├── agents/
│   │   ├── base.py               # 에이전트 기본 클래스 (Gemini API)
│   │   ├── research.py           # 리서치 에이전트
│   │   ├── writer.py             # 작가 에이전트
│   │   └── editor.py             # 편집장 에이전트
│   ├── tools/
│   │   ├── rss_reader.py         # RSS 피드 수집기
│   │   ├── web_scraper.py        # 미술관 웹사이트 스크래퍼
│   │   └── search.py             # 뉴스 검색 (Google News RSS)
│   ├── models/
│   │   ├── config.py             # 설정 모델 (AppConfig)
│   │   ├── research.py           # 리서치 데이터 모델
│   │   ├── content.py            # 콘텐츠 데이터 모델 (Draft, BlogPost)
│   │   └── review.py             # 편집 검토 모델 (EditReview)
│   ├── publisher/
│   │   ├── naver.py              # 네이버 블로그 발행 (Playwright)
│   │   └── markdown_to_html.py   # 마크다운 -> HTML 변환
│   └── utils/
│       └── storage.py            # 파일 저장/로드 관리
│
├── scripts/
│   └── apply_skin_css.py         # 네이버 블로그 스킨 탐색 스크립트
│
├── output/                       # 생성된 콘텐츠 저장소
│   ├── research/                 #   리서치 브리핑 (JSON)
│   ├── drafts/                   #   초안 (마크다운, 버전별)
│   ├── reviews/                  #   편집 검토 결과 (JSON)
│   └── published/                #   최종 발행 글 (마크다운)
│
└── tests/                        # 테스트
```

---

## 부록: CLI 명령어 요약

| 명령어 | 설명 |
|--------|------|
| `blog-agents generate` | 전체 파이프라인 실행 (카테고리 자동 로테이션) |
| `blog-agents generate museum` | 미술관 전시 카테고리로 글 생성 |
| `blog-agents generate gallery` | 갤러리 전시 카테고리로 글 생성 |
| `blog-agents generate artfair` | 아트페어/비엔날레 카테고리로 글 생성 |
| `blog-agents generate special` | 특별전/기획전 카테고리로 글 생성 |
| `blog-agents generate --auto` | 자동 모드 (토픽 자동 선택) |
| `blog-agents generate --auto --publish` | 자동 생성 + 네이버 즉시 발행 |
| `blog-agents generate --auto --draft` | 자동 생성 + 네이버 임시저장 |
| `blog-agents research <category>` | 리서치만 실행 (토픽 확인) |
| `blog-agents publish` | 생성된 글을 네이버에 발행 |
| `blog-agents publish --draft` | 임시저장으로 발행 |
| `blog-agents publish <파일경로>` | 특정 파일 발행 |
| `blog-agents naver-login` | 네이버 로그인 세션 저장 (최초 1회) |
| `blog-agents status` | 생성 현황 확인 |

---

## 부록: FAQ

**Q: Gemini API 무료 쿼터는 얼마나 되나요?**
A: 모델별로 별도 쿼터가 적용됩니다. `gemini-2.5-flash` 기준 무료 티어에서 일일 수십~수백 회 호출이 가능합니다. 블로그 글 1개 생성에 약 4~8회의 API 호출이 필요하므로, 하루 여러 개의 글을 생성할 수 있습니다.

**Q: 네이버 블로그 API를 사용하지 않는 이유는?**
A: 네이버 블로그 API는 글 작성 기능을 제공하지 않습니다. 따라서 Playwright 브라우저 자동화를 통해 SmartEditor ONE에 직접 글을 입력하는 방식을 사용합니다.

**Q: 글의 스타일이 마음에 들지 않으면 어떻게 하나요?**
A: `config/prompts/writer_agent.md` 파일을 편집하여 문체, 톤, 구조를 변경할 수 있습니다. 카테고리별 스타일은 `writer_museum.md`, `writer_gallery.md` 등에서 조정합니다.

**Q: 미술 전시가 아닌 다른 주제(예: 맛집, 여행)로 변경할 수 있나요?**
A: 가능합니다. `config/prompts/` 의 프롬프트 파일들과 `config/sources.yaml`의 데이터 소스를 변경하면 됩니다. 다만, 현재 코드는 미술 전시에 최적화되어 있으므로 일부 코드 수정이 필요할 수 있습니다.

**Q: 생성된 글의 저작권은?**
A: AI가 생성한 콘텐츠의 저작권은 법적으로 아직 명확하게 정립되지 않은 영역입니다. 생성된 글을 발행 전에 검토하고, 필요 시 수정하여 사용하는 것을 권장합니다.

**Q: 네이버 로그인 정보가 안전한가요?**
A: 로그인 세션은 로컬 머신의 `~/.blog-agents/naver-session/` 디렉토리에 저장됩니다. ID/PW를 코드에 저장하지 않으며, Playwright persistent context 방식으로 브라우저 쿠키만 보관합니다. `.gitignore`에 이미 포함되어 있어 Git에 업로드되지 않습니다.
