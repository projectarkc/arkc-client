#!/usr/bin/env python3
# coding:utf-8

import socket
import logging
import asyncore

# Need to switch to asyncio


class ClientControl(asyncore.dispatcher):

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
        ClientReceiver(conn, self.control)


class ClientReceiver(asyncore.dispatcher):

    '''represent each connection with the client (e.g. browser)'''

    def __init__(self, conn, control):
        self.control = control
        asyncore.dispatcher.__init__(self, conn)
        self.idchar = self.control.register(self)
        if self.idchar is None:
            self.close()
        self.from_remote_buffer_dict = {}
        self.from_remote_buffer_index = 100000
        self.to_remote_buffer = b''
        self.to_remote_buffer_index = 100000
        self.retransmit_lock = False

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        logging.debug('%04i from client ' % len(read) + self.idchar)
        self.to_remote_buffer += read

    def writable(self):
        return self.from_remote_buffer_index in self.from_remote_buffer_dict

    def handle_write(self):
        i = 0
        self.retransmit_lock = False
        while self.writable() and i <= 4:
            tosend = self.from_remote_buffer_dict.pop(
                self.from_remote_buffer_index)
            while len(tosend) > 0:
                sent = self.send(tosend)
                logging.debug('%04i to client ' % sent + self.idchar)
                tosend = tosend[sent:]
            i += 1
        if self.next_from_remote_buffer() % self.control.req_num == 0:
            self.control.received_confirm(
                self.idchar, self.from_remote_buffer_index)

    def handle_close(self):
        self.control.remove(self.idchar)
        self.close()

    def retransmission_check(self):
        if not self.writable() and self.retransmit_lock and \
            all(_ in self.from_remote_buffer_dict
                for _ in range(self.from_remote_buffer_index + 1,
                               self.from_remote_buffer_index + self.control.req_num + 1)):
            self.control.retransmit(
                self.idchar, self.from_remote_buffer_index)
            self.retransmit_lock = True

    def next_to_remote_buffer(self):
        self.to_remote_buffer_index += 1
        if self.to_remote_buffer_index == 1000000:
            # TODO: raise exception or close connection
            self.to_remote_buffer_index = 100000

    def next_from_remote_buffer(self):
        # Clean up
        if self.from_remote_buffer_index % 20 == 0:
            for i in range(self.from_remote_buffer_index - 20,
                           self.from_remote_buffer_index):
                if i in self.from_remote_buffer_dict:
                    self.from_remote_buffer_dict.pop(i)

        self.from_remote_buffer_index += 1
        if self.from_remote_buffer_index == 1000000:
            # TODO: raise exception or close connection
            self.from_remote_buffer_index = 100000
        return self.from_remote_buffer_index
