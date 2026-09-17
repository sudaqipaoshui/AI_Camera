#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
@author:sonic.gao
@time: 2025/06/18 21:26
@contact: gaoyuhang@dreamsports.ai
@description: 各种加密算法实现
"""
import base64
import hashlib
import pyDes
import requests
import unpaddedbase64
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP as PKCS, PKCS1_v1_5
from Crypto.Hash import SHA3_256
from Crypto.Hash import SHA256
from Crypto.Signature.pss import MGF1
import time
consts = [
    "2976ae25f6b04f719f351e2fd890fa50",
    "ed8abe8d1fc3456a8a1e366151c2a6b7",
    "6b10b3f89d1c4bfa8199ff3f74aa2887",
    "a76d51834a4f4609a38d1a0f5e3d6465",
    "e6be849e07c64511a17b777743021af3",
    "3edb5e23e8b34f848af4888feb169e9b",
    "c527b8e5816346c6a586e7ea9db27fa5",
    "bb719cd4f60d4567a19103187e855b30",
    "85c9ff17d6cf46bbbea8e8671d25a944",
    "9341dc8b84bb422598a890273a28fe09"
]


def get_encryption(host, app_id=10000, **kwargs):
    url = host + "/api/1/poseidon/account/get_encryption"
    querystring = {"app_id": app_id}
    response = requests.request("GET", url, params=querystring)
    return response.json()['data']['key_id'], response.json()['data']['key']


def get_encryption2(host, app_id=10000):
    """
    获取key_id/key
    每次要用到密码的时候，先调用本接口，获取key和key_id
    把密码使用rsa加密,BASE64, 再传输，并带上本次的key_id,规则见新版密码规则
    """
    url = host + "/acc/2/in/get_encryption"
    querystring = {"app_id": app_id,'none':int(time.time())}
    response = requests.request("GET", url, params=querystring)
    return response.json()['data']['key_id'], response.json()['data']['key']


def rsa(raw, key):
    """
    RSA加密
    :param raw: 明文密码或者pin_code
    :param key: 用来RSA加密的public key，会在一定时间内失效，请在实际使用时通过get_encryption2获取。
    :return: rsa加密后的字符串
    """
    keyDER = unpaddedbase64.decode_base64(key)
    keyPub = RSA.importKey(keyDER)
    cipher = PKCS.new(keyPub, SHA3_256, lambda x, y: MGF1(x, y, SHA256))
    cipher_text = cipher.encrypt(raw.encode())
    return base64.urlsafe_b64encode(cipher_text)


def sha3256(raw):
    """
    SHA3-256算法
    :param raw: 待加密的字符串。
    :return: SHA3-256加密后的字符串
    """
    salt = consts[ord(raw[0]) % len(consts)]
    sh = SHA3_256.new()
    sh.update((raw + salt).encode("utf-8"))
    return sh.hexdigest()


def rsa_pkcs_key_pair(bits=2048):
    """
    PKCS格式的RSA密钥对，public key in pkcs8 , private key in pkcs1
    :param bits:
    :return:
    """
    key = RSA.generate(bits)
    pub_key_pkcs = base64.b64encode(key.publickey().exportKey(pkcs=8)).decode()
    prv_key_pkcs = base64.b64encode(key.exportKey(pkcs=1)).decode()
    return pub_key_pkcs, prv_key_pkcs


def rsa_encrypt(s, public_key):
    """
    :param s: 原字符串
    :param public_key: unicode bytes or PEM encode的字符串
    :return: base64编码bytes string
    """
    key = RSA.importKey(public_key)
    cipher = PKCS1_v1_5.new(key)
    cipher_text = base64.b64encode(cipher.encrypt(bytes(s, 'utf-8')))
    return cipher_text


def rsa_decrypt(s, private_key):
    """
    :param s: base64编码bytes string
    :param private_key: bytes or PEM encode的字符串
    :return: string
    """
    key = RSA.importKey(private_key)
    cipher = PKCS1_v1_5.new(key)
    raw_text = cipher.decrypt(base64.b64decode(s), None).decode()
    return raw_text


def des3_encrypt(s, key):
    """
    :param s: 原字符串
    :param key: unicode bytes or PEM encode的字符串
    :return: base64编码bytes string
    """
    m5 = hashlib.md5()
    m5.update(key.encode('utf-8'))
    key_m = m5.digest()
    key_m += key_m[0:8]
    k = pyDes.triple_des(key_m, pyDes.CBC, IV="\0\0\0\0\0\0\0\0", pad=None, padmode=pyDes.PAD_PKCS5)
    d = k.encrypt(s)
    return base64.b64encode(d).decode()
