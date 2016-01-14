import asyncio
import logging
import time
import struct

from common import AESCipher
from common import get_timestamp, parse_timestamp
from main import loop

MAX_HANDLE = 100
CLOSECHAR = chr(4) * 5
SEG_SIZE = 4083     # 4096(total) - 1(type) - 2(id) - 3(index) - 7(splitchar)


class servercontrol(asyncio.Protocol):

    def __init__(self, ctl):
        self.ctl = ctl
        self.write_event = asyncio.Event()
        self.write_event.clear()
        self.auth_raw = b''
        self.ctl = ctl
        self.from_remote_buffer_raw = b''
        self.cipher = None
        self.preferred = False
        self.closing = False
        self.split = bytes(
            chr(27) +
            chr(28) +
            "%X" % struct.unpack('B', self.ctl.str[-2:-1])[0] +
            "%X" % struct.unpack('B', self.ctl.str[-3:-2])[0] +
            chr(31),
            "UTF-8"
        )
        self.no_data_count = 0
        self.auth_raw = b''
        self.latency = 10000

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        logging.info('Serv_recv_Accept from {}'.format(peername))
        self.transport = transport
        self.begin_auth()

    def getrecv(self):
        return self.ctl.offerconn()

    def ping_recv(self, msg):
        """Parse ping (without flag) and send back when necessary."""
        seq = int(msg[0])
        logging.debug("recv ping%d" % seq)
        if seq == 0:
            raw_packet = "1" + "1" + msg[1:] + get_timestamp()
            to_write = self.cipher.encrypt(raw_packet) + self.split
            logging.debug("send ping1")
            self.transport.write(to_write)
        else:
            time1 = parse_timestamp(msg[1:])
            self.latency = int(time.time() * 1000) - time1
            logging.debug("latency: %dms" % self.latency)

    def data_received(self, data):
        """Handle received data."""

        b_close = bytes(CLOSECHAR, "ASCII")

        if self.cipher is None:
            self.begin_auth(data)
        else:
            read_count = 0
            self.from_remote_buffer_raw += data
            bytessplit = self.from_remote_buffer_raw.split(self.split)
            for Index in range(len(bytessplit)):
                if Index < len(bytessplit) - 1:
                    b_dec = self.cipher.decrypt(bytessplit[Index])
                    # flag is 0 for normal data packet, 1 for ping packet
                    flag = int(b_dec[:1].decode("UTF-8"))
                    if flag == 0:
                        try:
                            cli_id = b_dec[1:3].decode("UTF-8")
                            seq = int(b_dec[3:6].decode("UTF-8"))
                            b_data = b_dec[6:]
                        except Exception:
                            logging.warning("decode error")
                            cli_id = None
                        if cli_id == "00" and b_data == b_close:
                            self.closing = True
                            self.ctl.closeconn(self)
                        else:
                            if cli_id in self.ctl.clientreceivers:
                                if b_data != b_close:
                                    self.ctl.clientreceivers[
                                        cli_id].from_remote_buffer[seq] = b_data
                                else:
                                    self.ctl.clientreceivers[cli_id].close()
                                read_count += len(b_data)
                    else:
                        # strip off type (always 1)
                        self.ping_recv(b_dec[1:].decode("UTF-8"))

                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            logging.debug('%04i from server' % read_count)

    def begin_auth(self, data):

        # Deal with the beginning authentication
        time.sleep(0.05)
        self.auth_raw = b''
        try:
            self.auth_raw += data
            if len(self.auth_raw) >= 768:
                self.auth_raw = self.auth_raw[:768]
                blank = self.auth_raw[:512]
                if not self.ctl.remotepub.verify(self.ctl.str, (int(blank, 16), None)):
                    logging.warning("Authentication failed, socket closing")
                    self.close()
                else:
                    # self.send(self.ctl.localcert.encrypt(pyotp.HOTP(self.ctl.localcert_sha1)) + self.splitchar)
                    self.cipher = AESCipher(
                        self.ctl.localcert.decrypt(self.auth_raw[-256:]), self.ctl.str)
                    self.full = False
                    self.ctl.newconn(self)
                    # , client auth string sent")
                    logging.debug(
                        "Authentication succeed, connection established")
                    loop.call_soon(self.handle_write())
            else:
                if len(self.auth_raw) == 0:
                    self.no_data_count += 1
        except Exception:
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
                        self.write_event.set()
                        return True
            self.write_event.clear()
            return False
        else:
            self.write_event.clear()
            return False

    async def handle_write(self):
        # Called when writable
        while True:
            self.write_event.wait()
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
            self.writable()

    def handle_close(self):
        self.closing = True
        self.ctl.closeconn(self)
        self.transport.close()

    def encrypt_and_send(self, cli_id, buf=None):
        """Encrypt and send data, and return the length sent.

        When `buf` is not specified, it is automatically read from the
        `to_remote_buffer` corresponding to `cli_id`.
        """
        b_id = bytes(cli_id, "UTF-8")
        idx = self.ctl.clientreceivers[cli_id].to_remote_buffer_index
        b_idx = bytes('%i' % idx, "UTF-8")
        if buf is None:
            buf = self.ctl.clientreceivers[cli_id].to_remote_buffer
        self.transport.write(self.cipher.encrypt(b"0" + b_id + b_idx + buf[:SEG_SIZE]) +
                             self.split)
        return min(SEG_SIZE, len(buf))

    def id_write(self, cli_id, lastcontents=None):
        # Write to a certain cli_id. Lastcontents is used for CLOSECHAR
        sent = 0
        try:
            sent = self.encrypt_and_send(cli_id)
            self.ctl.clientreceivers[cli_id].next_to_remote_buffer()
        except KeyError:
            pass
        if lastcontents is not None:
            sent += self.encrypt_and_send(cli_id, bytes(lastcontents, "UTF-8"))
            # self.ctl.clientreceivers[cli_id].next_to_remote_buffer()
        logging.debug('%04i to server' % sent)
        try:
            self.ctl.clientreceivers[cli_id].to_remote_buffer = self.ctl.clientreceivers[
                cli_id].to_remote_buffer[sent:]
        except KeyError:
            pass
