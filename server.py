import socket
import asyncore

from Crypto.Cipher import AES

#Need to switch to asyncio

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
        self.to_remote_buffer = b''
        self.cipher = None
        self.ctl.newconn(self)

    def handle_connect(self): #TODO: make sure it is necessarily first to happen
        read = self.recv(4096)
        blank = self.ctl.remotepub.decrypt(read)
        if not blank[16:] == bytes(self.ctl.str, "UTF-8"):
            print("Authentication failed")
            self.close()
        else:
            self.cipher = AES.new(blank[:16], AES.MODE_CFB, blank)

    def handle_read(self):
        read = self.cipher.decrypt(self.recv(4096)) #fragments?
        print('%04i from server' % len(read))
        self.from_remote_buffer += read

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        if len(self.to_remote_buffer)<=4096:
            sent = len(self.to_remote_buffer)
            self.send(self.cipher.encrypt(self.to_remote_buffer))
        else:
            self.send(self.cipher.encrypt(self.to_remote_buffer[:4096])) #complete message for encryption?
            sent = 4096
        print('%04i to server' % sent)
        self.to_remote_buffer = self.to_remote_buffer[sent:]

    def handle_close(self):
        self.close()
