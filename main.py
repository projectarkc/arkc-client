#! /usr/bin/env python3

#Need to switch to asyncio

import socket
import asyncore

class coordinate(object):

    def __init__(self):
        pass

    def newconn(self):
        pass

    def closeconn(self):
        pass

    def reqconn(self):
        pass

    def issufficient(self):
        pass
#to be done

class servercontrol(asyncore.dispatcher):

    def __init__(self, serverip, serverport, ctl, backlog=5):
        self.receivernum = 0
        self.ctl = ctl
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((serverip, serverport))
        self.listen(backlog)
#ctl init

    def handle_accept(self):
        conn, addr = self.accept()
        print('Serv_recv_Accept')
        self.receivernum += 1
        print('Current Receivers = %d' % self.receivernum)
        serverreceiver(conn, self)
#updating ctl

    def getrecv(self):
        pass
#using ctl
    def closeconn(self):
        pass
#using ctl

class serverreceiver(asyncore.dispatcher):

    def __init__(self, conn, serverctl):
        self.serverctl = serverctl
        self.clientip = clientip
        self.clientport = clientport
        asyncore.dispatcher.__init__(self, conn)
        self.from_remote_buffer = b''
        self.to_remote_buffer = b''

    def handle_connect(self):
        pass

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
        self.serverctl.closeconn()
        self.close()


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
        print('Client_recv_Accept')
        clientreceiver(conn, self.scontrol.getrecv)


class clientreceiver(asyncore.dispatcher):

    def __init__(self, conn, sreceiver):
        self.sreceiver = sreceiver
        asyncore.dispatcher.__init__(self, conn)
        self.from_remote_buffer = b''
        self.to_remote_buffer = b''

    def handle_connect(self):
        pass

    def handle_read(self):
        read = self.recv(4096)
        print('%04i from client' % len(read))
        self.sreceiver.to_remote_buffer += read

    def writable(self):
        return (len(self.sreceiver.from_remote_buffer) > 0 or (not self.sreceiver.connected))

    def handle_write(self):
        if not self.sreceiver.connected:
            self.close()
            return
        sent = self.send(self.sreceiver.from_remote_buffer)
        print('%04i to client' % sent)
        self.sreceiver.from_remote_buffer = self.sreceiver.from_remote_buffer[
            sent:]

    def handle_close(self):
        self.close()

if __name__ == '__main__':
    clientcontrol(servercontrol('0.0.0.0', 8000, coordinate()),"0.0.0.0",8001)
    asyncore.loop()
