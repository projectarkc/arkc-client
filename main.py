#! /usr/bin/env python3

#Need to switch to asyncio

import socket
import asyncore
import optparse
import threading
import random
import string
from Crypto.PublicKey import RSA
from time import sleep

DEFAULT_LOCAL_HOST = "127.0.0.1"
DEFAULT_LOCAL_PORT = 8001

DEFAULT_REMOTE_PORT = 8000

DEFAULT_LOCAL_CONTROL_PORT = 8002
DEFAULT_REMOTE_CONTROL_PORT = 9000

class coordinate(object):

    required = 4
    authdata = b"0" #authdata needs to be unique for every client certificate

    def __init__(self, ctlip, ctlport_remote, ctlport_local, localcert, remotecert):
        self.count = 0
        self.available = 0
        self.remotepub = remotecert
        self.localcert = localcert
        self.recvs = []
        self.str = ''.join(random.shuffle(list(string.ascii_letters)[:5])) #TODO: should be used for AES in every data transmission
        self.udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udpsock.bind(('', ctlport_local))
        self.addr = (ctlip, ctlport_remote)
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.start()

    def newconn(self, recv):
        self.available += 1
        self.count += 1
        self.recvs.append(recv)
        if self.issufficient():
            self.check.clear()
        print("Available socket %d" % self.available)
            
    def closeconn(self):
        self.count -=1
        if self.count <0:
            self.count =0
            print("coordinate: minus count error")
        if not self.issufficient():
            self.check.set()
        print("Available socket %d" % self.available)

    def reqconn(self):
        while True:
            self.check.wait()
            self.requestdata = self.generatereq()
            self.udpsock.sendto(self.requestdata,self.addr)
            sleep(0.05)
            
    def generatereq(self):
        salt = ''.join(random.shuffle(list(string.ascii_letters)[:5]))
        blank = salt.join(self.authdata)
        blank.join(self.localcert.encrypt(salt.join(self.str), "r"))
        return self.remotepub.encrypt(blank, "r")
    
    def issufficient(self):
        return self.available >= self.required
    
    def offerconn(self):
        if self.available <=0:
            return None
        self.available -=1
        offer = self.recvs [0]
        self.recvs = self.recvs[1:]
        if not self.issufficient():
            self.check.set()
        print("Available socket %d" % self.available)
        return offer

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
            print("Auth failed")
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
        parser.add_option('--remote-host',  dest="remote_host", default = "")
        parser.add_option('--remote-port',  dest="remote_port", type='int', default=DEFAULT_REMOTE_PORT)
        parser.add_option('--remote-control-host',  dest="remote_control_host", default="0.0.0.0")
        parser.add_option('--remote-control-port',  dest="remote_control_port", type='int', default=DEFAULT_REMOTE_CONTROL_PORT)
        parser.add_option('--local-control-port', dest="local_control_port", type='int', default=DEFAULT_LOCAL_CONTROL_PORT)
        parser.add_option('--remote-cert',  dest="remote_cert", default = "")
        parser.add_option('--local-cert',  dest="local_cert", default = "")
        options, args = parser.parse_args()
        if options.remote_host == "":
            print("Fatal error, remote host not specified.")
            quit()
        if options.remote_cert == "":
            print("Fatal error, remote host certificate not specified.")
            quit()
        if options.local_cert == "":
            print("Fatal error, local certificate not specified.")
            quit()
        try:
            remote_cert_file = open(options.remote_cert, "r")
            cert = RSA.importKey(remote_cert_file.read())
            remotecert = cert.publickey()
            remote_cert_file.close()
        except Exception as err:
            print ("Fatal error while loading remote host certificate.")
            print (err)
            quit()
            
        try:
            local_cert_file = open(options.local_cert, "r")
            localcert = RSA.importKey(remote_cert_file.read())
            local_cert_file.close()
            if not localcert.has_private():
                print("Fatal error, no private key included in local certificate.")
        except IOError as err:
            print ("Fatal error while loading local certificate.")
            print (err)
            quit()
        
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
                    options.local_control_port,
                    localcert,
                    remotecert
                    )
                ),
            options.local_host,
            options.local_port
            )
    except Exception as e:
        print (e)
    asyncore.loop()
