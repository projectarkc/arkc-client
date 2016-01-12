from Crypto.Cipher import AES
from requests import get
import socket
import struct
import logging
import random
import bisect
import string
import base64
from hashlib import sha1
from time import time

logging.getLogger("requests").setLevel(logging.DEBUG)

try:
    from Crypto.PublicKey import RSA
except Exception as e:
    print("Library Crypto (pycrypto) is not installed. Fatal error.")
    quit()
# TODO:Need to switch to PKCS for better security


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
        return '-' + baseN((-1) * num, base, numerals)

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
