import base64, json, os, socket, ssl, stat, time, urllib.error, urllib.parse, urllib.request
from http.cookiejar import CookieJar

TLS_RISK_APPROVAL_FLAG = "--i-understand-insecure-tls-risk"
TLS_MODES = ("strict", "custom_ca", "insecure_approved")

class BackendError(RuntimeError):
    def __init__(self,code,message,retry_safe=False,status=None): super().__init__(message); self.code=code; self.retry_safe=retry_safe; self.status=status

def _tls_context(base_url, ca_cert_path=None, insecure_skip_tls_verify=False, insecure_risk_approved=False):
    parsed=urllib.parse.urlsplit(base_url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("base URL must use HTTPS")
    if ca_cert_path and insecure_skip_tls_verify:
        raise ValueError("custom CA and insecure TLS mode cannot be combined")
    if insecure_skip_tls_verify and not insecure_risk_approved:
        raise ValueError(f"insecure TLS mode requires explicit risk acceptance with {TLS_RISK_APPROVAL_FLAG}")
    if insecure_risk_approved and not insecure_skip_tls_verify:
        raise ValueError(f"{TLS_RISK_APPROVAL_FLAG} is valid only with --insecure-skip-tls-verify")
    if ca_cert_path:
        try:
            info=os.stat(ca_cert_path)
            if not stat.S_ISREG(info.st_mode) or not os.access(ca_cert_path,os.R_OK): raise OSError
            context=ssl.create_default_context(cafile=ca_cert_path)
        except (OSError,ssl.SSLError):
            raise ValueError("CA certificate must be a readable regular PEM file")
        return context,"custom_ca"
    if insecure_skip_tls_verify:
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname=False; context.verify_mode=ssl.CERT_NONE
        return context,"insecure_approved"
    return ssl.create_default_context(),"strict"

class Backend:
    def __init__(self,base_url,timeout=5.0,retries=2,ca_cert_path=None,insecure_skip_tls_verify=False,insecure_risk_approved=False):
        if timeout<=0 or timeout>30: raise ValueError("timeout must be >0 and <=30 seconds")
        if retries<0 or retries>3: raise ValueError("retries must be 0..3")
        self.ssl_context,self.tls_verification_mode=_tls_context(base_url,ca_cert_path,insecure_skip_tls_verify,insecure_risk_approved)
        self.base=base_url.rstrip('/'); self.timeout=timeout; self.retries=retries; self.jar=CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.ssl_context),urllib.request.HTTPCookieProcessor(self.jar)); self.authenticated=False
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
                code="auth_failed" if e.code in (401,403) else "not_found" if e.code==404 else "backend_error"
                raise BackendError(code,f"backend HTTP {e.code}",retry_safe=method=="GET",status=e.code)
            except urllib.error.URLError as e:
                if isinstance(e.reason,ssl.SSLCertVerificationError):
                    raise BackendError("tls_verification_failed","TLS certificate verification failed",retry_safe=True)
                if method=="GET" and i+1<attempts: time.sleep(min(.05*(2**i),.2)); continue
                raise BackendError("timeout","backend request timed out",retry_safe=method=="GET")
            except (socket.timeout,TimeoutError):
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
            ciphertext=base64.b64encode(encrypted).decode()
            self._raw_request('POST','/api/auth/login',body={'email':email,'password':ciphertext,'rememberMe':False})
            self.authenticated=True
        except BackendError: raise
        except Exception:
            raise BackendError('auth_contract_error','RSA-OAEP login setup failed',False)
    def request(self,method,path,body=None,headers=None,idempotency=None,authenticated=True):
        if authenticated and not self.authenticated: self.login_from_env()
        return self._raw_request(method,path,body,headers,idempotency)
    def session_status(self): return {"connected":self.authenticated and bool(list(self.jar)),"session_storage":"protected in-memory CookieJar","cookie_values_exposed":False,"tls_verification_mode":self.tls_verification_mode}
RSA_CONTRACT={"algorithm":"RSA-OAEP","hash":"SHA-256","public_key_path":"/api/auth/public-key","login_path":"/api/auth/login","login_request_fields":["email","password","rememberMe"],"encrypted_field":"password","remember_me":False,"refresh_path":"/api/auth/refresh","logout_path":"/api/auth/logout","credential_environment":["CLAWPOD_CLOUD_EMAIL","CLAWPOD_CLOUD_PASSWORD"],"credential_transport":"encrypt JSON password and millisecond timestamp with portal public key; place the ciphertext in the outer password field","session":"HttpOnly cookie retained only in protected process-memory CookieJar","plaintext_persistence":False,"tls":{"default":"strict","preferred_internal_network_exception":"custom_ca","insecure_exception":"explicitly approved internal networks only","ca_persisted":False}}
