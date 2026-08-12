import pytest
from cli_anything.clawpod_cloud_webhooks.core.safety import *
from cli_anything.clawpod_cloud_webhooks.core.contracts import *
from cli_anything.clawpod_cloud_webhooks.utils.backend import Backend, RSA_CONTRACT

def test_redacts_headers_recursively():
    x=redact({'headers':{'Authorization':'Bearer nope','Cookie':'sid=nope','X-Webhook-Signature':'nope'},'nested':[{'signing_secret':'nope'}]})
    assert 'nope' not in str(x) and str(x).count('[REDACTED]')==4
def test_redacts_url_token(): assert 'abcDEF123456' not in redact('https://x/incoming/abcDEF123456')
def test_redacts_bearer_in_string(): assert 'token123' not in redact('Bearer token123')
def test_redacts_nested_json_strings_objects_and_lists():
    canaries=['CANARY_COOKIE','CANARY_AUTH','CANARY_PROXY','CANARY_SET','CANARY_SIG','CANARY_TOKEN','CANARY_SECRET','CANARY_PASSWORD','CANARY_API']
    value={'headers':'{"cOoKiE":"CANARY_COOKIE","AUTHORIZATION":"Bearer CANARY_AUTH","Proxy-Authorization":"CANARY_PROXY","Set-Cookie":"CANARY_SET","x-WebHook-Signature":"CANARY_SIG"}',
           'payload':'[{"token":"CANARY_TOKEN"},{"nested":"{\\"secret\\":\\"CANARY_SECRET\\",\\"Password\\":\\"CANARY_PASSWORD\\",\\"api-key\\":\\"CANARY_API\\"}"}]',
           'useful':'keep-me'}
    cleaned=redact(value)
    rendered=json.dumps(cleaned)
    assert all(canary not in rendered for canary in canaries)
    assert cleaned['useful']=='keep-me'
    assert isinstance(cleaned['headers'],dict) and isinstance(cleaned['payload'],list)
def test_redacts_malformed_and_non_json_text_patterns():
    canaries=['CANARY_BAD_COOKIE','CANARY_BAD_TOKEN','CANARY_FORM_PASSWORD']
    value={'malformed':'{"Cookie":"CANARY_BAD_COOKIE", token=CANARY_BAD_TOKEN',
           'form':'name=useful password=CANARY_FORM_PASSWORD note=kept'}
    rendered=json.dumps(redact(value))
    assert all(canary not in rendered for canary in canaries)
    assert 'useful' in rendered and 'kept' in rendered
def test_redacts_unclosed_quoted_values_and_preserves_separated_text():
    canaries=['CANARY_UNCLOSED_COOKIE','CANARY_UNCLOSED_AUTH','CANARY_UNCLOSED_API']
    cases=[
        'useful=kept; Cookie="CANARY_UNCLOSED_COOKIE',
        'prefix kept, authorization=\'CANARY_UNCLOSED_AUTH',
        'note:kept api-key="CANARY_UNCLOSED_API',
    ]
    cleaned=[redact(value) for value in cases]
    rendered=json.dumps(cleaned)
    assert all(canary not in rendered for canary in canaries)
    assert 'useful=kept' in cleaned[0] and 'prefix kept' in cleaned[1] and 'note:kept' in cleaned[2]
def test_redacts_quoted_values_at_common_separators():
    canaries=['CANARY_SEMICOLON','CANARY_COMMA','CANARY_BRACE']
    value='Cookie="CANARY_SEMICOLON"; authorization=\'CANARY_COMMA\', api-key="CANARY_BRACE"}'
    cleaned=redact(value)
    assert all(canary not in cleaned for canary in canaries)
    assert ';' in cleaned and ',' in cleaned and '}' in cleaned
def test_sensitive_parent_key_replaces_malformed_value():
    assert redact({'CoOkIe':'not-json CANARY_PARENT'})['CoOkIe']=='[REDACTED]'
def test_digest_deterministic(): assert digest({'b':2,'a':1})==digest({'a':1,'b':2})
def test_payload_exact_cap(): validate_body(b'x'*MAX_BODY)
def test_payload_over_cap():
    with pytest.raises(ValueError): validate_body(b'x'*(MAX_BODY+1))
