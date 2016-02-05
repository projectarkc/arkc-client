import socket
import asyncore
import logging
import time
import struct

from common import AESCipher
from common import get_timestamp, parse_timestamp
from _io import BlockingIOError

# Need to switch to asyncio

MAX_HANDLE = 100
CLOSECHAR = chr(4) * 5
REAL_SERVERPORT = 55000
SEG_SIZE = 4080     # 4096(total) - 1(type) - 2(id) - 6(index) - 7(splitchar)


class ServerControl(asyncore.dispatcher):

    '''listen at the required port'''

    def __init__(self, serverip, serverport, ctl, pt=False, backlog=5):
        self.ctl = ctl
        asyncore.dispatcher.__init__(self)
        if ctl.ipv6 == "":
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.create_socket(socket.AF_INET6, socket.SOCK_STREAM)
        # TODO: support IPv6
        self.set_reuse_addr()

        if pt:
            serverip = "127.0.0.1"
            serverport = REAL_SERVERPORT
        self.bind((serverip, serverport))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        logging.info('Serv_recv_Accept from %s' % str(addr))
        ServerReceiver(conn, self.ctl)

    def getrecv(self):
        return self.ctl.offerconn()


class ServerReceiver(asyncore.dispatcher):

    '''represent each connection with arkc-server'''

    def __init__(self, conn, ctl):
        self.ctl = ctl
        asyncore.dispatcher.__init__(self, conn)
        self.from_remote_buffer_raw = b''
        self.cipher = None
        self.preferred = False
        self.closing = False
        self.i = -1
        self.split = bytes(
            chr(27) +
            chr(28) +
            "%X" % struct.unpack('B', self.ctl.main_pw[-2:-1])[0] +
            "%X" % struct.unpack('B', self.ctl.main_pw[-3:-2])[0] +
            chr(31),
            "UTF-8"
        )
        self.no_data_count = 0
        self.read = b''
        self.latency = 10000
        time.sleep(0.05)  # async
        self.begin_auth()

    def ping_recv(self, msg):
        """Parse ping (without flag) and send back when necessary."""
        seq = int(msg[0])
        #logging.debug("recv ping%d" % seq)
        if seq == 0:
            raw_packet = "1" + "1" + msg[1:] + get_timestamp()
            to_write = self.cipher.encrypt(raw_packet) + self.split
            #logging.debug("send ping1")
            self.send(to_write)
        else:
            time1 = parse_timestamp(msg[1:])
            self.latency = int(time.time() * 1000) - time1
            logging.debug("latency: %dms" % self.latency)

    def handle_connect(self):
        pass

    def handle_read(self):
        """Handle received data."""

        b_close = bytes(CLOSECHAR, "ASCII")

        if self.cipher is None:
            self.begin_auth()
        else:
            read_count = 0
            self.from_remote_buffer_raw += self.recv(8192)
            bytessplit = self.from_remote_buffer_raw.split(self.split)
            for Index in range(len(bytessplit)):
                if Index < len(bytessplit) - 1:
                    b_dec = self.cipher.decrypt(bytessplit[Index])
                    # flag is 0 for normal data packet, 1 for ping packet
                    flag = int(b_dec[:1].decode("UTF-8"))
                    if flag == 0:
                        try:
                            cli_id = b_dec[1:3].decode("UTF-8")
                            seq = int(b_dec[3:9].decode("UTF-8"))
                            b_data = b_dec[9:]
                        except Exception:
                            logging.warning("decode error")
                            cli_id = None
                        if cli_id == "00":
                            if b_data == b_close:

                                logging.debug("closing connection")
                                self.closing = True
                                self.ctl.closeconn(self)
                                self.close()
              #               elif seq == 50:
              #                   id_list = b_data.decode("UTF-8").split(',')
                            # self.ctl.server_check(id_list)
                            # TODO: Experimental function
                        else:
                            if cli_id in self.ctl.clientreceivers:
                                if b_data != b_close:
                                    self.ctl.max_recved_idx[
                                        self.i][cli_id] = seq
                                    self.ctl.clientreceivers[
                                        cli_id].from_remote_buffer[seq] = b_data
                                else:
                                    for _ in self.ctl.max_recved_idx:
                                        if _ is not None:
                                            _.pop(cli_id, None)
                                    self.ctl.clientreceivers[cli_id].close()
                                read_count += len(b_data)
                            # else:
                            #    self.encrypt_and_send(cli_id, CLOSECHAR)
                    else:
                        # strip off type (always 1)
                        self.ping_recv(b_dec[1:].decode("UTF-8"))

                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            if read_count > 0:
                logging.debug('%04i from server' % read_count)

    def begin_auth(self):
        # Deal with the beginning authentication
        self.read = b''
        try:
            self.read += self.recv(770)
            if len(self.read) >= 770:
                self.read = self.read[:770]
                signature = self.read[:512]
                # TODO: fix an error in int(signature,16)
                if not self.ctl.serverpub.verify(self.ctl.main_pw, (int(signature, 16), None)):
                    logging.warning("Authentication failed, socket closing")
                    self.close()
                else:
                    # self.send(self.ctl.localcert.encrypt(pyotp.HOTP(self.ctl.localcert_sha1)) + self.splitchar)
                    try:
                        self.cipher = AESCipher(
                            self.ctl.localcert.decrypt(self.read[512:768]), self.ctl.main_pw)
                    except ValueError:
                        # TODO: figure out why
                        logging.warning(
                            "Authentication failed, socket closing")
                        self.handle_close()
                    self.full = False
                    idchar = self.read[768:770].decode('utf-8')
                    self.i = int(idchar)
                    self.ctl.newconn(self)
                    logging.debug(
                        "Authentication succeed, connection established")
                    self.send(
                        self.cipher.encrypt(b"2AUTHENTICATED" + self.read[768:770] +
                                            repr(
                                                self.ctl.max_recved_idx[self.i]).encode()
                                            )
                        + self.split
                    )
            else:
                if len(self.read) == 0:
                    self.no_data_count += 1
        except BlockingIOError:
            pass

        except socket.error:
            logging.info("empty recv error")

        except Exception as err:
            raise err
            logging.error(
                "Authentication failed, due to error, socket closing")
            self.close()

    def writable(self):
        if self.preferred:
            for cli_id in self.ctl.clientreceivers:
                if self.ctl.clientreceivers[cli_id] is None:
                    logging.warning(
                        "Client receiver %s NoneType error" % cli_id)
                    del self.ctl.clientreceivers[cli_id]
                else:
                    if len(self.ctl.clientreceivers[cli_id].to_remote_buffer) > 0:
                        return True
        else:
            return False

    def handle_write(self):
        # Called when writable
        if self.cipher is not None:
            if self.ctl.ready == self:
                written = 0
                for cli_id in self.ctl.clientreceivers:
                    if self.ctl.clientreceivers[cli_id].to_remote_buffer:
                        self.id_write(cli_id)
                        written += 1
                    if written >= self.ctl.swapcount:
                        break
            self.ctl.refreshconn()
        else:
            self.handle_read()

    def handle_close(self):
        self.closing = True
        self.ctl.closeconn(self)
        self.close()

    def encrypt_and_send(self, cli_id, buf=None, b_idx=None):
        """Encrypt and send data, and return the length sent.

        When `buf` is not specified, it is automatically read from the
        `to_remote_buffer` corresponding to `cli_id`.
        """
        b_id = bytes(cli_id, "UTF-8")
        if buf is None:
            b_idx = bytes(
                str(self.ctl.clientreceivers[cli_id].to_remote_buffer_index), 'utf-8')
            buf = self.ctl.clientreceivers[cli_id].to_remote_buffer[:SEG_SIZE]
            self.ctl.clientreceivers[cli_id].next_to_remote_buffer()
            self.ctl.clientreceivers[cli_id].to_remote_buffer = self.ctl.clientreceivers[
                cli_id].to_remote_buffer[len(buf):]
        else:
            buf = bytes(buf, "utf-8")
        self.send(self.cipher.encrypt(b"0" + b_id + b_idx + buf) +
                  self.split)
        return len(buf)

    def id_write(self, cli_id, lastcontents=None, seq=None):
        # Write to a certain cli_id. Lastcontents is used for CLOSECHAR
        sent = 0
        try:
            if lastcontents is not None and seq is not None:
                sent += self.encrypt_and_send(cli_id,
                                              lastcontents,
                                              bytes(seq, 'utf-8'))
            sent = self.encrypt_and_send(cli_id)
            logging.debug('%04i to server' % sent)

        except KeyError:
            pass
