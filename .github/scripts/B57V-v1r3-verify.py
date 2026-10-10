#!/usr/bin/env python3
"""B57V v1r3 review-only verifier/collector. No signing or study reads.

This code does not itself certify G1/G2/G4. It collects two-client TUF evidence from the same Sigstore upstream,
performs authenticated CLI checks, and preserves verbatim outputs for independent review.
Runs only after the companion GitHub workflow has pinned its exact Git blob and SHA-256.
"""
import base64
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = 'ajknoll23-code/LOG-Trade-Calculator'
RUN_ID = '38008133649'
SOURCE_SHA = 'd48cd3b6f2c17069396c230f0f3e19de68224ffa'
SOURCE_REF = 'refs/heads/main'
SIGNER = REPO + '/.github/workflows/B57R-v1r1.yml'
OIDC_ISSUER = 'https://token.actions.githubusercontent.com'
REPO_ID, OWNER_ID = '1332656701', '302637022'
REKOR_LOG_KEY_ID = 'wNI9atQGlz+VWfO6LRygH4QUfY/8W4RFwiT5i5WRgB0='
REKOR_SIGNING_TIME = dt.datetime(2026, 10, 10, 0, 13, 57, tzinfo=dt.timezone.utc)
ROOT_SNAPSHOT_NOT_BEFORE = dt.datetime(2026, 10, 10, 0, 31, 53, tzinfo=dt.timezone.utc)

# Immutable observed B57R inputs; these ZIP SHAs were checked against Claude's
# independent inspection and the original local downloads. No name search.
ATTEMPTS = {
    1: {'artifact': 11652620406,
        'zip_sha256': 'f0cd9aac71d6c7fa79a8eb7358c254f96ce9d4ef83046fad7c80d6f83930f569',
        'bundle_sha256': 'a99883abfe27f802adbaa45072ccc05b1fa4d4c8a2cf9467a767f5335ae1688f',
        'subject_sha256': '42265630b7bc1cb1bd9c5aaf3569eb751d3a759b74d25ff232ebabc83b090a23'},
    2: {'artifact': 11652576755,
        'zip_sha256': '0ba384dfa708cb859cd4e3115abe465760ca12568ac1a3314f1f50249b0bf49b',
        'bundle_sha256': '6952effbdc5529f131b521eae03f09c1690737d5db512d446bdf6af866038493',
        'subject_sha256': 'bcaa9a93d3890f800f45d0ab37893fd3e61861e83995c1609faa483ff241748c'}
}

# Publisher-advertised digest pins, looked up from official GitHub Releases API.
GH_VERSION = '2.102.0'
GH_ARCHIVE = 'gh_2.102.0_linux_amd64.tar.gz'
GH_ARCHIVE_SHA256 = 'bb766f710eef8ede859c18578c72c327597cd4c8a85b06001b1f3843c6019386'
COSIGN_VERSION = '3.1.3'
COSIGN_SHA256 = '4629c757b7618056f8ddd7e2625ae9fdd94c0372a65049520bc7d9df9efc7f71'

# Independent TUF bootstrap, pinned to a specific sigstore/root-signing commit
# AND the particular Git blob SHA, not a mutable main branch.
SIGSTORE_ANCHOR_COMMIT = 'fa6fe2077745863d57e90a5651e3b331f2b53275'
SIGSTORE_ANCHOR_GIT_BLOB = '3f18ee74ca6415a3a8dbdc30be69fc1b1703c02f'
SIGSTORE_ANCHOR_SHA256 = '836bff947925edfc23eb9ce17af66fb1e43bb5e2bdd240520985ae52b585eae9'
TUF_MIRROR = 'https://tuf-repo-cdn.sigstore.dev'

EXPECTED_MEMBERS = {
    'NOT_A_B57_FREEZE.txt', 'b57r_subject.json',
    'b57r_signed_attestation_bundle.json', 'bundle_sha256.txt',
    'bundle_shape_probe_status.json', 'subject_sha256.txt'
}

class Blocked(RuntimeError):
    pass


