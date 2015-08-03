import socket
import logging
import asyncore

# Need to switch to asyncio

class clientcontrol(asyncore.dispatcher):
    
    """ a standard client service dispatcher """

    def __init__(self, control, clientip, clientport, backlog=5):
        self.control = control
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((clientip, clientport))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        logging.info('Client_recv_Accept from %s' % str(addr))
        clientreceiver(conn, self.control)

class clientreceiver(asyncore.dispatcher):

    def __init__(self, conn, control):
        self.control = control
        asyncore.dispatcher.__init__(self, conn)
        self.idchar = self.control.register(self)
        if self.idchar is None:
            self.close()
        self.from_remote_buffer = b''
        self.to_remote_buffer = b''

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        logging.info('%04i from client' % len(read))
        self.to_remote_buffer += read

    def writable(self):
        return len(self.from_remote_buffer) > 0

    def handle_write(self):
        sent = self.send(self.from_remote_buffer)
        logging.info('%04i to client' % sent)
        self.from_remote_buffer = self.from_remote_buffer[sent:]

    def handle_close(self):
        self.control.remove(self.idchar)
        self.close()
