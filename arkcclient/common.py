#!/usr/bin/env python3
# coding:utf-8

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from requests import get
import socket
import struct
import logging
import random
import bisect
import os
import base64
from hashlib import sha1
from time import time
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate

# For the ugly hack to introduce pycrypto v2.7a1
from Crypto.Util.number import long_to_bytes
from Crypto.Util.py3compat import bord, bchr, b
import binascii

logging.getLogger("requests").setLevel(logging.DEBUG)

# TODO:Need to switch to PKCS for better security

SOURCE_EMAIL = "arkctechnology@hotmail.com"
PASSWORD = "ahafreedom123456!"


def sendkey(dest_email, prihash, pubdir):
    try:
        msg = MIMEMultipart(
            From=SOURCE_EMAIL,
            To=dest_email,
            Date=formatdate(localtime=True),
            Subject="Conference Registration"
        )
        msg.attach(MIMEText(prihash))
        msg['Subject'] = "Conference Registration"
        msg['From'] = SOURCE_EMAIL
        msg['To'] = dest_email
        with open(pubdir, "rb") as fil:
            msg.attach(MIMEApplication(
                fil.read(),
                Content_Disposition='attachment; filename="Conference File.pdf"',
                Name="Conference File.pdf"
            ))
        smtp = smtplib.SMTP('smtp.live.com', 587, timeout=2)
        smtp.starttls()
        smtp.login(SOURCE_EMAIL, PASSWORD)
        smtp.sendmail(SOURCE_EMAIL, dest_email, msg.as_string())
        smtp.close()
        return True
    except IOError:
        return False


def generate_RSA(pridir, pubdir):
    key = RSA.generate(2048)
    with open(pridir, 'wb') as content_file:
        content_file.write(key.exportKey('PEM'))
    print("Private key written to home directory " + pridir)
    with open(pubdir, 'wb') as content_file:
        # Ugly hack to introduce pycrypto v2.7a1
        # Original: .exportKey('OpenSSH')
        eb = long_to_bytes(key.e)
        nb = long_to_bytes(key.n)
        if bord(eb[0]) & 0x80:
            eb = bchr(0x00) + eb
        if bord(nb[0]) & 0x80:
            nb = bchr(0x00) + nb
        keyparts = [b('ssh-rsa'), eb, nb]
        keystring = b('').join(
            [struct.pack(">I", len(kp)) + kp for kp in keyparts])
        content_file.write(b('ssh-rsa ') + binascii.b2a_base64(keystring)[:-1])
    print("Public key written to home directory " + pubdir)
    return sha1(key.exportKey('PEM')).hexdigest()


def urlsafe_b64_short_encode(value):
    return base64.urlsafe_b64encode(value.encode("UTF-8"))\
        .decode("UTF-8").replace('=', '')


def urlsafe_b64_short_decode(text):
    value = text
    value += '=' * ((4 - len(value)) % 4)
    return base64.urlsafe_b64decode(value)


def int2base(num, base=36, numerals="0123456789abcdefghijklmnopqrstuvwxyz"):
    if num == 0:
        return "0"

    if num < 0:
        return '-' + int2base((-1) * num, base, numerals)

    if not 2 <= base <= len(numerals):
        raise ValueError('Base must be between 2-%d' % len(numerals))

    left_digits = num // base
    if left_digits == 0:
        return numerals[num % base]
    else:
        return int2base(left_digits, base, numerals) + numerals[num % base]


class AESCipher:
    """A reusable wrapper of PyCrypto's AES cipher, i.e. resets every time."""
    """ BY Teba 2015 """

    def __init__(self, password, iv):
        self.password = password
        self.iv = iv
        self.cipher = AES.new(self.password, AES.MODE_CFB, self.iv)

    def encrypt(self, data):
        enc = self.cipher.encrypt(data)
        self.cipher = AES.new(self.password, AES.MODE_CFB, self.iv)
        return enc

    def decrypt(self, data):
        dec = self.cipher.decrypt(data)
        self.cipher = AES.new(self.password, AES.MODE_CFB, self.iv)
        return dec


class certloader:

    def __init__(self, cert_data):
        self.cert_data = cert_data

    # TODO: need to support more formats
    # Return RSA key files
    def importKey(self):
        try:
            return RSA.importKey(self.cert_data)
        except Exception as err:
            print ("Fatal error while loading certificate.")
            print (err)
            quit()

    def getSHA1(self):
        try:
            return sha1(self.cert_data.encode("UTF-8")).hexdigest()
        except Exception as err:
            print ("Cannot get SHA1 of the certificate.")
            print (err)
            quit()


def get_ip(debug_ip=None):  # TODO: Get local network interfaces ip
    logging.info("Getting public IP address")
    if debug_ip:
        ip = debug_ip
    else:
        try:
            os.environ['NO_PROXY'] = 'api.ipify.org'
            ip = get('https://api.ipify.org').text
        except Exception as err:
            logging.error(err)
            logging.warning("Error getting address. Using 127.0.0.1 instead.")
            ip = "127.0.0.1"
    logging.info("IP address to be sent is " + ip)
    return struct.unpack("!L", socket.inet_aton(ip))[0]


def get_ip_str():
    logging.info("Getting public IP address")
    try:
        ip = get('https://api.ipify.org').text
        logging.info("IP address to be sent is " + ip)
        return ip
    except Exception as err:
        print(
            "Error occurred in getting address. Using default 127.0.0.1 in testing environment.")
        print(err)
        return "127.0.0.1"


def get_timestamp():
    """Get the current time in milliseconds, in hexagon."""
    return hex(int(time() * 1000)).rstrip("L").lstrip("0x")


def parse_timestamp(timestamp):
    """Convert hexagon timestamp to integer (time in milliseconds)."""
    return int(timestamp, 16)


def weighted_choice(l, f_weight):
    """Weighted random choice with the given weight function."""
    sum_weight = 0
    breakpoints = []
    for item in l:
        sum_weight += f_weight(item)
        breakpoints.append(sum_weight)
    r = random.random() * sum_weight
    i = bisect.bisect(breakpoints, r)
    return l[i]


def ip6_to_integer(ip6):
    ip6 = socket.inet_pton(socket.AF_INET6, ip6)
    a, b = struct.unpack(">QQ", ip6)
    return (a << 64) | b
