import socket
import asyncore

from Crypto.Cipher import AES

#Need to switch to asyncio

SPLITCHAR = chr(30)

class servercontrol(asyncore.dispatcher):

    def __init__(self, serverip, serverport, ctl, backlog=5):
        self.ctl = ctl
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((serverip, serverport))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        print('Serv_recv_Accept from %s' % str(addr))
        serverreceiver(conn, self.ctl)
        
    def getrecv(self):
        return self.ctl.offerconn()
        
class serverreceiver(asyncore.dispatcher):

    def __init__(self, conn, ctl):
        self.ctl = ctl
        asyncore.dispatcher.__init__(self, conn)
        self.from_remote_buffer = b''
        self.from_remote_buffer_raw = b''
        self.to_remote_buffer = b''
        self.cipher = None
        self.ctl.newconn(self)

    def handle_connect(self):
        pass

    def handle_read(self):
        read = b''
        if self.cipher == None:
            try:
                read += self.recv(768)
                if len(read) >= 768:
                    read = read[:768]
                    blank = read[:512]
                    if not self.ctl.remotepub.verify(bytes(self.ctl.str, "UTF-8"), (int(blank, 16), None)):
                        print("Authentication failed, socket closing")
                        self.ctl.closeconn()
                        self.close()
                    else:
                        self.cipher = AES.new(self.ctl.localcert.decrypt(read[-256:]), AES.MODE_CFB, bytes(self.ctl.str, "UTF-8"))
            except Exception as err:
                print("Authentication failed, socket closing")
                self.ctl.closeconn()
                self.close()
        else:
            self.from_remote_buffer_raw += self.recv(8192)
            strsplit = self.from_remote_buffer_raw.decode("UTF-8").split(SPLITCHAR)
            for Index in range(len(strsplit)):
                if Index < len(strsplit):
                    decryptedtext = self.cipher.decrypt(bytes(strsplit(Index),"UTF-8"))
                    self.from_remote_buffer += decryptedtext
                    read += len(decryptedtext)
                else:
                    self.from_remote_buffer_raw = bytes(strsplit(Index), "UTF-8")
            print('%04i from server' % read)

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        if len(self.to_remote_buffer)<=4096:
            sent = len(self.to_remote_buffer)
            self.send(self.cipher.encrypt(self.to_remote_buffer) + bytes(SPLITCHAR, "UTF-8"))
        else:
            self.send(self.cipher.encrypt(self.to_remote_buffer[:4096]) + bytes(SPLITCHAR, "UTF-8"))
            sent = 4096
        print('%04i to server' % sent)
        self.to_remote_buffer = self.to_remote_buffer[sent:]

    def handle_close(self):
        self.ctl.closeconn()
        self.close()
