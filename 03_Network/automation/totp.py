"""Second factor of the bastion (SRV-BASTION): print the current TOTP code of the administration account.

  python automation/totp.py            current 6-digit code and its remaining validity
The secret is `credentials.bastion_totp_secret` in the inventory (lab only). A real administrator would hold it in an
authenticator application; in the lab this helper plays that role. RFC 6238, SHA-1, 30 s step, 6 digits.
"""
import base64
import hashlib
import hmac
import struct
import sys
import time
from pathlib import Path

# The same function is sent to the GNS3 VM by access_matrix.py: keep it free of third-party imports.
TOTP_SOURCE = '''import base64, hashlib, hmac, struct, sys, time
def totp(secret, at=None):
    key = base64.b32decode(secret.upper())
    digest = hmac.new(key, struct.pack(">Q", int(at if at is not None else time.time()) // 30), hashlib.sha1).digest()
    o = digest[-1] & 15
    return "%06d" % ((struct.unpack(">I", digest[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)
'''
exec(TOTP_SOURCE)


if __name__ == "__main__":
    import yaml
    inv = yaml.safe_load((Path(__file__).resolve().parents[1] / "inventory" / "dc_casa.yaml").read_text(encoding="utf-8"))
    print(f"{totp(inv['credentials']['bastion_totp_secret'])}   (valid {30 - int(time.time()) % 30} s more)")  # noqa: F821
