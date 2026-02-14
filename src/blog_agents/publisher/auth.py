"""Google OAuth 2.0 인증 관리."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console

console = Console()

# Blogger API에 필요한 스코프
SCOPES = ["https://www.googleapis.com/auth/blogger"]
TOKEN_FILE = "token.json"


def get_credentials(credentials_path: str | Path):
    """OAuth 2.0 인증 정보를 가져온다. 최초 실행 시 브라우저 인증 필요."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials_path = Path(credentials_path)
    token_path = credentials_path.parent / TOKEN_FILE

    creds = None

    # 기존 토큰이 있으면 로드
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # 토큰이 없거나 만료된 경우
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            console.print("  [dim]토큰 갱신 중...[/]")
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                console.print(
                    f"[red]credentials.json을 찾을 수 없습니다: {credentials_path}[/]\n"
                    f"Google Cloud Console에서 OAuth 클라이언트 ID를 생성하고\n"
                    f"credentials.json을 다운로드하여 config/google/ 에 넣어주세요."
                )
                raise FileNotFoundError(f"credentials.json not found: {credentials_path}")

            console.print(
                "[bold yellow]브라우저에서 Google 계정 인증이 필요합니다...[/]"
            )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
            console.print("[green]인증 성공![/]")

        # 토큰 저장 (다음 실행 시 재사용)
        token_path.write_text(creds.to_json())
        console.print(f"  [dim]토큰 저장: {token_path}[/]")

    return creds


def get_blogger_service(credentials_path: str | Path):
    """Blogger API 서비스 객체를 반환."""
    from googleapiclient.discovery import build

    creds = get_credentials(credentials_path)
    service = build("blogger", "v3", credentials=creds)
    return service
