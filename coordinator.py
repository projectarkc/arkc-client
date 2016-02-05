import threading
import logging
import os
import sys
import random
import string
import binascii
import hashlib
import dnslib
import base64
import atexit
import struct
import socket
import miniupnpc
from time import sleep
from string import ascii_letters

from common import weighted_choice, get_ip, ip6_to_integer, urlsafe_b64_short_encode, int2base

import pyotp

CLOSECHAR = chr(4) * 5

rng = random.SystemRandom()


class Coordinate(object):

    '''Request connections and deal with part of authentication'''

    def __init__(self, ctl_domain, clientpri, clientpri_sha1, serverpub,
                 clientpub_sha1, req_num, remote_host, remote_port, dns_servers,
                 debug_ip, swapcount, ptexec, obfs_level, ipv6, not_upnp):
        self.serverpub = serverpub
        self.clientpri = clientpri
        self.clientpri_sha1 = clientpri_sha1
        self.clientpub_sha1 = clientpub_sha1
        self.req_num = req_num
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
        self.ptexec = ptexec
        self.obfs_level = obfs_level
        self.clientreceivers = {}
        self.ready = None

        # serverreceivers
        self.recvs = [None] * self.req_num
        # each dict maps client connection id to the max index received
        # by the corresponding serverreceiver
        self.max_recved_idx = [{}] * self.req_num

        self.main_pw = (''.join(rng.choice(ascii_letters) for _ in range(16)))\
            .encode('ASCII')
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.setDaemon(True)

        # Try to map ports via UPnP

        if not not_upnp:
            try:
                u = miniupnpc.UPnP()
                u.discoverdelay = 200
                logging.info("Scanning for UPnP devices")
                if u.discover() > 0:
                    logging.info("Device discovered")
                    u.selectigd()
                    if self.ipv6 == "" and self.ip != struct.unpack("!I", socket.inet_aton(u.externalipaddress()))[0]:
                        logging.warning(
                            "Mismatched external address, more than one layers of NAT? UPnP may not work.")
                    r = u.getspecificportmapping(remote_port, 'TCP')
                    if r is None:
                        b = u.addportmapping(remote_port, 'TCP', u.lanaddr,
                                             remote_port, 'ArkC Client port %u' % remote_port, '')
                        if b:
                            logging.info("Port mapping succeed")
                            atexit.register(self.exit_handler, upnp_obj=u)
                    elif r[0] == u.lanaddr and r[1] == remote_port:
                        logging.info("Port mapping already existed.")
                    else:
                        logging.error("Remote port occupied in UPnP mapping")
                    # TODO: implement the following function
                    #    eport = eport + 1
                    #    logging.warning("Original remote port used, switched to " + str(eport))
                    #    r = u.getspecificportmapping(eport, 'TCP')
                else:
                    logging.error("No UPnP devices discovered")
            except Exception:
                logging.error("Error arose when initializing UPnP")

        # obfs4 = level 1 and 2, meek (GAE) = level 3
        if 1 <= self.obfs_level <= 2:
            self.certs_send = None
            self.certs_random = ''.join(rng.choice(ascii_letters)
                                        for _ in range(40))
            self.certcheck = threading.Event()
            self.certcheck.clear()
            pt = threading.Thread(target=self.ptinit)
            pt.setDaemon(True)
            pt.start()
            self.certcheck.wait(1000)
        elif self.obfs_level == 3:
            pt = threading.Thread(target=self.meekinit)
            pt.setDaemon(True)
            pt.start()

        req.start()

    def exit_handler(self, upnp_obj):
        # Clean up UPnP
        try:
            upnp_obj.deleteportmapping(self.remote_port, 'TCP')
        except Exception:
            pass

    def ptinit(self):
        # Initialize obfs4 TODO: problem may exist
        path = os.path.split(os.path.realpath(sys.argv[0]))[0]
        with open(path + os.sep + "ptclient.py") as f:
            code = compile(f.read(), "ptclient.py", 'exec')
            globals = {
                "SERVER_string": self.remote_host + ":" + str(self.remote_port),
                "CERT_STR": self.certs_random,
                "ptexec": self.ptexec + " -logLevel=ERROR",
                "INITIATOR": self,
                "LOCK": self.certcheck,
                "IAT": self.obfs_level
            }
            exec(code, globals)
        # Index of the resolver currently in use, move forward on failure
        self.resolv_cursor = 0

    def meekinit(self):
        # Initialize MEEK
        if self.remote_host == "":
            self.remote_host = "0.0.0.0"
        path = os.path.split(os.path.realpath(sys.argv[0]))[0]
        with open(path + os.sep + "meekclient.py") as f:
            code = compile(f.read(), "meekclient.py", 'exec')
            globals = {
                "SERVER_string": self.remote_host + ":" + str(self.remote_port),
                "ptexec": self.ptexec + " --disable-tls"
            }
            exec(code, globals)
        # Index of the resolver currently in use, move forward on failure
        self.resolv_cursor = 0

    def newconn(self, recv):
        # Called when receive new connections
        self.recvs[recv.i] = recv
        if self.ready is None:
            self.ready = recv
            recv.preferred = True
        self.refreshconn()
        if self.recvs.count(None) <= 2:
            self.check.clear()
        logging.info("Running socket %d" %
                     (self.req_num - self.recvs.count(None)))

    def closeconn(self, conn):
        # Called when a connection is closed
        if self.ready is not None:
            if self.ready.closing:
                if not all(_ is None for _ in self.recvs):
                    self.ready = [_ for _ in self.recvs if _ is not None][0]
                    self.ready.preferred = True
                    self.refreshconn()
                else:
                    self.ready = None
        try:
            self.recvs[conn.i] = None
        except ValueError:
            pass
        if any(_ is None for _ in self.recvs):
            self.check.set()
        logging.info("Running socket %d" %
                     (self.req_num - self.recvs.count(None)))

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
            sleep(0.5)  # TODO: use asyncio

    def generatereq(self):
        """
        Generate strings for authentication.

        Message format:
            (
                req_num_connection_number (HEX, 2 bytes) +
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
        number_in_hex = "%02X" % min((self.req_num), 255)
        msg[0] += number_in_hex
        msg[0] += "%04X" % self.remote_port
        msg[0] += self.clientpub_sha1
        if self.ipv6 == "":
            myip = int2base(self.ip)
        else:
            myip = int2base(
                int(binascii.hexlify(socket.inet_pton(socket.AF_INET6, self.ipv6)), 16)) + "G"
        salt = binascii.hexlify(os.urandom(16)).decode("ASCII")
        h = hashlib.sha256()
        h.update(
            (self.clientpri_sha1 + myip + salt + number_in_hex).encode('utf-8'))
        msg.append(pyotp.TOTP(bytes(h.hexdigest(), "UTF-8")).now())
        msg.append(binascii.hexlify(self.main_pw).decode("ASCII"))
        msg.append(myip)
        msg.append(salt)
        if 1 <= self.obfs_level <= 2:
            certs_byte = urlsafe_b64_short_encode(self.certs_send)
            msg.extend([certs_byte[:50], certs_byte[50:]])
        elif self.obfs_level == 3:
            msg.append(
                ''.join([random.choice(ascii_letters) for _ in range(5)]))
        return '.'.join(msg)

    def issufficient(self):
        return all(_ is not None for _ in self.recvs)

    def refreshconn(self):
        # TODO: better algorithm
        f = lambda r: 1.0 / (1 + r.latency ** 2)
        recvs_avail = list(filter(lambda _: _ is not None, self.recvs))
        next_conn = weighted_choice(recvs_avail, f)
        next_conn.latency += 100  # Avoid repetition
        self.ready.preferred = False
        self.ready = next_conn
        next_conn.preferred = True

    def register(self, clirecv):
        cli_id = None
        if all(_ is None for _ in self.recvs):
            return None
        while (cli_id is None) or (cli_id in self.clientreceivers) or (cli_id == "00"):
            a = list(string.ascii_letters)
            random.shuffle(a)
            cli_id = ''.join(a[:2])
        self.clientreceivers[cli_id] = clirecv
        return cli_id

    def remove(self, cli_id):
        try:
            if any(_ is not None for _ in self.recvs):
                self.ready.id_write(cli_id, CLOSECHAR, '000010')
            self.clientreceivers.pop(cli_id)
        except KeyError:
            pass

    # def server_check(self, server_id_list):
    #    '''check ready to use connections'''
    #    for conn in list(filter(lambda _: _ is not None, self.recvs)):
    #        if conn.idchar not in server_id_list:
    #            self.recvs[conn.i] = None
    #            conn.close()
    #    self.refreshconn()
    #    if len(list(filter(lambda _: _ is not None, self.recvs))) < self.req_num:
    #        self.check.set()

    def received_confirm(self, cli_id, index):
        '''send confirmation'''
        # TODO: remove this method
        # Why does server not respond after removing this?
        # self.ready.id_write(cli_id, str(index), '000030')
        self.ready.id_write(cli_id, 'fuck', '000030')
