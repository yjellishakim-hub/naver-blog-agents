# GitHub Actions 자동화 설정 가이드

## 개요

월/수/금 오전 10시에 자동으로 블로그 포스트를 생성하고 네이버 블로그에 임시저장하는 워크플로우입니다.

## 1단계: GitHub에 저장소 푸시

```bash
cd "/Users/ellisha/Desktop/visual projects/naver blog-agents"

# GitHub에 새 저장소 생성 후
git init
git add .
git commit -m "Initial commit: el_filmography blog automation"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/naver-blog-agents.git
git push -u origin main
```

## 2단계: GitHub Secrets 설정

GitHub 저장소 페이지에서:

1. **Settings** 탭 클릭
2. 왼쪽 메뉴에서 **Secrets and variables** → **Actions** 클릭
3. **New repository secret** 버튼 클릭

### 추가할 Secrets:

#### `GEMINI_API_KEY`
- Name: `GEMINI_API_KEY`
- Secret: `AIzaSyD4PMtOB9Y-qd3VnBFQeEvy4IRTUQdq5eo`
- 클릭: **Add secret**

#### `NAVER_BLOG_ID`
- Name: `NAVER_BLOG_ID`
- Secret: `el_filmography`
- 클릭: **Add secret**

## 3단계: Naver 세션 저장 (중요!)

GitHub Actions에서 네이버 로그인 세션을 사용하려면 로컬에서 저장한 세션을 Secret으로 추가해야 합니다.

### 방법 1: 로컬 세션 파일을 Base64로 인코딩

```bash
# 네이버 로그인 (로컬에서 한 번 실행)
blog-agents naver-login

# 세션 파일 확인
ls -la ~/.cache/blog_agents_naver/

# 세션 파일을 Base64로 인코딩
cd ~/.cache/blog_agents_naver/
tar -czf - *.json | base64 > ~/Desktop/naver_session.txt
```

그 다음 GitHub Secret 추가:
- Name: `NAVER_SESSION`
- Secret: `~/Desktop/naver_session.txt` 파일 내용 전체 복사

### 방법 2: GitHub Actions에서 처음 실행 시 수동 로그인 (비추천)

워크플로우에서 `NAVER_PASSWORD` Secret을 추가하고 자동 로그인 스크립트 사용 (보안상 비추천)

## 4단계: 워크플로우 활성화 확인

1. GitHub 저장소 → **Actions** 탭
2. "I understand my workflows, go ahead and enable them" 클릭
3. 왼쪽에서 **Auto Blog Generation** 워크플로우 확인

## 5단계: 수동 테스트 실행

자동 스케줄 전에 수동으로 테스트:

1. **Actions** 탭
2. **Auto Blog Generation** 클릭
3. **Run workflow** 버튼 클릭
4. Category 입력 (선택사항):
   - 비워두면 자동 로테이션
   - `seoul`, `gwangju`, `film`, `weekly` 중 선택
5. **Run workflow** 클릭

## 스케줄

- **월요일** 오전 10시
- **수요일** 오전 10시
- **금요일** 오전 10시

자동 로테이션 순서:
1. 서울 전시
2. 광주 문화
3. 영화 리뷰
4. 주간 추천

## 생성된 파일 확인

워크플로우 실행 후:

1. **Actions** 탭 → 실행된 워크플로우 클릭
2. **Artifacts** 섹션에서 `blog-post-XXX` 다운로드
3. 또는 네이버 블로그 관리자 → **임시저장** 확인

## 문제 해결

### 워크플로우 실패 시

1. **Actions** 탭에서 실패한 실행 클릭
2. 각 스텝의 로그 확인
3. 주요 확인 사항:
   - Secrets 설정 확인 (`GEMINI_API_KEY`, `NAVER_BLOG_ID`)
   - 네이버 세션 만료 여부
   - API 할당량 초과 여부

### 네이버 로그인 실패

로컬에서 세션 재생성:

```bash
blog-agents naver-login
# 위의 "방법 1"대로 세션을 다시 GitHub Secret으로 업로드
```

### 스케줄 시간 변경

`.github/workflows/auto-blog.yml` 파일 수정:

```yaml
schedule:
  - cron: '0 1 * * 1,3,5'  # UTC 01:00 = KST 10:00
  # 예: UTC 22:00 = KST 07:00 (아침 7시)
  # - cron: '0 22 * * 0,2,4'
```

## 로컬 실행

GitHub Actions 없이 로컬에서 실행:

```bash
# 자동 로테이션
blog-agents generate --auto --publish --draft

# 특정 카테고리
blog-agents generate seoul --auto --publish --draft
```

## 참고

- 워크플로우는 `main` 브랜치에 푸시될 때만 활성화됩니다
- 생성된 글은 **임시저장**으로 발행되므로 수동으로 확인 후 공개하세요
- `rotation_state.json`은 자동으로 커밋되어 다음 실행 시 로테이션을 이어갑니다
