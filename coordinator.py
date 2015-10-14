import socket
import threading
import logging
import os
import random
import string
from dnslib.dns import DNSRecord,DNSHeader,DNSQuestion,QTYPE
from dnslib.digparser import DigParser
from time import sleep

CLOSECHAR = chr(4) * 5

class coordinate(object):

    '''Used to request connections and deal with part of authentication'''
    
    def __init__(self, ctl_domain, localcert, remotecert, localpub, required, remote_port):
        self.remotepub = remotecert
        self.localcert = localcert
        self.authdata = localpub
        self.required = required
        self.remote_port = remote_port
        self.ctl_domain = ctl_domain
        self.clientreceivers = {}
        self.ready = None
                
        self.recvs = []  # For serverreceivers
        self.str = os.urandom(16)
        #self.udpsock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.setDaemon(True)
        req.start()

    def newconn(self, recv):
        # Called when receive new connections
        self.recvs.append(recv)
        if self.ready is None:
            self.ready = recv
            recv.preferred = True
        self.refreshconn()
        if len(self.recvs) + 2 >= self.required:
            self.check.clear()
        logging.info("Running socket %d" % len(self.recvs))
            
    def closeconn(self, conn):
        # Called when a connection is closed
        if self.ready is not None:
            if self.ready.closing:
                if len(self.recvs) > 0:
                    self.ready = self.recvs[0]
                    self.recvs[0].preferred = True
                    self.refreshconn()
                else:
                    self.ready = None
        self.recvs.remove(conn)
        if len(self.recvs) < self.required:
            self.check.set()
        logging.info("Running socket %d" % len(self.recvs))

    #def reqconn(self):
    #    # Sending UDP requests
    #    while True:
    #        self.check.wait()  # Start the request when the client needs connections
    #        requestdata = self.generatereq()
    #        #print(len(requestdata))    
    #        self.udpsock.sendto(requestdata, self.addr)
    #        sleep(0.1)
            
    def reqconn(self):
        # Sending UDP requests
        while True:
            self.check.wait()  # Start the request when the client needs connections
            requestdata = self.generatereq()
            #print(len(requestdata))    
            socket.gethostbyname(requestdata + '.' + self.ctl_domain)
            
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
        salt = os.urandom(16)
        required_hex = "%X" % min((self.required), 255)
        sign_hex = '%X' % self.localcert.sign(salt, None)[0]
        remote_port_hex = '%X' % self.remote_port
        if len(required_hex) == 1:
            required_hex = '0' + required_hex
        if len(sign_hex) == 510:
            sign_hex = '0' + sign_hex
        remote_port_hex = '0' * (4 - len(remote_port_hex)) + remote_port_hex
        return  salt + \
                bytes(required_hex, "UTF-8") + \
                bytes(remote_port_hex, "UTF-8") + \
                bytes(self.authdata, "UTF-8") + \
                bytes(sign_hex, "UTF-8") + \
                self.remotepub.encrypt(self.str, None)[0]  # TODO: Replay attack?

    def issufficient(self):
        return len(self.recvs) >= self.required
    
    #TODO: Optimize and make it smoother
    def refreshconn(self):
        next_conn = random.choice(self.recvs)
        self.ready.preferred = False
        self.ready = next_conn
        next_conn.preferred = True
    
    def register(self, clirecv):
        cli_id = None
        if len(self.recvs) == 0:
            return None
        while (cli_id is None) or (cli_id in self.clientreceivers):
            a = list(string.ascii_letters)
            random.shuffle(a)
            cli_id = ''.join(a[:2])
        self.clientreceivers[cli_id] = clirecv
        return cli_id
    
    def remove(self, cli_id):
        if len(self.recvs) >0:
            self.ready.id_write(cli_id, CLOSECHAR)
        del self.clientreceivers[cli_id]