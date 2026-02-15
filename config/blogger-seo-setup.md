# Blogger SEO 최적화 설정 가이드

블로그 주소: https://econlaw-lab.blogspot.com/

## 1. Blogger 기본 SEO 설정 (필수)

### 1-1. 검색 설명 활성화
1. Blogger 대시보드 → **설정** → **검색 환경설정**
2. **메타 태그** → "검색 설명 사용"을 **예**로 설정
3. 블로그 설명 입력:
   ```
   한국 경제·법률 전문 분석 블로그. 거시경제, 부동산 세법, 기업법, 글로벌 뉴스를 쉽고 깊이있게 분석합니다.
   ```
4. **저장**

### 1-2. 커스텀 robots.txt
1. 설정 → 검색 환경설정 → **맞춤 robots.txt**
2. 아래 내용 입력:
   ```
   User-agent: *
   Allow: /
   Sitemap: https://econlaw-lab.blogspot.com/sitemap.xml
   ```

### 1-3. 커스텀 robots 헤더 태그
1. 설정 → 검색 환경설정 → **맞춤 robots 헤더 태그**
2. 홈페이지: `all`
3. 보관 및 검색 페이지: `noindex`
4. 게시물 및 페이지: `all`

## 2. Google Search Console 등록 (필수)

### 2-1. Search Console 연결
1. https://search.google.com/search-console 접속
2. **속성 추가** → URL 접두어 → `https://econlaw-lab.blogspot.com/`
3. **HTML 태그** 방식으로 소유권 확인
   - 제공된 meta 태그를 복사
   - Blogger → 테마 → **HTML 편집** → `<head>` 바로 아래에 붙여넣기
4. 소유권 확인 완료

### 2-2. 사이트맵 제출
1. Search Console → **사이트맵** 메뉴
2. 사이트맵 URL 입력: `sitemap.xml`
3. **제출** 클릭
4. Blogger는 자동으로 sitemap.xml을 생성합니다

### 2-3. 색인 생성 요청
- 새 글 발행 후 Search Console → **URL 검사** → 글 URL 입력 → **색인 생성 요청**
- 초기에는 수동으로 요청하면 더 빠르게 색인됩니다

## 3. Blogger 테마 SEO 최적화

### 3-1. Open Graph 태그 추가
Blogger → 테마 → **HTML 편집** → `<head>` 섹션에 아래 추가:

```html
<!-- Open Graph / 소셜 미디어 미리보기 -->
<meta property='og:type' content='website'/>
<meta property='og:title' expr:content='data:blog.pageTitle'/>
<meta property='og:description' expr:content='data:blog.metaDescription'/>
<meta property='og:url' expr:content='data:blog.canonicalUrl'/>
<meta property='og:site_name' content='이코노로: 법과 숫자, 그 사이 이야기'/>
<meta property='og:locale' content='ko_KR'/>

<!-- Twitter Card -->
<meta name='twitter:card' content='summary'/>
<meta name='twitter:title' expr:content='data:blog.pageTitle'/>
<meta name='twitter:description' expr:content='data:blog.metaDescription'/>
```

### 3-2. 언어 및 지역 설정
`<html>` 태그에 lang 속성 확인:
```html
<html lang='ko'>
```

## 4. 글 발행 시 개별 SEO 체크리스트

아래는 시스템이 자동으로 처리하는 항목입니다:
- [x] Schema.org JSON-LD 구조화 데이터 (Article 스키마)
- [x] 키워드 기반 라벨 태깅
- [x] 본문 기반 meta description 생성
- [x] SEO 최적화 제목 (키워드 앞배치, 25자 이내)
- [x] H2 소제목에 보조 키워드 분산
- [x] 모바일 반응형 인라인 CSS

## 5. 추가 성장 전략

### 네이버 웹마스터 도구
1. https://searchadvisor.naver.com/ 접속
2. 사이트 등록: `https://econlaw-lab.blogspot.com/`
3. HTML 태그로 소유권 확인
4. 사이트맵 제출: `https://econlaw-lab.blogspot.com/sitemap.xml`
5. RSS 제출: `https://econlaw-lab.blogspot.com/feeds/posts/default?alt=rss`

### 다음 웹마스터 도구
1. https://webmaster.daum.net/ 접속
2. 사이트 등록 및 인증

### 핀 수집 요청
- 네이버 서치어드바이저에서 **웹페이지 수집** 요청
- 구글은 새 글 발행 후 Search Console에서 **URL 검사** → **색인 생성 요청**
