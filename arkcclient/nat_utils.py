import socket
import asyncore
import logging
import time
import threading


class punching_server(asyncore.dispatcher):
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
        self.remote_addr = addr
        self.port = binding_port
        self.ctl = ctl
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind(("127.0.0.1", self.port))
        self.connect(self.remote_addr)

    def handle_connect(self):
        str = self.auth_string
        self.send(str)
        data = self.recv(512).split(' ')
        addr = (data[0], int(data[1]))
        self.ctl.traversal_status = 1
        threading.Thread(target=tcp_punching_send(addr, self.port)).start()

    def auth_string(self):
        pass


def tcp_punching_send(addr, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port))
    while 1:
        pass  # TODO: keep sending packages to Arkc server
