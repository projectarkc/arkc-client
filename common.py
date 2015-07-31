from Crypto.Cipher import AES

from hashlib import sha1

try:
    from Crypto.PublicKey import RSA
except Exception as e:
    print("Library Crypto (pycrypto) is not installed. Fatal error.")
    quit()
#TODO:Need to switch to PKCS for better security

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
    
    ''' Used to load certfiles'''
    
    def __init__(self, certfile):
        self.certfile = certfile
    
    #TODO: need to support more formats
    #Return RSA key files
    def importKey(self):
        try:
            data = self.certfile.read()
            return RSA.importKey(data)
        except Exception as err:
            print ("Fatal error while loading certificate.")
            print (err)
            quit()
            
    #Note: This SHA1 is different from the SHA1 of the Der version
    #Return HEX version of SHA1        
    def getSHA1(self):
        try:
            data = self.certfile.read()
            #TODO: should use compatible SHA1 value
            return sha1(data.encode("UTF-8")).hexdigest()
        except Exception as err:
            print ("Cannot get SHA1 of the certificate.")
            print (err)
            quit()