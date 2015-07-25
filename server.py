import socket
import asyncore

from Crypto.Cipher import AES

#Need to switch to asyncio

SPLITCHAR = chr(30) * 5

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
        self.cipherinstance = None
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
                        self.cipherinstance = self.cipher
            except Exception as err:
                print("Authentication failed, socket closing")
                self.ctl.closeconn()
                self.close()
        else:
            read_count = 0
            self.from_remote_buffer_raw += self.recv(8192)
            bytessplit = self.from_remote_buffer_raw.split(bytes(SPLITCHAR, "UTF-8"))
            #TODO: Use Async
            for Index in range(len(bytessplit)):
                if Index < len(bytessplit) -1:
                    decryptedtext = self.cipherinstance.decrypt(bytessplit[Index])
                    self.cipherinstance = self.cipher
                    self.from_remote_buffer += decryptedtext
                    read_count += len(decryptedtext)
                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            print('%04i from server' % read_count)

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        if self.cipherinstance is not None:
            if len(self.to_remote_buffer)<=4096:
                sent = len(self.to_remote_buffer)
                self.send(self.cipherinstance.encrypt(self.to_remote_buffer) + bytes(SPLITCHAR, "UTF-8"))
            else:
                self.send(self.cipherinstance.encrypt(self.to_remote_buffer[:4096]) + bytes(SPLITCHAR, "UTF-8"))
                sent = 4096
            self.cipherinstance = self.cipher
            print('%04i to server' % sent)
            self.to_remote_buffer = self.to_remote_buffer[sent:]
        else:
            self.handle_read()

    def handle_close(self):
        self.ctl.closeconn()
        self.close()
