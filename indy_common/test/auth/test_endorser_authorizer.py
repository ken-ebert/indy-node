import pytest
import time

from indy_common.authorize.auth_constraints import AuthConstraint, IDENTITY_OWNER
from indy_common.authorize.authorizer import EndorserAuthorizer
from indy_common.constants import ENDORSER, NETWORK_MONITOR
from indy_common.types import Request
from indy_node.persistence.idr_cache import IdrCache
from plenum.common.constants import CURRENT_PROTOCOL_VERSION, STEWARD, TRUSTEE
from plenum.test.helper import randomOperation
from storage.kv_in_memory import KeyValueStorageInMemory

AUTH_CONSTR = AuthConstraint(role=ENDORSER, sig_count=1)


def get_idr_by_role(role):
    if role == TRUSTEE:
        return "trustee_did"
    if role == STEWARD:
        return "steward_did"
    if role == ENDORSER:
        return "endorser_did"
    if role == NETWORK_MONITOR:
        return "network_monitor_did"
    return "no_role_did"


@pytest.fixture(scope='module')
def idr_cache():
    cache = IdrCache("Cache",
                     KeyValueStorageInMemory())
    cache.set("author_no_role", 1, int(time.time()), role=IDENTITY_OWNER,
              verkey="SomeVerkey", isCommitted=False)
    cache.set("trustee_did", 1, int(time.time()), role=TRUSTEE,
              verkey="SomeVerkey1", isCommitted=False)
    cache.set("steward_did", 1, int(time.time()), role=STEWARD,
              verkey="SomeVerkey2", isCommitted=False)
    cache.set("endorser_did", 1, int(time.time()), role=ENDORSER,
              verkey="SomeVerkey3", isCommitted=False)
    cache.set("no_role_did", 1, int(time.time()), role=IDENTITY_OWNER,
              verkey="SomeVerkey4", isCommitted=False)
    cache.set("network_monitor_did", 1, int(time.time()), role=NETWORK_MONITOR,
              verkey="SomeVerkey5", isCommitted=False)
    cache.set("endorser_did2", 1, int(time.time()), role=ENDORSER,
              verkey="SomeVerkey6", isCommitted=False)
    return cache


@pytest.fixture(scope='module')
def authorizer(idr_cache):
    return EndorserAuthorizer(cache=idr_cache)


def build_req_multi_signed_by_endorser(author_role, endorser_role=ENDORSER, append_endorser=False):
    author_idr = get_idr_by_role(author_role) if author_role != IDENTITY_OWNER else "author_no_role"
    endorser_idr = get_idr_by_role(endorser_role)
    req = Request(identifier=author_idr,
                  reqId=1,
                  operation=randomOperation(),
                  signatures={endorser_idr: "sig1", author_idr: "sig2"},
                  protocolVersion=CURRENT_PROTOCOL_VERSION)
    if append_endorser:
        req.endorser = endorser_idr
    return req


def build_req_multi_signed_by_author_only(author_role):
    idr = get_idr_by_role(author_role)
    return Request(identifier=idr,
                   reqId=1,
                   operation=randomOperation(),
                   signatures={idr: "sig2"},
                   protocolVersion=CURRENT_PROTOCOL_VERSION)


def build_req_multi_signed_by_non_author_only(author_role, non_author_role):
    return Request(identifier=get_idr_by_role(author_role),
                   reqId=1,
                   operation=randomOperation(),
                   signatures={get_idr_by_role(non_author_role): "sig"},
                   protocolVersion=CURRENT_PROTOCOL_VERSION)


def build_req_signed_by_author_only(author_role):
    idr = get_idr_by_role(author_role)
    return Request(identifier=idr,
                   reqId=1,
                   operation=randomOperation(),
                   signature="sig2",
                   protocolVersion=CURRENT_PROTOCOL_VERSION)


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD, ENDORSER])
def test_dont_require_endorser_if_one_sig(authorizer, author_role):
    req = build_req_signed_by_author_only(author_role)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD, ENDORSER])
