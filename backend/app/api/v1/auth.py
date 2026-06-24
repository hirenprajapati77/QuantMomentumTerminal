import time
import os
import urllib.parse
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse
from backend.app.config.settings import settings
from backend.scripts.login_fyers import generate_fyers_login_url, exchange_code_for_token
from backend.app.core.crypto import encrypt_str

router = APIRouter()

@router.get("/login-url")
def get_login_url():
    """
    Get the Fyers authorization URL.
    """
    app_id = settings.FYERS_APP_ID
    redirect_uri = settings.FYERS_REDIRECT_URI
    if not app_id or not redirect_uri:
        raise HTTPException(status_code=500, detail="Fyers credentials (app_id or redirect_uri) are not configured in settings.")
    
    url = generate_fyers_login_url(app_id, redirect_uri)
    return {"login_url": url}

@router.get("/callback")
def oauth_callback(
    auth_code: str = Query(None, alias="auth_code"),
    code: str = Query(None, alias="code"),
    state: str = Query(None)
):
    """
    Callback endpoint that Fyers redirects to. Exchanges auth code for an access token.
    Supports both 'auth_code' (Fyers standard) and 'code' query parameters.
    """
    effective_code = auth_code or code
    if not effective_code:
        raise HTTPException(status_code=400, detail="Missing authorization code (parameter 'auth_code' or 'code').")
    
    app_id = settings.FYERS_APP_ID
    secret_id = settings.FYERS_SECRET_ID
    
    if not app_id or not secret_id:
        raise HTTPException(status_code=500, detail="Fyers credentials (app_id or secret_id) are not configured in settings.")
    
    try:
        access_token = exchange_code_for_token(app_id, secret_id, effective_code)
        
        # Save token to file
        token_path = settings.token_path
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(encrypt_str(access_token))
        
        # Return a nice premium styled HTML success page
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <style>
                body {
                    background-color: #0f172a;
                    color: #f8fafc;
                    font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }
                .card {
                    background: rgba(30, 41, 59, 0.7);
                    backdrop-filter: blur(16px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 24px;
                    padding: 48px;
                    text-align: center;
                    max-width: 480px;
                    box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.5), 0 8px 10px -6px rgb(0 0 0 / 0.5);
                }
                h1 {
                    color: #38bdf8;
                    margin-bottom: 16px;
                    font-size: 28px;
                }
                p {
                    color: #94a3b8;
                    font-size: 16px;
                    line-height: 1.6;
                }
                .checkmark {
                    font-size: 64px;
                    color: #10b981;
                    margin-bottom: 24px;
                }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="checkmark">✓</div>
                <h1>Fyers Login Successful</h1>
                <p>Your access token has been generated and saved securely. You can now close this tab and return to the scanner dashboard.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content, status_code=200)
    except Exception as e:
        # Styled error page
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Failed</title>
            <style>
                body {{
                    background-color: #0f172a;
                    color: #f8fafc;
                    font-family: 'Outfit', 'Inter', -apple-system, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }}
                .card {{
                    background: rgba(30, 41, 59, 0.7);
                    backdrop-filter: blur(16px);
                    border: 1px solid rgba(239, 68, 68, 0.2);
                    border-radius: 24px;
                    padding: 48px;
                    text-align: center;
                    max-width: 480px;
                    box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.5), 0 8px 10px -6px rgb(0 0 0 / 0.5);
                }}
                h1 {{
                    color: #ef4444;
                    margin-bottom: 16px;
                    font-size: 28px;
                }}
                p {{
                    color: #94a3b8;
                    font-size: 16px;
                    line-height: 1.6;
                }}
                .error-icon {{
                    font-size: 64px;
                    color: #ef4444;
                    margin-bottom: 24px;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="error-icon">✗</div>
                <h1>Authentication Failed</h1>
                <p>Authentication failed. Please try again or contact your administrator.</p>
            </div>
        </body>
        </html>
        """
        logger.error(f"Fyers token exchange failed: {e}", exc_info=True)
        return HTMLResponse(content=error_html, status_code=400)

@router.get("/status")
def get_auth_status():
    """
    Check if a valid token exists and has not expired.
    Fyers tokens expire after 24 hours.
    """
    token_path = settings.token_path
    if not token_path.exists():
        return {
            "authenticated": False,
            "message": "Token file not found."
        }
    
    # Check age of token file
    mtime = os.path.getmtime(token_path)
    age_seconds = time.time() - mtime
    age_hours = age_seconds / 3600.0
    
    # 24 hours token expiration
    if age_hours >= 24.0:
        return {
            "authenticated": False,
            "message": f"Token expired (age: {age_hours:.1f} hours)."
        }
    
    return {
        "authenticated": True,
        "age_hours": round(age_hours, 2),
        "expires_in_hours": round(24.0 - age_hours, 2)
    }