@pytest.mark.parametrize('op',sorted(BROKEN_OPS))
def test_broken_operators_rejected(op):
    with pytest.raises(ValueError): validate_features({'conditions':[{'operator':op}]})
def test_template_rejected():
    with pytest.raises(ValueError): validate_features({'message_template':'{{x}}'})
def test_agent_target_requires_proof():
    with pytest.raises(ValueError): guard_agent_targets({'targets':[{'type':'agent'}]})
def test_idempotency_required():
    with pytest.raises(ValueError): require_idempotency('')
def test_source_full_merge_preserves_nullable():
    cur={'name':'n','playbook_id':'p','is_active':True,'provider':'custom','tenant_id':'t'}
    assert source_merge(cur,{'is_active':False})['playbook_id']=='p'
def test_source_unknown_field_rejected():
    with pytest.raises(ValueError): source_merge({}, {'url_token':'x'})
def test_tenant_preflight_rejects_target():
    with pytest.raises(ValueError): preflight({'targets':[{'tenant_id':'other'}]},'t')
def test_preview_has_approval_and_digest():
    p=preview('rule','r',{}, {'tenant_id':'t'},'t','key-1'); assert p['requires_approval'] and p['effect_digest'].startswith('sha256:')
def test_idempotency_key_is_bound_into_every_effect_digest():
    assert preview('rule','r',{}, {'tenant_id':'t'},'t','key-1')['effect_digest'] != preview('rule','r',{}, {'tenant_id':'t'},'t','key-2')['effect_digest']
    assert create_preview('playbook',{'name':'p','tenant_id':'t'},'t','key-1')['effect_digest'] != create_preview('playbook',{'name':'p','tenant_id':'t'},'t','key-2')['effect_digest']
    assert delete_preview('source','s',{'tenant_id':'t'},'t','key-1')['effect_digest'] != delete_preview('source','s',{'tenant_id':'t'},'t','key-2')['effect_digest']
def test_create_payload_tenant_conflict_is_rejected():
    with pytest.raises(ValueError,match='tenant isolation mismatch'): validate_payload('playbook',{'name':'p','tenant_id':'other'},'t')
def test_delivered_with_error_fails(): assert not verify_event({'status':'delivered','error_message':'tenant isolation violation'})['ok']
def test_destination_proof_required(): assert not verify_event({'status':'delivered'},True)['ok']
def test_secret_warning_retains_expiry(): assert secret_warning({'previous_secret_expires_at':'later'},'regenerate')['previous_secret_may_remain_valid']
def test_timeout_bounds():
    with pytest.raises(ValueError): Backend('http://x',timeout=31)
def test_rsa_contract(): assert RSA_CONTRACT['algorithm']=='RSA-OAEP' and RSA_CONTRACT['hash']=='SHA-256' and not RSA_CONTRACT['plaintext_persistence']

def test_readback_semantics_normalize_numeric_identifier_types():
    from cli_anything.clawpod_cloud_webhooks.core.contracts import readback_mismatches
    expected = {'name': 'n', 'tenant_id': '2', 'playbook_id': '17'}
    actual = {'name': 'n', 'tenant_id': 2, 'playbook_id': 17}
    assert readback_mismatches('source', expected, actual) == {}
    actual['name'] = 'changed'
    assert readback_mismatches('source', expected, actual)['name']['actual'] == 'changed'


def test_playbook_readback_verifies_only_returned_contract_fields():
    from cli_anything.clawpod_cloud_webhooks.core.contracts import readback_mismatches, validate_payload
    payload = validate_payload('playbook', {'name': 'p', 'content': 'c'}, '2')
    assert readback_mismatches('playbook', payload, {'name': 'p', 'content': 'c', 'tenant_id': 2}) == {}
    with pytest.raises(ValueError, match='unknown Playbook fields: is_active'):
        validate_payload('playbook', {'name': 'p', 'content': 'c', 'is_active': True}, '2')
