import socket
import asyncore
import logging
import time
import struct

from common import AESCipher
from _io import BlockingIOError

# Need to switch to asyncio

SPLITCHAR = chr(27) + chr(28) + chr(29) + chr(30) + chr(31)
CLOSECHAR = chr(4) * 5

MAX_HANDLE = 100

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
        logging.info('Serv_recv_Accept from %s' % str(addr))
        serverreceiver(conn, self.ctl)
        
    def getrecv(self):
        return self.ctl.offerconn()
        
class serverreceiver(asyncore.dispatcher):

    def __init__(self, conn, ctl):
        self.ctl = ctl
        asyncore.dispatcher.__init__(self, conn)
        self.from_remote_buffer_raw = b''
        self.cipher = None
        self.preferred = False
        self.closing = False
        #self.splitchar = SPLITCHAR #
        self.splitchar = chr(27)+chr(28)+"%X" % struct.unpack('B', self.ctl.str[-2:-1])[0] + "%X" % struct.unpack('B', self.ctl.str[-3:-2])[0]+chr(31)
        print (self.splitchar)
        self.no_data_count = 0
        self.read = b''
        self.begin_auth()

    def handle_connect(self):
        pass

    def handle_read(self):
        # Handle received data
        if self.cipher == None:
            self.begin_auth()
        else:
            read_count = 0
            self.from_remote_buffer_raw += self.recv(8192)
            bytessplit = self.from_remote_buffer_raw.split(bytes(self.splitchar, "UTF-8"))
            for Index in range(len(bytessplit)):
                if Index < len(bytessplit) - 1:
                    decryptedtext = self.cipher.decrypt(bytessplit[Index])
                    try:
                        cli_id = decryptedtext[:2].decode("ASCII")
                    except Exception as err:
                        logging.warning("decode error")
                        cli_id = None
                    if cli_id in self.ctl.clientreceivers:
                        if decryptedtext[2:] != bytes(CLOSECHAR, "ASCII"):
                            self.ctl.clientreceivers[cli_id].from_remote_buffer += decryptedtext[2:]
                        else:
                            self.ctl.clientreceivers[cli_id].close()
                        read_count += len(decryptedtext) - 2
                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            logging.info('%04i from server' % read_count)

    def begin_auth(self):
        # Deal with the beginning authentication
        time.sleep(0.05)
        self.read = b''
        try:
            self.read += self.recv(768)
            if len(self.read) >= 768:
                self.read = self.read[:768]
                blank = self.read[:512]
                if not self.ctl.remotepub.verify(self.ctl.str, (int(blank, 16), None)):
                    logging.warning("Authentication failed, socket closing")
                    self.close()
                else:
                    self.cipher = AESCipher(self.ctl.localcert.decrypt(self.read[-256:]), self.ctl.str)
                    self.full = False
                    self.ctl.newconn(self)
                    logging.info("Authentication succeed, connection established")
            else:
                if len(self.read) == 0:
                    self.no_data_count += 1
                    #if self.no_data_count >= 10:
                    #    self.close()
        except BlockingIOError as err:
            pass
        except Exception as err:
            logging.warning("Authentication failed, due to error, socket closing")
            self.close()
            
    def writable(self):
        if self.preferred:
            for cli_id in self.ctl.clientreceivers:
                if self.ctl.clientreceivers[cli_id] is None:
                    logging.warning("Client receiver %s NoneType error" % cli_id)
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
                writed = 0
                for cli_id in self.ctl.clientreceivers:
                    if self.ctl.clientreceivers[cli_id].to_remote_buffer:
                        self.id_write(cli_id)
                        writed += 1
                    if writed >= 5:
                        break
            self.ctl.refreshconn()
        else:
            self.handle_read()

    def handle_close(self):
        self.closing = True
        self.ctl.closeconn(self)
        self.close()        
        
    def id_write(self, cli_id, lastcontents=None):
        # Write to a certain cli_id. Lastcontents is used for CLOSECHAR
        if len(self.ctl.clientreceivers[cli_id].to_remote_buffer) <= 4096:
            sent = len(self.ctl.clientreceivers[cli_id].to_remote_buffer)
            self.send(self.cipher.encrypt(bytes(cli_id, "UTF-8") + self.ctl.clientreceivers[cli_id].to_remote_buffer) + bytes(self.splitchar, "UTF-8"))
        else:
            self.send(self.cipher.encrypt(bytes(cli_id, "UTF-8") + self.ctl.clientreceivers[cli_id].to_remote_buffer[:4096]) + bytes(self.splitchar, "UTF-8"))
            sent = 4096
        if lastcontents is not None:
            self.send(self.cipher.encrypt(bytes(cli_id, "UTF-8") + bytes(lastcontents, "UTF-8")) + bytes(self.splitchar, "UTF-8"))
            sent += len(lastcontents)
        logging.info('%04i to server' % sent)
        self.ctl.clientreceivers[cli_id].to_remote_buffer = self.ctl.clientreceivers[cli_id].to_remote_buffer[sent:]