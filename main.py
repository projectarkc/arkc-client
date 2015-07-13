#! /usr/bin/env python3

#Need to switch to asyncio

import socket
import asyncore
import optparse

from time import sleep

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_LOCAL_PORT = 8001

DEFAULT_REMOTE_PORT = 8000

DEFAULT_LOCAL_CONTROL_PORT = 8002
DEFAULT_REMOTE_CONTROL_PORT = 9000

class coordinate(object):

    required = 4
    requestdata = b"0"

    def __init__(self, ctlip, ctlport_remote, ctlport_local):
        self.count = 0
        self.available = 0
        self.recvs = []
        self.udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udpsock.bind(('', ctlport_local))
        self.addr = (ctlip, ctlport_remote)
#TODO how to request available sockets with out obstruction? keep servercontrol initialized?

    def newconn(self, recv):
        self.available += 1
        self.count += 1
        self.recvs.append(recv)
        print("available socket %d" % self.available)
            
    def closeconn(self):
        self.count -=1
        if self.count <0:
            self.count =0
            print("coordinate: minus count error")
        print("available socket %d" % self.available)

    def reqconn(self):
        while self.available < self.required:
            self.udpsock.sendto(self.requestdata,self.addr)
            sleep(0.05)

    def issufficient(self):
        pass
    
    def offerconn(self):
        if self.available <=0:
            self.reqconn()
        self.available -=1
        offer = self.recvs [0]
        self.recvs = self.recvs[1:]
        print("available socket %d" % self.available)
        return offer

class servercontrol(asyncore.dispatcher):

    def __init__(self, serverip, serverport, ctl, backlog=5):
        self.receivernum = 0
        self.ctl = ctl
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((serverip, serverport))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        print('Serv_recv_Accept from %s' % addr)
        self.receivernum += 1
        print('Current Receivers = %d' % self.receivernum)
        self.ctl.newconn(serverreceiver(conn, self))
        
    def getrecv(self):
        return self.ctl.offerconn()
        
    def closeconn(self):
        self.ctl.closeconn()

class serverreceiver(asyncore.dispatcher):

    def __init__(self, conn, serverctl):
        self.serverctl = serverctl
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
#TODO, on this occasion, it needs to close the clientreceiver's socket

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
        print('Client_recv_Accept from %s' % addr)
        clientreceiver(conn, self.scontrol.getrecv())


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
        self.sreceiver.close()
        self.close()

if __name__ == '__main__':
    parser = optparse.OptionParser()
    try:
        parser.add_option('--local-host', dest="local_host", default=DEFAULT_LOCAL_HOST)
        parser.add_option('--local-port',  dest="local_port", type='int', default=DEFAULT_LOCAL_PORT)
        parser.add_option('--remote-host',  dest="remote_host")
        parser.add_option('--remote-port',  dest="remote_port", type='int', default=DEFAULT_REMOTE_PORT)
        parser.add_option('--remote-control-host',  dest="remote_control_host", default="0.0.0.0")
        parser.add_option('--remote-control-port',  dest="remote_control_port", type='int', default=DEFAULT_REMOTE_CONTROL_PORT)
        parser.add_option('--local-control-port', dest="local_control_port", type='int', default=DEFAULT_LOCAL_CONTROL_PORT)
        options, args = parser.parse_args()
        remote_control_host = options.remote_control_host
        if remote_control_host == "0.0.0.0":
            remote_control_host = options.remote_host
    except Exception as e:
        print (e)
    
    try:
        clientcontrol(
            servercontrol(
                options.remote_host,
                options.remote_port,
                coordinate(
                    remote_control_host,
                    options.remote_control_port,
                    options.local_control_port
                    )
                ),
            options.local_host,
            options.local_port
            )
    except Exception as e:
        print (e)
    asyncore.loop()
