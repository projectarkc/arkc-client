import socket
import asyncore
import logging
import time
import threading


class punching_server(asyncore.dispatcher):
    # TODO: wrong structure, two dispatcher at different level!
    # TODO: disconnect after some time

    def __init__(self, ctl):
        self.ctl = ctl
        # A client-server matching with client's address as key and server's
        # address as value
        self.client_matching = {}
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind(("127.0.0.1", ctl.punching_server_port))
        self.listen(6)

        # TODO: write buffer and read buffer!
        # Read asyncore docs! socket recv and send here can be incomplete

    def handle_accept(self):
        conn, self.cli_addr = self.accept()
        data = conn.recv(512)
        self.source = self.match_client(data)
        while 1:
            if self.diy_writable():
                break
            time.sleep(1)
        self.handle_write()

    def match_client(self, data):
        # TODO: recieve authentication strings from client and server, then
        # match them in client_matching, at last return 0 if
        pass
        # its from client or 1 if its from server

    def handle_write(self):
        if self.source:
            for cli, ser in self.client_matching.items():
                if ser == self.cli_addr:
                    send_addr = str(cli[0]) + ' ' + str(cli[1])
                    self.client_matching.pop(cli)
                    break
            self.send(send_addr)
        else:
            send_addr = self.client_matching[self.cli_addr]
            self.send(str(send_addr[0] + ' ' + str(send_addr[1])))

    def writable(self):
        return False

    def diy_writable(self):
        if self.source:
            return (self.cli_addr in self.client_matching.values())
        else:
            return (self.cli_addr in self.client_matching.keys())


class tcp_punching_connect(asyncore.dispatcher):

    def __init__(self, addr, binding_port, ctl):
        asyncore.dispatcher.__init__(self)
        self.remote_addr = addr
        self.port = binding_port
        self.ctl = ctl
        self.finished = False
        self.wbuffer = self.auth_string()
        self.rbuffer = ""
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("127.0.0.1", self.port))
        self.connect(self.remote_addr)

    def readable(self):
        return not(self.finished)

    def handle_connect(self):
        pass

    def writable(self):
        return (len(self.wbuffer) > 0)

    def handle_write(self):
        sent = self.send(self.wbuffer)
        self.wbuffer = self.buffer[sent:]

    def auth_string(self):
        pass

    def handle_read(self):
        self.rbuffer += self.recv(512)
        if ('\n' in self.rbuffer):
            data = self.rbuffer.split(" ")
            if len(data) != 2:
                self.close()  # TODO: return failure
        # TODO: recv may not get complete message back!
        addr = (data[0], int(data[1]))
        self.ctl.traversal_status = 1
        self.p = threading.Thread(target=tcp_punching_send(addr, self.port))
        self.p.start()
        self.finished = True


class tcp_punching_send(threading.Thread):

    def __init__(self, addr, port):
        self._stopevent = threading.Event()
        self._stopevent.set()
        self.addr = addr
        self.port = port
        threading.Thread.__init__(self)

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", self.port))
        while 1:
            self._stopevent.wait()
            try:
                s.connect(self.addr)
            except Exception as err:
                pass

    def join(self, timeout=None):
        self._stopevent.clear()
        threading.Thread.join(self, timeout)
