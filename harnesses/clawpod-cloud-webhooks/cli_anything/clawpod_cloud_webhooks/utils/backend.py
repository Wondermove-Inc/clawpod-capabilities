import base64, json, os, socket, time, urllib.error, urllib.request
from http.cookiejar import CookieJar
class BackendError(RuntimeError):
    def __init__(self,code,message,retry_safe=False,status=None): super().__init__(message); self.code=code; self.retry_safe=retry_safe; self.status=status
class Backend:
    def __init__(self,base_url,timeout=5.0,retries=2):
        if not base_url.startswith(("http://","https://")): raise ValueError("base URL must be HTTP(S)")
        if timeout<=0 or timeout>30: raise ValueError("timeout must be >0 and <=30 seconds")
        if retries<0 or retries>3: raise ValueError("retries must be 0..3")
        self.base=base_url.rstrip('/'); self.timeout=timeout; self.retries=retries; self.jar=CookieJar(); self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar)); self.authenticated=False
    def _raw_request(self,method,path,body=None,headers=None,idempotency=None):
        raw=None if body is None else json.dumps(body,separators=(",",":"),sort_keys=True).encode()
        hs={"Accept":"application/json"}; hs.update(headers or {})
        if raw is not None: hs["Content-Type"]="application/json"
        if idempotency: hs["Idempotency-Key"]=idempotency
        attempts=self.retries+1 if method=="GET" else 1
        for i in range(attempts):
            try:
                req=urllib.request.Request(self.base+path,data=raw,headers=hs,method=method)
                with self.opener.open(req,timeout=self.timeout) as rsp:
                    data=rsp.read(2_097_152)
                    if len(data)>=2_097_152: raise BackendError("response_too_large","backend response exceeds cap")
                    return json.loads(data or b'{}')
            except urllib.error.HTTPError as e:
                retry=e.code in (429,502,503,504) and method=="GET"
                if retry and i+1<attempts: time.sleep(min(.05*(2**i),.2)); continue
                raise BackendError("auth_failed" if e.code in (401,403) else "backend_error",f"backend HTTP {e.code}",retry_safe=method=="GET",status=e.code)
            except (urllib.error.URLError,socket.timeout,TimeoutError):
                if method=="GET" and i+1<attempts: time.sleep(min(.05*(2**i),.2)); continue
                raise BackendError("timeout","backend request timed out",retry_safe=method=="GET")
    def login_from_env(self):
        email=os.environ.get('CLAWPOD_CLOUD_EMAIL'); password=os.environ.get('CLAWPOD_CLOUD_PASSWORD')
        if not email or not password:
            raise BackendError('auth_required','authenticated command requires protected CLAWPOD_CLOUD_EMAIL and CLAWPOD_CLOUD_PASSWORD environment injection',False)
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            key_data=self._raw_request('GET','/api/auth/public-key')
            pem=key_data.get('public_key') or key_data.get('publicKey')
            if not pem: raise BackendError('auth_contract_error','public-key response omitted public key',False)
            public_key=serialization.load_pem_public_key(pem.encode())
            plaintext=json.dumps({'password':password,'timestamp':int(time.time()*1000)},separators=(',',':')).encode()
            encrypted=public_key.encrypt(plaintext,padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
            self._raw_request('POST','/api/auth/login',body={'email':email,'encrypted_password':base64.b64encode(encrypted).decode()})
            self.authenticated=True
        except BackendError: raise
        except Exception:
            raise BackendError('auth_contract_error','RSA-OAEP login setup failed',False)
    def request(self,method,path,body=None,headers=None,idempotency=None,authenticated=True):
        if authenticated and not self.authenticated: self.login_from_env()
        return self._raw_request(method,path,body,headers,idempotency)
    def session_status(self): return {"connected":self.authenticated and bool(list(self.jar)),"session_storage":"protected in-memory CookieJar","cookie_values_exposed":False}
RSA_CONTRACT={"algorithm":"RSA-OAEP","hash":"SHA-256","public_key_path":"/api/auth/public-key","login_path":"/api/auth/login","refresh_path":"/api/auth/refresh","logout_path":"/api/auth/logout","credential_environment":["CLAWPOD_CLOUD_EMAIL","CLAWPOD_CLOUD_PASSWORD"],"credential_transport":"encrypt JSON password and millisecond timestamp with portal public key","session":"HttpOnly cookie retained only in protected process-memory CookieJar","plaintext_persistence":False}
