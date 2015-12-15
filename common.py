from Crypto.Cipher import AES
from requests import get
import socket
import struct
import logging
from hashlib import sha1

logging.getLogger("requests").setLevel(logging.DEBUG)

try:
    from Crypto.PublicKey import RSA
except Exception as e:
    print("Library Crypto (pycrypto) is not installed. Fatal error.")
    quit()
# TODO:Need to switch to PKCS for better security

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
    if debug_ip:
        ip = debug_ip
    else:
        try:
            ip = get('https://api.ipify.org').text
        except Exception as err:
            logging.error(err)
            logging.warning("Error getting address. Using 127.0.0.1 instead.")
            ip = "127.0.0.1"
    return struct.unpack("!L", socket.inet_aton(ip))[0]

def get_ip_str():
    try:
        ip = get('https://api.ipify.org').text
        return ip
    except Exception as err:
        print("Error occurred in getting address. Using default 127.0.0.1 in testing environment.")
        print(err)
        return "127.0.0.1"
