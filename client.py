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
        self.from_remote_buffer = {}
        self.from_remote_buffer_index = 100
        self.to_remote_buffer = b''
        self.to_remote_buffer_index = 100
        self.retrans_position = None

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        logging.debug('%04i from client ' % len(read) + self.idchar)
        self.to_remote_buffer += read

    def writable(self):
        if self.from_remote_buffer_index in self.from_remote_buffer:
            return True
        # default continual length = 7
        elif self.from_remote_buffer_index + 7 in self.from_remote_buffer \
                and self.retrans_position:
            # Retransmission
            tosend = ''
            range_check = range(self.from_remote_buffer_index,
                                7 + self.from_remote_buffer_index)
            for i in range_check:
                if i - self.from_remote_buffer_index <= 50 and i not in self.from_remote_buffer:
                    tosend += str(i)
            if len(tosend) > 0:
                self.control.retransmit(self.idchar, tosend)
                logging.debug(
                    "Restransmission, lost frame at connection " + self.idchar +
                    ' ' + tosend)
                self.retrans_position = self.from_remote_buffer_index
            return False

    def handle_write(self):
        i = 0
        while self.writable() and i <= 4:
            sent = self.send(
                self.from_remote_buffer.pop(self.from_remote_buffer_index))
            i += 1
        if self.next_from_remote_buffer() % self.control.required == 0:
            self.control.received_confirm(
                self.idchar, self.from_remote_buffer_index)
        logging.debug('%04i to client ' % sent + self.idchar)

    def handle_close(self):
        self.control.remove(self.idchar)
        self.close()

    def next_to_remote_buffer(self):
        self.to_remote_buffer_index += 1
        if self.to_remote_buffer_index == 1000:
            self.to_remote_buffer_index = 100

    def next_from_remote_buffer(self):
        # Reset transmission
        if self.retrans_position is not None:
            if self.from_remote_buffer_index - self.retrans_position == 7:
                self.retrans_position = None
        # Clean up
        if self.from_remote_buffer_index % 20 == 0:
            for i in range(self.from_remote_buffer_index - 20,
                           self.from_remote_buffer_index):
                if i in self.from_remote_buffer:
                    self.from_remote_buffer.pop(i)

        self.from_remote_buffer_index += 1
        if self.from_remote_buffer_index == 1000:
            self.from_remote_buffer_index = 100
        return self.from_remote_buffer_index
