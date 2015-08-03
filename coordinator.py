import socket
import threading
import logging
import os
from time import sleep

class coordinate(object):

    '''Used to request connections and deal with part of authentication'''
    
    def __init__(self, ctlip, ctlport_remote, localcert, remotecert, localpub, required, remote_port):
        self.count = 0
        self.available = 0
        self.remotepub = remotecert
        self.localcert = localcert
        self.authdata = localpub
        self.required = required
        
        self.recvs = []  # For serverreceivers
        # TODO: make the following string more random
        self.str = ''.join(map(lambda xx:(hex(ord(xx))[2:]),os.urandom(16)))
        self.udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addr = (ctlip, ctlport_remote)
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.start()

    def newconn(self, recv):
        # Called when receive new connections
        self.available += 1
        self.count += 1
        self.recvs.append(recv)
        if self.available + 2 >= self.required:
            self.check.clear()
        logging.info("Available socket %d" % self.available)
            
    def closeconn(self):
        # Called when a connection is closed
        self.count -= 1
        self.available -= 1
        if not self.issufficient():
            self.check.set()
        logging.info("Available socket %d" % self.available)

    def reqconn(self):
        # Sending UDP requests
        while True:
            self.check.wait()  # Start the request when the client needs connections
            requestdata = self.generatereq()    
            self.udpsock.sendto(requestdata, self.addr)
            sleep(0.1)
            
    def generatereq(self):
        # Generate strings for authentication
        """
            The encrypted message should be
            salt +
            required_connection_number (HEX, 2 bytes) +
            used_remote_listening_port (HEX, 4 bytes) +
            client_sign(salt) +
            server_pub(main_pw)
            Total length is 16 + 2 + 4 + 40 + 512 + 256 = 830 bytes
        """
        salt = ''.join(map(lambda xx:(hex(ord(xx))[2:]),os.urandom(16)))
        saltstr = ''.join(salt)
        required_hex = "%X" % min((self.required - self.available + self.count), 255)
        sign_hex = '%X' % self.localcert.sign(bytes(saltstr, "UTF-8"), None)[0]
        remote_port_hex = '%X' % self.remote_port
        if len(required_hex) == 1:
            required_hex = '0' + required_hex
        if len(sign_hex) == 510:
            sign_hex = '0' + sign_hex
        remote_port_hex = '0' * (4 - len(remote_port_hex)) + remote_port_hex
        return  (bytes(saltstr, "UTF-8")
                + bytes(required_hex, "UTF-8")
                + bytes(remote_port_hex, "UTF-8")
                + bytes(self.authdata, "UTF-8")
                + bytes(sign_hex, "UTF-8")
                + self.remotepub.encrypt(bytes(self.str, "UTF-8"), None)[0])  # TODO: Replay attack?

    def issufficient(self):
        return self.available >= self.required

    def offerconn(self):
        # Called to request connections in a standard model
        if self.available <= 0:
            sleep(0.5)
            if self.available <= 0:
                return None
        return self.pickconn()

    def pickconn(self):  # Ugly Selection with low optimization
        # Decide which conn is the best to give out
        minimum = None
        for serverconn in self.recvs:
            if not serverconn.full:
                minimum = serverconn
                break
        if minimum is None:
            return None
        for serverconn in self.recvs:
            if len(serverconn.clientreceivers) < len(minimum.clientreceivers) and not serverconn.full:
                minimum = serverconn
        return minimum
    
    def checkavailable(self, ctl_id):
        for serverconn in self.recvs:
            if ctl_id in serverconn.clientreceivers:
                return False
        return True
