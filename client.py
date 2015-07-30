import socket
import asyncore

#Need to switch to asyncio

class clientcontrol(asyncore.dispatcher):

    def __init__(self, scontrol, clientip, clientport, backlog=5):
        self.scontrol = scontrol
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((clientip, clientport))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        print('Client_recv_Accept from %s' % str(addr))
        clientreceiver(conn, self.scontrol)

class clientreceiver(asyncore.dispatcher):

    def __init__(self, conn, scontrol):
        asyncore.dispatcher.__init__(self, conn)
        self.sreceiver = scontrol.getrecv()
        if self.sreceiver == None:
            print("No available socket from server. Closing this socket.")
            self.close()
        else:
            self.idchar = self.sreceiver.add_clientreceiver(self)
        #self.from_remote_buffer = b''
        #self.to_remote_buffer = b''

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        print('%04i from client' % len(read))
        self.sreceiver.to_remote_buffers[self.idchar] += read

    def writable(self):
        return (len(self.sreceiver.from_remote_buffers[self.idchar]) > 0 or (not self.sreceiver.connected))

    def handle_write(self):
        if not self.sreceiver.connected:
            self.close()
            return
        sent = self.send(self.sreceiver.from_remote_buffers[self.idchar])
        print('%04i to client' % sent)
        self.sreceiver.from_remote_buffers[self.idchar] = self.sreceiver.from_remote_buffers[self.idchar][sent:]

    def handle_close(self):
        self.sreceiver.remove_clientreceiver(self.idchar)
        self.close()
