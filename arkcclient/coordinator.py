import threading
import logging
import os
import random
import string
import binascii
import hashlib
import dnslib
import atexit
import struct
import socket
import miniupnpc
from time import sleep
from string import ascii_letters

from common import weighted_choice, get_ip, urlsafe_b64_short_encode, int2base
from meekclient import main as meekexec

from server import ServerControl

from nat_utils import tcp_punching_connect, punching_server
from client import ClientControl

from pyotp.totp import TOTP

CLOSECHAR = chr(4) * 5

rng = random.SystemRandom()


class Coordinate(object):

    '''Request connections and deal with part of authentication'''

    def __init__(self, ctl_domain, clientpri, clientpri_sha1, serverpub,
                 clientpub_sha1, req_num, local_host, local_port, remote_host,
                 remote_port, dns_servers, debug_ip, swapcount, ptexec,
                 obfs_level, ipv6, not_upnp, tcp):
        self.tcp = tcp
        self.req_num = req_num
        self.remote_host = remote_host
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

        # shared properties, used in ServerReceiver
        self.remote_port = remote_port
        self.serverpub = serverpub
        self.clientpri = clientpri
        self.clientpri_sha1 = clientpri_sha1
        self.clientpub_sha1 = clientpub_sha1
        self.clientreceivers_dict = dict()
        self.punching_server_port = 50009
        self.main_pw = (''.join(rng.choice(ascii_letters) for _ in range(16)))\
            .encode('ASCII')
        # each dict maps client connection id to the max index received
        # by the corresponding serverreceiver
        self.serverreceivers_pool = [None] * self.req_num

        # each entry as dict: conn_id -> queue, each queue is (index, data)
        # pairs
        self.server_send_buf_pool = [{}] * self.req_num

        self.server_recv_max_idx = [{}] * self.req_num
        # end of shared properties

        self.ready = None  # used to store the next ServerReceiver to use

        # lock the method to request connections
        self.check = threading.Event()
        self.check.set()
        req = threading.Thread(target=self.reqconn)
        req.setDaemon(True)

        # traversal_status:
        # 1 = traversal is done
        # 2 = traversal not needed
        # 0 = static traversal not established
        if not not_upnp:
            if not self.upnp_start():
                self.traversal_status = 0
            else:
                self.traversal_status = 1
        else:
            self.traversal_status = 2
            self.punching_server = punching_server(self)

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

        self.cctl = ClientControl(
            self,
            local_host,
            local_port
        )

        if self.traversal_status != 0:
            self.sctl = ServerControl(
                self.remote_host,
                self.remote_port,
                self,
                pt=bool(self.obfs_level)
            )

        req.start()

    def upnp_start(self):
        # return True = success, False = fail
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
                    return False
                return self.upnp_mapping(u)
            else:
                logging.error("No UPnP devices discovered")
        except Exception:
            logging.error("Error arose in UPnP discovery")

    def upnp_mapping(self, u):
        # Try to map ports via UPnP
        try:
            r = u.getspecificportmapping(self.remote_port, 'TCP')
            if r is None:
                b = u.addportmapping(self.remote_port, 'TCP', u.lanaddr,
                                     self.remote_port, 'ArkC Client port %u' % self.remote_port, '')
                u.addportmapping(self.punching_server_port, 'TCP', u.lanaddr,
                                 self.punching_server_port, 'ArkC Client supporting port %u' % self.punching_server_port, '')
                if b:
                    logging.info("Port mapping succeed")
                    atexit.register(self.exit_handler, upnp_obj=u)
                    return True
            elif r[0] == u.lanaddr and r[1] == self.remote_port:
                logging.info("Port mapping already existed.")
                return True
            else:
                logging.warning(
                    "Remote port " + str(self.remote_port) + " occupied in UPnP mapping")
                if self.remote_port <= 60000:
                    self.remote_port += 1
                logging.warning(
                    "Original remote port used. Retrying with port switched to " + str(self.remote_port))
                self.upnp_mapping(u)
        except Exception:
            logging.error("Error arose when initializing UPnP")
        finally:
            return False

    def exit_handler(self, upnp_obj):
        # Clean up UPnP
        try:
            upnp_obj.deleteportmapping(self.remote_port, 'TCP')
        except Exception:
            pass

    def tcp_punching(self, domain, addr, tcp=False):
        # TODO: implement tcp option
        A_query = dnslib.DNSRecord(
            q=dnslib.DNSQuestion(domain, dnslib.QTYPE.A))
        TXT_query = dnslib.DNSRecord(
            q=dnslib.DNSQuestion(domain, dnslib.QTYPE.TXT))
        A_rec = dnslib.DNSRecord.parse(A_query.send(addr[0], addr[1]))
        punching_ip = A_rec.short()
        TXT_rec = dnslib.DNSRecord.parse(TXT_query.send(addr[0], addr[1]))
        punching_port = int((TXT_rec.short()))
        self.punching_addr = (punching_ip, punching_port)
        self.tcp_punching_connection = tcp_punching_connect(
            self.punching_addr, self.remote_port, self)

    def reqconn(self):
        """Send DNS queries."""
        while True:
            # Start the request when the client needs connections
            self.check.wait()
            requestdata = self.generatereq()

            # TODO: should be moved aside to reuse the thread
            if self.traversal_status == 0:
                self.tcp_punching(requestdata + "." + self.ctl_domain, (
                    self.dns_servers[self.dns_count][0],
                    self.dns_servers[self.dns_count][1],
                    self.tcp, 1
                ))
                if self.traversal_status != 0:
                    self.sctl.startlisten()
            else:
                d = dnslib.DNSRecord(dnslib.DNSQuestion(
                    q=requestdata + "." + self.ctl_domain))
                # TODO: rewrite with dnslib, DNSRecord.send() and add TCP
                # support
                try:
                    d.send(self.dns_servers[self.dns_count][0],
                           self.dns_servers[self.dns_count][1],
                           self.tcp, 0.001)
                except:
                    pass

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
        msg.append(TOTP(bytes(h.hexdigest(), "UTF-8")).now())
        msg.append(binascii.hexlify(self.main_pw).decode("ASCII"))
        msg.append(myip)
        msg.append(salt)
        msg.append(str(self.traversal_status))
        if 1 <= self.obfs_level <= 2:
            certs_byte = urlsafe_b64_short_encode(self.certs_send)
            msg.extend([certs_byte[:50], certs_byte[50:]])
        elif self.obfs_level == 3:
            msg.append(
                ''.join([random.choice(ascii_letters) for _ in range(5)]))
        return '.'.join(msg)

    def issufficient(self):
        return all(_ is not None for _ in self.serverreceivers_pool)

    def refreshconn(self):
        # TODO: better algorithm
        f = lambda r: 1.0 / (1 + r.latency ** 2)
        recvs_avail = list(
            filter(lambda _: _ is not None, self.serverreceivers_pool))
        next_conn = weighted_choice(recvs_avail, f)
        next_conn.latency += 100  # Avoid repetition
        self.ready.preferred = False
        self.ready = next_conn
        next_conn.preferred = True

    def newconn(self, recv):
        # Called when receive new connections
        self.serverreceivers_pool[recv.i] = recv
        if self.ready is None:
            self.ready = recv
            recv.preferred = True
        self.refreshconn()
        if self.serverreceivers_pool.count(None) <= 2:
            self.check.clear()
        logging.info("Running socket %d" %
                     (self.req_num - self.serverreceivers_pool.count(None)))

    def closeconn(self, conn):
        # Called when a connection is closed
        if self.ready is not None:
            if self.ready.closing:
                if not all(_ is None for _ in self.serverreceivers_pool):
                    self.ready = [
                        _ for _ in self.serverreceivers_pool if _ is not None][0]
                    self.ready.preferred = True
                    self.refreshconn()
                else:
                    self.ready = None
        try:
            self.serverreceivers_pool[conn.i] = None
        except ValueError:
            pass
        if any(_ is None for _ in self.serverreceivers_pool):
            self.check.set()
        logging.info("Running socket %d" %
                     (self.req_num - self.serverreceivers_pool.count(None)))

    def register(self, clirecv):
        cli_id = None
        if all(_ is None for _ in self.serverreceivers_pool):
            return None
        while (cli_id is None) or (cli_id in self.clientreceivers_dict) or (cli_id == "00"):
            a = list(string.ascii_letters)
            random.shuffle(a)
            cli_id = ''.join(a[:2])
        self.clientreceivers_dict[cli_id] = clirecv
        return cli_id

    def remove(self, cli_id):
        try:
            if any(_ is not None for _ in self.serverreceivers_pool):
                self.ready.id_write(cli_id, CLOSECHAR, '000010')
        except Exception:
            pass
        try:
            self.clientreceivers_dict.pop(cli_id)
            for buf in self.server_send_buf_pool:
                buf.pop(cli_id)
            for idxlist in self.server_recv_max_idx:
                idxlist.pop(cli_id)
        except KeyError:
            pass

    # def server_check(self, server_id_list):
    #    '''check ready to use connections'''
    #    for conn in list(filter(lambda _: _ is not None, self.serverreceivers_pool)):
    #        if conn.idchar not in server_id_list:
    #            self.serverreceivers_pool[conn.i] = None
    #            conn.close()
    #    self.refreshconn()
    #    if len(list(filter(lambda _: _ is not None, self.serverreceivers_pool))) < self.req_num:
    #        self.check.set()

    def received_confirm(self, cli_id, index):
        '''send confirmation'''
        self.ready.id_write(cli_id, str(index), '000030')

    def retransmit(self, cli_id, seqs):
        '''called when asking retransmission'''
        if len(self.recvs) > 0:
            self.ready.id_write(cli_id, str(seqs), '020')

    def ptinit(self):
        # Initialize obfs4 TODO: problem may exist
        path = os.path.dirname(os.path.abspath(__file__))
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
        #self.resolv_cursor = 0

    def meekinit(self):
        # Initialize MEEK
        if self.remote_host == "":
            self.remote_host = "0.0.0.0"
        meekexec(
            self.ptexec + " --disable-tls", self.remote_host + ":" + str(self.remote_port))
        # Index of the resolver currently in use, move forward on failure
        #self.resolv_cursor = 0
