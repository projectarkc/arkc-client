import socket
import asyncore

#Need to switch to asyncio
#Need to use AES

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
        self.ctl.newconn(self)

    def handle_connect(self): #TODO: make sure it is necessarily first to happen
        read = self.recv(4096)
        if not self.ctl.remotepub.decrypt(read) == self.ctl.str:
            print("Authentication failed")
            self.close()

    def handle_read(self):
        read = self.recv(4096)
        print('%04i from server' % len(read))
        self.from_remote_buffer += read

    def writable(self):
        return (len(self.to_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.to_remote_buffer)
        print('%04i to server' % sent)
        self.to_remote_buffer = self.to_remote_buffer[sent:]

    def handle_close(self):
        self.close()