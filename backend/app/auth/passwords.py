"""用户密码哈希与验证。"""

from pwdlib import PasswordHash


_password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """使用推荐的Argon2配置生成密码哈希。"""

    return _password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """验证明文密码是否匹配已有哈希。"""

    return _password_hasher.verify(
        password,
        password_hash,
    )