import threading
import logging
import os
import sys
import random
import string
import binascii
import hashlib
import base64
import dnslib
import socket

from time import sleep
from string import ascii_letters

from common import weighted_choice, get_ip, ip6_to_integer

import pyotp

CLOSECHAR = chr(4) * 5

rng = random.SystemRandom()


class coordinate(object):

    '''Request connections and deal with part of authentication'''

    def __init__(self, ctl_domain, localcert, localcert_sha1, remotecert,
                 localpub, required, remote_host, remote_port, dns_servers,
                 debug_ip, swapcount, obfs4_exec, obfs_level, ipv6):
        self.remotepub = remotecert
        self.localcert = localcert
        self.localcert_sha1 = localcert_sha1
        self.authdata = localpub
        self.required = required
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.dns_servers = dns_servers
        random.shuffle(self.dns_servers)
        self.dns_count = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.swapcount = swapcount
        self.ctl_domain = ctl_domain
        if ipv6 == "":
            self.ip = get_ip(debug_ip)
        self.ipv6 = ipv6
        self.obfs4_exec = obfs4_exec
        self.obfs_level = obfs_level
        self.clientreceivers = {}
        self.ready = None
        self.recvs = []  # For serverreceivers
        self.str = (''.join(rng.choice(ascii_letters) for _ in range(16)))\
            .encode('ASCII')
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.setDaemon(True)

        # ptproxy enabled
        if self.obfs_level:
            self.certs_send = None
            self.certs_random = ''.join(rng.choice(ascii_letters)
                                        for _ in range(40))
            self.certcheck = threading.Event()
            self.certcheck.clear()
            pt = threading.Thread(target=self.ptinit)
            pt.setDaemon(True)
            pt.start()
            self.certcheck.wait(1000)

        req.start()

    def ptinit(self):
        path = os.path.split(os.path.realpath(sys.argv[0]))[0]
        with open(path + os.sep + "ptclient.py") as f:
            code = compile(f.read(), "ptclient.py", 'exec')
            globals = {
                "SERVER_string": self.remote_host + ":" + str(self.remote_port),
                "CERT_STR": self.certs_random,
                "ptexec": self.obfs4_exec + " -logLevel=ERROR",
                "INITIATOR": self,
                "LOCK": self.certcheck,
                "IAT": self.obfs_level
            }
            exec(code, globals)
        # Index of the resolver currently in use, move forward on failure
        self.resolv_cursor = 0

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
        try:
            self.recvs.remove(conn)
        except ValueError:
            pass
        if len(self.recvs) < self.required:
            self.check.set()
        logging.info("Running socket %d" % len(self.recvs))

    def reqconn(self):
        """Send DNS queries."""
        while True:
            # Start the request when the client needs connections
            self.check.wait()
            requestdata = self.generatereq()
            d = dnslib.DNSRecord.question(requestdata + "." + self.ctl_domain)
            self.sock.sendto(
                d.pack(),
                (
                    self.dns_servers[self.dns_count][0],
                    self.dns_servers[self.dns_count][1]
                )
            )
            self.dns_count += 1
            if self.dns_count == len(self.dns_servers):
                self.dns_count = 0
            sleep(0.1)

    def generatereq(self):
        """
        Generate strings for authentication.

        Message format:
            (
                required_connection_number (HEX, 2 bytes) +
                    used_remote_listening_port (HEX, 4 bytes) +
                    sha1(cert_pub) ,
                pyotp.TOTP(pri_sha1 + ip_in_hex_form + salt),
                main_pw,    # must send in encrypted form to avoid MITM
                ip_in_hex_form,
                salt,
                [cert1,
                cert2   (only when ptproxy is enabled)]
            )
        """
        msg = [""]
        msg[0] += "%02X" % min((self.required), 255)
        msg[0] += "%04X" % self.remote_port
        msg[0] += self.authdata
        if self.ipv6 == "":
            myip = "%X" % self.ip
        else:
            myip = "%X" % ip6_to_integer(self.ipv6) + "G"
        salt = binascii.hexlify(os.urandom(16)).decode("ASCII")
        h = hashlib.sha256()
        h.update((self.localcert_sha1 + myip + salt).encode('utf-8'))
        msg.append(pyotp.TOTP(bytes(h.hexdigest(), "UTF-8")).now())
        msg.append(binascii.hexlify(self.str).decode("ASCII"))
        msg.append(myip)
        msg.append(salt)

        if self.obfs_level:
            certs_byte = base64.b64encode(self.certs_send.encode("ASCII"))\
                .decode("ASCII").replace('=', '')
            msg.extend([certs_byte[:50], certs_byte[50:]])

        return '.'.join(msg)

    def issufficient(self):
        return len(self.recvs) >= self.required

    def refreshconn(self):
        # TODO: better algorithm
        f = lambda r: 1.0 / (1 + r.latency ** 2)
        next_conn = weighted_choice(self.recvs, f)
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
        if len(self.recvs) > 0:
            self.ready.id_write(cli_id, CLOSECHAR)
        self.clientreceivers.pop(cli_id)
