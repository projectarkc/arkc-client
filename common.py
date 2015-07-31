from Crypto.Cipher import AES

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