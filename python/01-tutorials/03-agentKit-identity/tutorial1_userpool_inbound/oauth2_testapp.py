from flask import Flask
from authlib.integrations.flask_client import OAuth
import jwt as pyjwt
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# Replace these values with your CIAM app configuration
issuer = os.environ.get("OAUTH2_ISSUER_URI")
client_id = os.environ.get("OAUTH2_CLIENT_ID")
client_secret = os.environ.get("OAUTH2_CLIENT_SECRET")
redirect_uri = "http://127.0.0.1:8082/callback"
scopes = "openid profile email"

oauth = OAuth(app)
oauth.register(
    name="ciam",
    client_id=client_id,
    client_secret=client_secret,
    server_metadata_url=f"{issuer}/.well-known/openid-configuration",
    client_kwargs={"scope": scopes},
    redirect_uri=redirect_uri,
)


@app.get("/")
def index():
    return "<html><body><h1>Python OAuth2 Login Sample</h1><p><a href='/login'>Sign in</a></p></body></html>"


@app.get("/login")
def login():
    return oauth.ciam.authorize_redirect(redirect_uri=redirect_uri, state="state")


@app.get("/callback")
def callback():
    token = oauth.ciam.authorize_access_token()
    access = token.get("access_token")
    claims = pyjwt.decode(access, options={"verify_signature": False})
    username = claims.get("preferred_username", "")
    email = claims.get("email", "")
    items = "".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in claims.items()])
    return f"""
    <html>
      <body>
        <h1>User Info</h1>
        <p><strong>preferred_username:</strong> {username}</p>
        <p><strong>email:</strong> {email}</p>
        <h2>Access Token Claims</h2>
        <ul>{items}</ul>
        <p><strong>Access Token:</strong> {access}</p>
        <p><a href='/logout'>Logout</a></p>
      </body>
    </html>
    """


@app.get("/logout")
def logout():
    return "<script>location='/'</script>"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8082)