def require(ok, code):
    if not ok:
        raise Blocked(code)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(data, code):
    require(data and not data.startswith(b'\xef\xbb\xbf') and b'\r' not in data,
            code + '_EMPTY_BOM_CR')
    def unique(pairs):
        out = {}
        for key, val in pairs:
            require(key not in out, code + '_DUPLICATE_KEY')
            out[key] = val
        return out
    def finite_float(value):
        number = float(value)
        require(number != float('inf') and number != float('-inf') and number == number,
                code + '_NONFINITE_FLOAT')
        return number
    def no_constant(_):
        raise Blocked(code + '_NONFINITE_CONSTANT')
    return json.loads(data.decode('utf-8', errors='strict'), object_pairs_hook=unique,
                      parse_float=finite_float, parse_constant=no_constant)


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


def minimal_subprocess_env(*, home=None):
    """Explicit allowlist. No inherited GitHub, cloud or CI credentials."""
    safe_home = str(home) if home is not None else '/home/runner'
    return {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            'HOME': safe_home, 'LANG': 'C.UTF-8',
            **({'XDG_CACHE_HOME': str(Path(safe_home) / '.cache')} if home is not None else {})}


def run_logged(args, outdir, name, *, env=None, timeout=150, required=True):
    # No subprocess is allowed to inherit process environment, even for --version.
    # Never log tokens or signed artifact download URLs.
    safe = dict(minimal_subprocess_env() if env is None else env)
    require(set(safe).issubset({'PATH', 'HOME', 'LANG', 'XDG_CACHE_HOME'}) and
            {'PATH', 'HOME', 'LANG'}.issubset(safe) and
            not any(k in safe for k in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN')),
            'SUBPROCESS_ENV_NOT_MINIMAL')
    res = subprocess.run(args, capture_output=True, env=safe, timeout=timeout, check=False)
    (outdir / (name + '.stdout')).write_bytes(res.stdout)
    (outdir / (name + '.stderr')).write_bytes(res.stderr)
    record = {'argv': [str(x) for x in args], 'exit_code': res.returncode,
              'stdout_sha256': sha256(res.stdout), 'stderr_sha256': sha256(res.stderr)}
    save_json(outdir / (name + '.exit.json'), record)
    if required:
        require(res.returncode == 0, name.upper() + '_FAILED')
    return res


def download(url, target, *, token=None, max_bytes=150_000_000, expected=None):
    """Bounded HTTPS downloads; bearer credentials used ONLY at api.github.com."""
    uri = urllib.parse.urlsplit(url)
    require(uri.scheme == 'https' and not uri.username and not uri.password,
            'DOWNLOAD_URL_NOT_HTTPS')
    if token:
        require(uri.hostname == 'api.github.com', 'GITHUB_TOKEN_HOST_DENIED')
    headers = {'User-Agent': 'B57V-v1-audit-read-only', 'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    # Public release URLs routinely redirect to GitHub's release asset CDN.
    # For authenticated Actions artifact downloads, NEVER forward the token.
    opener = urllib.request.build_opener(NoRedirect()) if token else urllib.request.build_opener()
    # HTTPError normally includes the full URL, which can contain a short-lived
    # signed blob-storage credential. Never serialize or print that exception.
    # Instead, identify only a fixed local resource, HTTP status, and hop.
    resource = ('attempt_' + target.parent.name.split('-')[-1] + '_artifact'
                if target.name == 'github_artifact.zip'
                else re.sub(r'[^A-Za-z0-9_]', '_', target.name)[:60])
    try:
        response = opener.open(urllib.request.Request(url, headers=headers), timeout=40)
    except urllib.error.HTTPError as e:
        if not token or e.code not in (301, 302, 303, 307, 308):
            raise Blocked('DOWNLOAD_HTTP_' + str(e.code) + '_ORIGIN_' + resource) from None
        loc = e.headers.get('Location')
        require(isinstance(loc, str), 'ARTIFACT_REDIRECT_MISSING_' + resource)
        new = urllib.parse.urlsplit(loc)
        require(new.scheme == 'https' and not new.username and not new.password and
                new.hostname and new.hostname != 'api.github.com',
                'ARTIFACT_REDIRECT_BAD_HOST_' + resource)
        # This request is constructed WITHOUT Authorization. Some GitHub artifact
        # URLs redirect again within the CDN; urllib can follow those redirects.
        try:
            response = urllib.request.urlopen(urllib.request.Request(loc, headers={
                'User-Agent': 'B57V-v1-audit-read-only'}), timeout=40)
        except urllib.error.HTTPError as e2:
            raise Blocked('DOWNLOAD_HTTP_' + str(e2.code) + '_SIGNED_CDN_' + resource) from None
        except urllib.error.URLError:
            raise Blocked('DOWNLOAD_NETWORK_SIGNED_CDN_' + resource) from None
    except urllib.error.URLError:
        raise Blocked('DOWNLOAD_NETWORK_ORIGIN_' + resource) from None
    with response as stream, open(target, 'xb') as out:
        total = 0
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            require(total <= max_bytes, 'DOWNLOAD_SIZE_LIMIT')
            out.write(chunk)
    actual = sha256(Path(target).read_bytes())
    if expected:
        require(actual == expected, 'DOWNLOAD_PIN_MISMATCH_' + Path(target).name)
    return {'path': Path(target).name, 'bytes': total, 'sha256': actual,
            'literal_sha256_pin': expected}


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def load_artifacts(outdir, token):
    result = {}
    for attempt, pins in ATTEMPTS.items():
        dest = outdir / ('attempt-' + str(attempt))
        dest.mkdir()
        archive = dest / 'github_artifact.zip'
        url = 'https://api.github.com/repos/' + REPO + '/actions/artifacts/' + str(pins['artifact']) + '/zip'
        item = download(url, archive, token=token, max_bytes=1_000_000, expected=pins['zip_sha256'])
        with zipfile.ZipFile(archive) as zf:
            require(zf.testzip() is None, 'ARTIFACT_BAD_ZIP')
            require(set(zf.namelist()) == EXPECTED_MEMBERS, 'ARTIFACT_UNEXPECTED_MEMBER_SET')
            for info in zf.infolist():
                require(not info.is_dir() and info.file_size < 100_000 and '/' not in info.filename,
                        'ARTIFACT_MEMBER_NOT_PLAIN_FILE')
                # Avoid symlink extraction and path traversal: use read() + verified name only.
                data = zf.read(info)
                (dest / info.filename).write_bytes(data)
        bundle = (dest / 'b57r_signed_attestation_bundle.json').read_bytes()
        subject = (dest / 'b57r_subject.json').read_bytes()
        require(sha256(bundle) == pins['bundle_sha256'], 'BUNDLE_SHA_PIN_MISMATCH')
        require(sha256(subject) == pins['subject_sha256'], 'SUBJECT_SHA_PIN_MISMATCH')
        obj = strict_json(subject, 'SUBJECT_JSON')
        require(obj.get('run_id') == RUN_ID and type(obj.get('run_attempt')) is int and
                obj['run_attempt'] == attempt and obj.get('workflow_ref') == SIGNER + '@' + SOURCE_REF and
                obj.get('source_commit') == SOURCE_SHA and obj.get('synthetic_only') is True and
                obj.get('production_change_authorized') is False, 'UNEXPECTED_SUBJECT_CLAIMS')
        item.update({'artifact_id': pins['artifact'], 'bundle_sha256': sha256(bundle),
                     'subject_sha256': sha256(subject), 'attempt': attempt})
        result[str(attempt)] = item
    return result


def install_gh(outdir, binaries):
    archive = outdir / GH_ARCHIVE
    item = download('https://github.com/cli/cli/releases/download/v' + GH_VERSION + '/' + GH_ARCHIVE,
                    archive, max_bytes=30_000_000, expected=GH_ARCHIVE_SHA256)
    gh = binaries / 'gh'
    with tarfile.open(archive, 'r:gz') as tf:
        members = [m for m in tf.getmembers() if m.name.endswith('/bin/gh')]
        require(len(members) == 1 and members[0].isfile() and members[0].size < 100_000_000,
                'GH_ARCHIVE_UNEXPECTED_LAYOUT')
        with tf.extractfile(members[0]) as source, open(gh, 'xb') as out:
            shutil.copyfileobj(source, out)
    gh.chmod(0o500)
    item['extracted_gh_binary_sha256_observed_not_preapproved'] = sha256(gh.read_bytes())
    version = run_logged([str(gh), '--version'], outdir, 'gh_version')
    require(('gh version ' + GH_VERSION).encode() in version.stdout, 'GH_VERSION_MISMATCH')
    flags = run_logged([str(gh), 'attestation', 'verify', '--help'], outdir, 'gh_verify_help')
    for flag in ('--bundle', '--custom-trusted-root', '--repo', '--signer-workflow',
                 '--signer-digest', '--source-digest', '--source-ref', '--cert-oidc-issuer',
                 '--predicate-type', '--deny-self-hosted-runners', '--format'):
        require(flag.encode() in flags.stdout, 'GH_MISSING_' + flag)
    return gh, item


def install_cosign(outdir, binaries):
    binary = binaries / 'cosign'
    item = download('https://github.com/sigstore/cosign/releases/download/v' + COSIGN_VERSION +
                    '/cosign-linux-amd64', binary, max_bytes=150_000_000, expected=COSIGN_SHA256)
    binary.chmod(0o500)
    result = run_logged([str(binary), 'version'], outdir, 'cosign_version', timeout=90)
    require(COSIGN_VERSION.encode() in (result.stdout + result.stderr), 'COSIGN_VERSION_MISMATCH')
    return binary, item


def parse_time(value):
    require(isinstance(value, str) and value.endswith('Z'), 'INVALID_TIME')
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(stamp.utcoffset() == dt.timedelta(0), 'TIME_NOT_UTC')
    return stamp


def root_fingerprints(root):
    """Signers' trust material only; NOT cryptographic verification."""
    require(isinstance(root, dict), 'ROOT_NOT_OBJECT')
    certs = set()
    intermediates = set()
    valid_intermediates_at_signing = set()
    for ca in root.get('certificateAuthorities', []):
        for cert in ca.get('certChain', {}).get('certificates', []):
            der = base64.b64decode(cert['rawBytes'], validate=True)
            digest = sha256(der)
            certs.add(digest)
            # Openssl is a *display parser only*. Trust is established by TUF and gh.
            parsed = subprocess.run(['openssl', 'x509', '-inform', 'DER', '-noout', '-subject', '-dates'],
                                    input=der, capture_output=True, check=True, env=minimal_subprocess_env())
            info = parsed.stdout.decode('ascii', errors='replace')
            if re.search(r'CN\s*=\s*sigstore-intermediate(?:\s|,|$)', info):
                fields = dict(line.split('=', 1) for line in info.splitlines() if '=' in line)
                nb = dt.datetime.strptime(fields['notBefore'], '%b %d %H:%M:%S %Y %Z').replace(tzinfo=dt.timezone.utc)
                na = dt.datetime.strptime(fields['notAfter'], '%b %d %H:%M:%S %Y %Z').replace(tzinfo=dt.timezone.utc)
                intermediates.add(digest)
                if nb <= REKOR_SIGNING_TIME <= na:
                    valid_intermediates_at_signing.add(digest)
    logs = {}
    for entry in root.get('tlogs', []):
        kid = entry.get('logId', {}).get('keyId')
        pub = entry.get('publicKey', {})
        if kid and pub.get('rawBytes'):
            logs[kid] = {'sha256': sha256(base64.b64decode(pub['rawBytes'], validate=True)),
                         'start': pub.get('validFor', {}).get('start'),
                         'end': pub.get('validFor', {}).get('end')}
    return {'cert_sha256': sorted(certs), 'intermediate_cert_sha256': sorted(intermediates),
            'valid_intermediate_sha256_at_signing': sorted(valid_intermediates_at_signing),
            'rekor_keys': logs}


def fetch_roots(outdir, gh, cosign):
    """Acquire two separate-client roots. Route B failure NEVER erases route A evidence.

    Both clients use the SAME upstream Sigstore TUF origin; two clients/bootstrap
    paths provide useful consistency checks, NOT independent origin authority.
    """
    root_a = outdir / 'trusted_root_A.jsonl'
    require(not root_a.exists(), 'ROOT_A_ALREADY_EXISTS')
    gh_res = run_logged([str(gh), 'attestation', 'trusted-root'], outdir,
                        'root_A_tuf_gh', timeout=180)
    root_a.write_bytes(gh_res.stdout)
    require(root_a.stat().st_size > 500, 'ROOT_A_TOO_SMALL')

    comparison = {
        'root_A_sha256': sha256(root_a.read_bytes()),
        'route_A_acquisition': 'CAPTURED',
        'route_B_acquisition': 'NOT_STARTED',
        'semantic_comparison': 'NOT_YET_EVALUATED',
        'same_upstream_sigstore_tuf': True,
        'independent_upstream_origins': False,
        'semantic_overlap_is_independent_authentication': False,
        'gates_G1_G2_G4': 'BLOCKED',
    }
    root_b = None
    try:
        anchor_path = outdir / 'sigstore_10.root.json'
        anchor_url = ('https://raw.githubusercontent.com/sigstore/root-signing/' +
                      SIGSTORE_ANCHOR_COMMIT + '/metadata/root_history/10.root.json')
        anchor = download(anchor_url, anchor_path, max_bytes=100_000)
        require(git_blob_sha(anchor_path.read_bytes()) == SIGSTORE_ANCHOR_GIT_BLOB, 'ANCHOR_GIT_BLOB_DRIFT')
        require(sha256(anchor_path.read_bytes()) == SIGSTORE_ANCHOR_SHA256, 'ANCHOR_SHA256_DRIFT')
        anchor.update({'git_blob_sha1_expected': SIGSTORE_ANCHOR_GIT_BLOB,
                       'literal_sha256_expected': SIGSTORE_ANCHOR_SHA256,
                       'root_signing_commit': SIGSTORE_ANCHOR_COMMIT})
        comparison['anchor'] = anchor
        cosign_home = outdir / 'cosign_home'
        cosign_home.mkdir()
        # Never copy os.environ: a fresh, allowlisted cache/home for TUF route B.
        env = minimal_subprocess_env(home=cosign_home)
        run_logged([str(cosign), 'initialize', '--mirror', TUF_MIRROR,
                    '--root', str(anchor_path)], outdir, 'root_B_tuf_cosign',
                   env=env, timeout=180)
        candidates = sorted(cosign_home.rglob('trusted_root.json'))
        require(len(candidates) == 1, 'COSIGN_TRUSTED_ROOT_NOT_UNIQUE')
        # Cosign caches pretty-printed JSON. gh's --custom-trusted-root requires
        # JSONL (one compact object per line), even for a single trusted root.
        # Record the as-acquired digest separately from gh's normalized bytes.
        raw = candidates[0].read_bytes()
        comparison['root_B_cosign_cache_raw_sha256'] = sha256(raw)
        root_b = outdir / 'trusted_root_B.jsonl'
        root_b.write_text(json.dumps(strict_json(raw, 'COSIGN_ROOT_JSON'),
                                     separators=(',', ':'), ensure_ascii=True) + '\n',
                          encoding='utf-8')
        comparison['root_B_sha256'] = sha256(root_b.read_bytes())
        comparison['route_B_acquisition'] = 'CAPTURED'
    except Exception as ex:
        comparison['route_B_acquisition'] = 'FAILED'
        comparison['route_B_error_code'] = type(ex).__name__ + ': ' + str(ex)[:200]

    # Compare independently from acquisition. Preserve both root files even when
    # semantic matching fails, so BOTH routes can be verified and diagnosed.
    if root_b is not None:
        try:
            roots_a = [strict_json(line, 'GH_ROOT_JSONL')
                       for line in root_a.read_bytes().splitlines() if line.strip()]
            bb = root_fingerprints(strict_json(root_b.read_bytes(), 'COSIGN_ROOT_JSON'))
            public_a = [root_fingerprints(x) for x in roots_a]
            a_matches = [a for a in public_a if REKOR_LOG_KEY_ID in a['rekor_keys']]
            require(len(a_matches) == 1, 'PUBLIC_GOOD_ROOT_NOT_UNIQUE')
            a = a_matches[0]
            require(REKOR_LOG_KEY_ID in bb['rekor_keys'], 'REKOR_ID_MISSING_ROUTE_B')
            require(a['rekor_keys'][REKOR_LOG_KEY_ID]['sha256'] ==
                    bb['rekor_keys'][REKOR_LOG_KEY_ID]['sha256'],
                    'REKOR_PUBLIC_KEY_DISAGREEMENT')
            overlap = set(a['valid_intermediate_sha256_at_signing']) & set(bb['valid_intermediate_sha256_at_signing'])
            require(bool(overlap), 'NO_VALID_FULCIO_INTERMEDIATE_AT_SIGNING_IN_BOTH_ROOTS')
            for rec in (a['rekor_keys'][REKOR_LOG_KEY_ID], bb['rekor_keys'][REKOR_LOG_KEY_ID]):
                require(parse_time(rec['start']) <= REKOR_SIGNING_TIME and
                        (not rec['end'] or parse_time(rec['end']) >= REKOR_SIGNING_TIME),
                        'REKOR_KEY_OUTSIDE_SIGNING_WINDOW')
            comparison.update({
                'semantic_comparison': 'MATCH_SANITY_ONLY',
                'root_A_public_good_cert_fingerprints': a['cert_sha256'],
                'root_B_cert_fingerprints': bb['cert_sha256'],
                'matching_rekor_public_key_sha256': a['rekor_keys'][REKOR_LOG_KEY_ID]['sha256'],
                'overlap_fulcio_valid_intermediate_sha256': sorted(overlap),
            })
        except Exception as ex:
            comparison['semantic_comparison'] = 'FAILED'
            comparison['semantic_error_code'] = type(ex).__name__ + ': ' + str(ex)[:200]
    else:
        comparison['semantic_comparison'] = 'NO_ROUTE_B_ROOT'

    comparison['snapshot_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    if dt.datetime.now(dt.timezone.utc) < ROOT_SNAPSHOT_NOT_BEFORE:
        comparison['semantic_comparison'] = 'ROOT_ACQUIRED_BEFORE_CERT_WINDOWS'
    save_json(outdir / 'root_semantic_comparison.json', comparison)
    return root_a, root_b, comparison


def offline_canary(outdir):
    """Prove the EXACT sudo/unshare wrapper is root-owned and has no outbound path."""
    probe = r"""import os, pathlib, socket, sys
if os.geteuid() != 0:
    sys.exit('NOT_ROOT_INSIDE_NETNS')
# /proc/net/dev is network-namespace aware; /sys/class/net may retain the
# parent mount namespace's view under unshare -n and give a false failure.
interfaces = [line.split(':')[0].strip() for line in pathlib.Path('/proc/net/dev').read_text().splitlines()[2:]]
if interfaces != ['lo']:
    sys.exit('UNEXPECTED_NET_INTERFACES:' + repr(sorted(interfaces)))
try:
    sock = socket.create_connection(('1.1.1.1', 443), timeout=2)
except OSError:
    print('B57V_OFFLINE_NETWORK_CANARY_PASS')
else:
    sock.close()
    sys.exit('OUTBOUND_CONNECT_SUCCEEDED')
"""
    res = run_logged(['sudo', '-n', 'unshare', '-n', '--', sys.executable, '-I', '-c', probe],
                     outdir, 'offline_network_isolation_canary', timeout=30, required=False)
    require(res.returncode == 0 and res.stdout.strip() == b'B57V_OFFLINE_NETWORK_CANARY_PASS',
            'OFFLINE_NETWORK_ISOLATION_CANARY_FAILED')
    return {'status': 'PASS', 'stdout_sha256': sha256(res.stdout)}


def attestation_args(gh, a_dir, trusted_root):
    return [str(gh), 'attestation', 'verify', str(a_dir / 'b57r_subject.json'),
            '--bundle', str(a_dir / 'b57r_signed_attestation_bundle.json'),
            '--custom-trusted-root', str(trusted_root), '--repo', REPO,
            '--signer-workflow', SIGNER, '--signer-digest', SOURCE_SHA,
            '--source-digest', SOURCE_SHA, '--source-ref', SOURCE_REF,
            '--cert-oidc-issuer', OIDC_ISSUER,
            '--predicate-type', 'https://slsa.dev/provenance/v1',
            '--deny-self-hosted-runners', '--format', 'json']


def offline_gh_run(args, outdir, label, expect_success):
    # No network namespace in a normal user process: enforce a fresh network
    # namespace as root. A failure to isolate is a BLOCK, never an online fallback.
    res = run_logged(['sudo', '-n', 'unshare', '-n', '--', *args], outdir, label,
                     env=minimal_subprocess_env(), timeout=150, required=False)
    if expect_success:
        require(res.returncode == 0, 'VERIFICATION_FAILED_' + label)
        parsed = strict_json(res.stdout, 'VERIFIED_OUTPUT_' + label)
        require(isinstance(parsed, (dict, list)), 'VERIFIED_JSON_BAD_ROOT_' + label)
    else:
        require(res.returncode != 0, 'NEGATIVE_CONTROL_FALSE_PASS_' + label)
    return res


def run_verification(outdir, gh, root_a, root_b):
    """Verify A and B SEPARATELY, retaining A's evidence even if B fails."""
    checks = {'routes': {}, 'negative_controls': {}, 'offline_network_canary': offline_canary(outdir)}
    for label, trusted_root in (('A', root_a), ('B', root_b)):
        route = {'status': 'NOT_STARTED', 'attempts': {}}
        checks['routes'][label] = route
        if trusted_root is None:
            route['status'] = 'NO_ROOT'
            continue
        for n in (1, 2):
            title = 'route_' + label + '_attempt_' + str(n) + '_verified_json'
            try:
                res = offline_gh_run(attestation_args(gh, outdir / ('attempt-' + str(n)), trusted_root),
                                     outdir, title, True)
                route['attempts'][str(n)] = {'status': 'PASS', 'verified_json_sha256': sha256(res.stdout),
                                             'exit_code': res.returncode}
            except Exception as ex:
                route['attempts'][str(n)] = {'status': 'FAILED',
                                             'error_code': type(ex).__name__ + ': ' + str(ex)[:200]}
        route['status'] = ('PASS' if all(route['attempts'].get(str(n), {}).get('status') == 'PASS'
                                          for n in (1, 2)) else 'FAILED')
    # Negatives require a functioning positive control. Never allow a negative's
    # failure alone to be mistaken for proof of authenticity.
    if checks['routes']['A']['status'] != 'PASS':
        checks['negative_controls']['status'] = 'SKIPPED_A_POSITIVE_NOT_PASSED'
        return checks
    negative_cases = []
    for n in (1, 2):
        original = outdir / ('attempt-' + str(n))
        wrong = outdir / ('attempt-' + str(2 if n == 1 else 1))
        args = attestation_args(gh, original, root_a)
        args[3] = str(wrong / 'b57r_subject.json')
        negative_cases.append(('negative_swap_' + str(n), args))
    args = attestation_args(gh, outdir / 'attempt-1', root_a)
    args[args.index('--signer-workflow') + 1] = REPO + '/.github/workflows/B57-v1r2.yml'
    negative_cases.append(('negative_wrong_signer', args))
    args = attestation_args(gh, outdir / 'attempt-1', root_a)
    args[args.index('--source-digest') + 1] = '0' * 40
    negative_cases.append(('negative_wrong_source_digest', args))
    args = attestation_args(gh, outdir / 'attempt-1', root_a)
    args[args.index('--source-ref') + 1] = 'refs/heads/feature'
    negative_cases.append(('negative_wrong_source_ref', args))
    args = attestation_args(gh, outdir / 'attempt-1', root_a)
    args[args.index('--repo') + 1] = 'unknown/not-the-repo'
    negative_cases.append(('negative_wrong_repo', args))
    for title, args in negative_cases:
        try:
            offline_gh_run(args, outdir, title, False)
            checks['negative_controls'][title] = 'PASS_REJECTED'
        except Exception as ex:
            checks['negative_controls'][title] = 'FAILED_' + type(ex).__name__ + ': ' + str(ex)[:200]
    checks['negative_controls']['status'] = ('PASS' if all(checks['negative_controls'].get(title) == 'PASS_REJECTED'
                                                            for title, _ in negative_cases) else 'FAILED')
    return checks


def main():
    evidence = Path(os.environ.get('RUNNER_TEMP', '/tmp')) / 'b57v-verification-v1'
    evidence.mkdir(mode=0o700, parents=False, exist_ok=False)
    save_json(evidence / 'STATUS.json', {'status': 'STARTED', 'G1': 'BLOCKED', 'G2': 'BLOCKED',
                                        'G4': 'BLOCKED', 'promotion_authorized': False,
                                        'study_data_read_authorized': False})
    print('B57V_COLLECTION_ONLY_NO_SIGNING_NO_PRODUCTION_NO_STUDY_READ')
    state = {'status': 'STARTED', 'G1': 'BLOCKED', 'G2': 'BLOCKED', 'G4': 'BLOCKED',
             'root_A_B_share_sigstore_TUF_upstream': True,
             'independent_root_origins_proven': False,
             'semantic_overlap_is_independent_authentication': False,
             'reviewed_verified_json_field_paths': False,
             'permanent_sigstore_log_writes': False,
             'git_commits': False, 'producer_workflow_changed': False}
    try:
        token = os.environ.pop('GH_TOKEN', '')
        # The token is held only in memory for the bounded API download call.
        # No child process inherits it (or any other inherited CI environment).
        for secret in ('GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN'):
            os.environ.pop(secret, None)
        require(bool(token), 'NO_READ_ONLY_GITHUB_TOKEN')
        state['artifacts'] = load_artifacts(evidence, token)
        binaries = evidence / 'binaries'
        binaries.mkdir()
        gh, state['gh_release'] = install_gh(evidence, binaries)
        cosign, state['cosign_release'] = install_cosign(evidence, binaries)
        root_a, root_b, state['root_comparison'] = fetch_roots(evidence, gh, cosign)
        state['cli_checks'] = run_verification(evidence, gh, root_a, root_b)
        require(state['cli_checks']['routes']['A']['status'] == 'PASS', 'ROOT_A_CLI_VERIFY_FAILED')
        require(state['cli_checks']['routes']['B']['status'] == 'PASS', 'ROOT_B_CLI_VERIFY_FAILED')
        require(state['root_comparison']['semantic_comparison'] == 'MATCH_SANITY_ONLY',
                'ROOT_A_B_SEMANTIC_COMPARISON_NOT_PASSED')
        require(state['cli_checks']['negative_controls']['status'] == 'PASS', 'NEGATIVE_CONTROLS_FAILED')
        state['status'] = 'CLI_VERIFICATION_BOTH_ROOTS_SUCCEEDED_AWAITING_EXACT_FIELD_PATH_REVIEW'
        # Explicitly leave all governance gates BLOCKED: a separately reviewed parser
        # MUST consume gh's authenticated JSON and enforce verified invocation ID+attempt.
        return 0
    except Exception as ex:
        state['status'] = 'BLOCKED_DIAGNOSTIC_ONLY'
        # HTTPError/URLError may contain a temporary bearer-style signed redirect
        # URL. Preserve only reviewed Blocked codes; suppress raw network exceptions.
        safe_detail = str(ex)[:200] if isinstance(ex, Blocked) else 'DETAIL_REDACTED_NETWORK_OR_IO'
        state['error_code'] = type(ex).__name__ + ': ' + safe_detail
        (evidence / 'diagnostic_error.txt').write_text(state['error_code'] + '\n', encoding='utf-8')
        return 1
    finally:
        save_json(evidence / 'STATUS.json', state)
        # Never upload a token, GitHub signed redirect URL, binary, or downloaded
        # release archive. Retain file hashes and certified output, not credentials.
        for p in (evidence / 'binaries',):
            if p.exists():
                shutil.rmtree(p)
        arch = evidence / GH_ARCHIVE
        if arch.exists():
            arch.unlink()
        # Remove cosign cache metadata? Preserve pinned TUF root B plus comparison only.
        cache = evidence / 'cosign_home'
        if cache.exists():
            shutil.rmtree(cache)
        print('B57V_G1_G2_G4_REMAIN_BLOCKED_UNTIL_INDEPENDENT_REVIEW')
        print('B57V_STATUS=' + state['status'])


if __name__ == '__main__':
    sys.exit(main())
