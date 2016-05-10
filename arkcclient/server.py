#!/usr/bin/env python3
# coding:utf-8

import socket
import asyncore
import logging
import time
import struct

from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.Cipher import PKCS1_v1_5 as PKCS_Cipher
from Crypto import Random

from common import AESCipher
from common import get_timestamp, parse_timestamp
from _io import BlockingIOError

# Need to switch to asyncio

MAX_HANDLE = 100
CLOSECHAR = chr(4) * 5
REAL_SERVERPORT = 55000
SEG_SIZE = 4080     # 4096(total) - 1(type) - 2(id) - 6(index) - 7(splitchar)
SPLIT2 = b'\x00\x01\x02\x03\x04'


class ServerControl(asyncore.dispatcher):

    '''listen at the required port'''

    def __init__(self, serverip, serverport, ctl, pt=False, backlog=5):
        self.ctl = ctl
        asyncore.dispatcher.__init__(self)
        if ctl.ipv6 == "":
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.create_socket(socket.AF_INET6, socket.SOCK_STREAM)
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
        self.read = b''
        self.from_remote_buffer_raw = b''
        self.cipher = None
        self.preferred = False
        self.closing = False
        self.i = -1
        self.split = bytes(
            chr(27) +
            chr(28) +
            chr(27) +
            chr(28) +
            #"%X" % struct.unpack('B', self.ctl.main_pw[-2:-1])[0] +
            #"%X" % struct.unpack('B', self.ctl.main_pw[-3:-2])[0] +
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
        if seq == 0:
            raw_packet = "1" + "1" + msg[1:] + get_timestamp()
            to_write = self.cipher.encrypt(raw_packet) + self.split
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
            # print(self.from_remote_buffer_raw)
            bytessplit = self.from_remote_buffer_raw.split(self.split)
            #print("CALL READ %d" % len(bytessplit))
            #print("PASSWORD IS " + repr(self.cipher.password))
            for Index in range(len(bytessplit)):
                if len(bytessplit[Index]) == 0:
                        continue
                    
                if Index < len(bytessplit) - 1:
                    try:
                        b_dec = self.cipher.decrypt(bytessplit[Index])
                    except ValueError:
                        raw = bytessplit[Index]
                        logging.fatal(
                            "Decrypt error at server read, data lost permanently. Debug info:")
                        print("Content length: %d" % len(raw))
                        print(raw)
                        continue
                    # flag is 0 for normal data packet, 1 for ping packet
                    try:
                        flag = int(b_dec[:1].decode("UTF-8"))
                    except Exception:
                        logging.fatal("AES decrypt failed or bad encoding. Data lost permanently.")
                    if flag == 0:
                        try:
                            cli_id = b_dec[1:3].decode("UTF-8")
                            seq = int(b_dec[3:9].decode("UTF-8"))
                            b_data = b_dec[9:]
                        except Exception:
                            logging.warning(
                                "Not recognizable data from server, length = %d" % len(b_dec))
                            continue
                        if cli_id == "00":
                            if b_data == b_close:

                                logging.debug("closing connection")
                                self.closing = True
                                self.ctl.closeconn(self)
                                self.close()
                            else:
                                logging.warning(
                                    "Not recognizable data from server, length = %d" % len(b_dec))
              #               elif seq == 50:
              #                   id_list = b_data.decode("UTF-8").split(',')
                            # self.ctl.server_check(id_list)
                            # TODO: Experimental function
                        else:
                            if cli_id in self.ctl.clientreceivers_dict:
                                if seq == 30:
                                    self.update_max_idx(cli_id,
                                                        int(b_data.decode('utf-8')))
                                elif b_data != b_close:
                                    self.ctl.clientreceivers_dict[
                                        cli_id].from_remote_buffer_list.append(b_data)
                                    # self.ctl.clientreceivers_dict[
                                    #    cli_id].retransmission_check()
                                else:
                                    logging.warning(
                                    "Not recognizable data from server, length = %d" % len(b_dec))
                                    #for _ in self.ctl.server_recv_max_idx:
                                    #    if _ is not None:
                                    #        _.pop(cli_id, None)
                                    #self.ctl.clientreceivers_dict[
                                    #    cli_id].close()
                                read_count += len(b_data)
                            else:
                                logging.debug(
                                    "Deleted connection, %s" % cli_id)
                            # else:
                            #    self.encrypt_and_send(cli_id, CLOSECHAR)
                    #elif flag == 1:
                    #    # strip off type (always 1)
                    #    self.ping_recv(b_dec[1:].decode("UTF-8"))
                    #else:
                    #    logging.warning(
                    #        "Not recognizable data from server, length = %d" % len(b_dec))

                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            if read_count > 0:
                logging.debug('%04i from server' % read_count)

    def begin_auth(self):
        # Deal with the beginning authentication
        try:

            self.read += self.recv(2048)
            #print("CALL AUTH")
            if b'\r\n' in self.read:
                authdata = self.read.split(b'\r\n')
                #print (authdata)
                # print(self.ctl.main_pw)
                signature = authdata[0]
                # TODO: fix an error in int(signature,16)
                try:
                    signer = PKCS1_v1_5.new(self.ctl.serverpub)
                    h = SHA256.new(self.ctl.main_pw)
                    verify = signer.verify(h, signature)
                except ValueError:
                    logging.debug("ValueError captured at server.py line 165")
                    verify = False
                if not verify:
                    logging.warning(
                        "Authentication failed, socket closing, case 1")
                    self.close()
                else:
                    try:
                        auth_cipher = PKCS_Cipher.new(self.ctl.clientpri)
                        sentinel = Random.new().read(32)
                        message = auth_cipher.decrypt(authdata[1], sentinel)
                        if len(message) != 16:
                            raise ValueError
                        self.cipher = AESCipher(
                            message, self.ctl.main_pw)
                        self.full = False
                        idchar = authdata[2].decode('utf-8')
                        self.i = int(idchar)
                        self.ctl.newconn(self)
                        logging.debug(
                            "Authentication succeed, connection established")
                        self.send(
                            self.cipher.encrypt(b"2AUTHENTICATED" + authdata[2]  # +
                                                # repr(
                                                # self.ctl.server_recv_max_idx[self.i]).encode()
                                                )
                            #+ self.split
                        )
                        # self.send_legacy(
                        #    eval(authdata[3].rstrip(self.split).decode('utf-8')))
                        self.read = None
                    except IOError:
                        # TODO: figure out why
                        logging.warning(
                            "Authentication failed, socket closing, , case 2")
                        self.handle_close()
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

    def send_legacy(self, idx_list):
        buf = self.ctl.server_send_buf_pool[self.i]
        for cli_id in idx_list:
            try:
                queue = buf[cli_id]
                while len(queue) and queue[0][0] <= idx_list[cli_id]:
                    queue.popleft()
                if len(queue):
                    for idx, data in queue:
                        self.encrypt_and_send(cli_id, data, idx)
            except Exception:
                pass

# WRITE PARTS NEED TO BE OPTIMIZED

    def writable(self):
        if self.preferred:
            for cli_id in self.ctl.clientreceivers_dict:
                if self.ctl.clientreceivers_dict[cli_id] is None:
                    logging.warning(
                        "Client receiver %s NoneType error" % cli_id)
                    del self.ctl.clientreceivers_dict[cli_id]
                else:
                    if SPLIT2 in self.ctl.clientreceivers_dict[cli_id].to_remote_buffer:
                        return True
            return False
        else:
            return False

    def handle_write(self):
        # Called when writable
        if self.cipher is not None:
            if self.ctl.ready == self:
                written = 0
                for cli_id in self.ctl.clientreceivers_dict:
                    if SPLIT2 in self.ctl.clientreceivers_dict[cli_id].to_remote_buffer:
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
                str(self.ctl.clientreceivers_dict[cli_id].to_remote_buffer_index), 'utf-8')
            splitted = self.ctl.clientreceivers_dict[
                cli_id].to_remote_buffer.split(SPLIT2)  # [SEG SIZE]
            if len(splitted) <= 1:
                return 0
            buf = splitted[0]
            # print(repr(buf))
            self.ctl.clientreceivers_dict[cli_id].next_to_remote_buffer()
            self.ctl.clientreceivers_dict[
                cli_id].to_remote_buffer = b'\x00\x01\x02\x03\x04'.join(splitted[1:])
            if cli_id not in self.ctl.server_send_buf_pool[self.i]:
                self.ctl.server_send_buf_pool[self.i][cli_id] = []
        else:
            buf = bytes(buf, "utf-8")
        tosend = self.cipher.encrypt(
            b"0" + b_id + b_idx + buf) + self.split
        while len(tosend) > 0:
            sent = self.send(tosend)
            tosend = tosend[sent:]
        self.ctl.server_send_buf_pool[self.i][cli_id].append((buf, b_idx))
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

    def update_max_idx(self, cli_id, seq):
        try:
            queue = self.ctl.server_send_buf_pool[self.i][cli_id]
            while len(queue) and queue[0][0] <= seq:
                queue.popleft()
        except Exception:
            pass
