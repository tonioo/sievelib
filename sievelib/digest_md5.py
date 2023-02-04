"""
Simple Digest-MD5 implementation (client side)

Implementation based on RFC 2831 (http://www.ietf.org/rfc/rfc2831.txt)
"""

import base64
import hashlib
import re
import secrets


class DigestMD5(object):
    def __init__(self, challenge, digesturi):
        self.__digesturi = digesturi
        self.__challenge = challenge

        self.__params = {}
        pexpr = re.compile(r'(\w+)="(.+)"')
        for elt in base64.b64decode(challenge).decode("latin").split(","):
            m = pexpr.match(elt)
            if m is None:
                continue
            self.__params[m.group(1)] = m.group(2)

    def __make_cnonce(self):
        return base64.b64encode(secrets.token_bytes(12))

    def __digest(self, value):
        return hashlib.md5(value.encode("latin")).digest()

    def __hexdigest(self, value):
        return hashlib.md5(value.encode("latin")).hexdigest()

    def __make_response(self, username, password, check=False):
        a1 = "%s:%s:%s" % (
            self.__digest("%s:%s:%s" % (username, self.realm, password)),
            self.__params["nonce"], self.cnonce
        )
        if check:
            a2 = ":%s" % self.__digesturi
        else:
            a2 = "AUTHENTICATE:%s" % self.__digesturi
        resp = "%s:%s:00000001:%s:auth:%s" \
               % (self.__hexdigest(a1), self.__params["nonce"],
                  self.cnonce, self.__hexdigest(a2))

        return self.__hexdigest(resp)

    def response(self, username, password, authz_id=''):
        self.realm = self.__params.get("realm", "")
        self.cnonce = self.__make_cnonce()
        respvalue = self.__make_response(username, password)

        dgres = 'username="%s",%snonce="%s",cnonce="%s",nc=00000001,qop=auth,' \
                'digest-uri="%s",response=%s' \
            % (username,
               ('realm="%s",' % self.realm) if len(self.realm) else "",
               self.__params["nonce"], self.cnonce, self.__digesturi, respvalue)
        if authz_id:
            dgres += ',authzid="%s"' % authz_id

        return base64.b64encode(dgres.encode("latin"))

    def check_last_challenge(self, username, password, value):
        challenge = base64.b64decode(value.strip('"'))
        return challenge == \
               ("rspauth=%s" % self.__make_response(username, password, True))
