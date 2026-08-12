import io, json, urllib.error
import pytest
from google_workspace_core.auth import AuthError, CredentialProvider


def _bundle(path):
 path.write_text(json.dumps({'accounts':{'work':{'access_token':'old','expires_at':0,'refresh_token':'REFRESH_SECRET','client_id':'CLIENT_SECRET','client_secret':'CLIENT_SECRET_VALUE'}}}))
 path.chmod(0o600)
 return CredentialProvider(str(path))


def test_refresh_invalid_grant_is_sanitized_and_actionable(tmp_path,monkeypatch):
 provider=_bundle(tmp_path/'credential.json')
 body=b'{"error":"invalid_grant","error_description":"PROVIDER_SECRET_BODY"}'
 error=urllib.error.HTTPError('https://oauth2.googleapis.com/token',400,'bad',{},io.BytesIO(body))
 monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:(_ for _ in ()).throw(error))
 with pytest.raises(AuthError) as caught: provider.token('work')
 text=str(caught.value)
 assert 'seven-day expiry' in text and 'revocation' in text and 'reauthorize this agent' in text
 assert 'PROVIDER_SECRET_BODY' not in text and 'REFRESH_SECRET' not in text and 'CLIENT_SECRET' not in text


def test_refresh_non_http_failure_is_sanitized(tmp_path,monkeypatch):
 provider=_bundle(tmp_path/'credential.json')
 monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:(_ for _ in ()).throw(urllib.error.URLError('SECRET_NETWORK_DETAIL')))
 with pytest.raises(AuthError,match='credential refresh failed') as caught: provider.token('work')
 assert 'SECRET_NETWORK_DETAIL' not in str(caught.value)