def test_dont_require_endorser_if_one_multisig(authorizer, author_role):
    req = build_req_multi_signed_by_author_only(author_role)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR])
@pytest.mark.parametrize('non_author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD, ENDORSER])
def test_require_endorser_if_signed_by_non_author(authorizer, author_role, non_author_role):
    if author_role == non_author_role:
        return
    req = build_req_multi_signed_by_non_author_only(author_role, non_author_role)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert not authorized
    assert "'Endorser' field must be explicitly set for the endorsed transaction" in reason


@pytest.mark.parametrize('author_role', [TRUSTEE, STEWARD, ENDORSER])
@pytest.mark.parametrize('non_author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD, ENDORSER])
def test_dont_require_endorser_if_signed_by_non_author(authorizer, author_role, non_author_role):
    if author_role == non_author_role:
        return
    req = build_req_multi_signed_by_non_author_only(author_role, non_author_role)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR])
def test_require_endorser_when_multi_sig(authorizer, author_role):
    # isn't authorized without explicit Endorser field
    req = build_req_multi_signed_by_endorser(author_role, append_endorser=False)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert not authorized
    assert "'Endorser' field must be explicitly set for the endorsed transaction" in reason

    # authorized with explicit Endorser field
    req = build_req_multi_signed_by_endorser(author_role, append_endorser=True)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('author_role', [TRUSTEE, STEWARD, ENDORSER])
def test_dont_require_endorser_when_multi_sig(authorizer, author_role):
    # authorized even without explicit Endorser field
    req = build_req_multi_signed_by_endorser(author_role, append_endorser=False)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized

    # authorized with explicit Endorser field
    req = build_req_multi_signed_by_endorser(author_role, append_endorser=True)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('endorser_role', [ENDORSER])
def test_allowed_endorser_roles(authorizer, endorser_role):
    req = build_req_multi_signed_by_endorser(author_role=IDENTITY_OWNER,
                                             endorser_role=endorser_role, append_endorser=True)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('endorser_role', [TRUSTEE, STEWARD, IDENTITY_OWNER, NETWORK_MONITOR])
def test_not_allowed_endorser_roles(authorizer, endorser_role):
    req = build_req_multi_signed_by_endorser(author_role=IDENTITY_OWNER,
                                             endorser_role=endorser_role, append_endorser=True)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert not authorized
    assert "Endorser must have one of the following roles" in reason


@pytest.mark.parametrize('author_role', [TRUSTEE, STEWARD, ENDORSER])
def test_endorser_role_checked_when_author_is_endorser(authorizer, author_role):
    req = build_req_multi_signed_by_endorser(author_role=author_role,
                                             endorser_role=IDENTITY_OWNER, append_endorser=True)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert not authorized
    assert "Endorser must have one of the following roles" in reason


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD])
def test_endorser_must_sign(authorizer, author_role):
    req = build_req_multi_signed_by_author_only(author_role=author_role)
    req.endorser = get_idr_by_role(ENDORSER)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert not authorized
    assert "Endorser must sign the transaction" in reason


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD])
def test_endorser_is_author_and_1_sig(authorizer, author_role):
    req = build_req_signed_by_author_only(author_role=ENDORSER)
    req.endorser = get_idr_by_role(ENDORSER)
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert authorized


@pytest.mark.parametrize('author_role', [IDENTITY_OWNER, NETWORK_MONITOR, TRUSTEE, STEWARD])
def test_endorser_is_not_author_and_1_sig(authorizer, author_role):
    req = build_req_signed_by_author_only(author_role=ENDORSER)
    req.endorser = "endorser_did2"
    authorized, reason = authorizer.authorize(req, AUTH_CONSTR)
    assert not authorized
    assert "Endorser must sign the transaction" in reason
