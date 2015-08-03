import socket
import asyncore
import random
import string
import logging

from common import AESCipher

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
        self.clientreceivers = {}
        asyncore.dispatcher.__init__(self, conn)
        self.from_remote_buffer_raw = b''
        self.cipher = None
        self.full = True
        self.no_data_count = 0

    def handle_connect(self):
        pass

    def handle_read(self):
        # Handle received data
        if self.cipher == None:
            self.begin_auth()
        else:
            read_count = 0
            self.from_remote_buffer_raw += self.recv(8192)
            bytessplit = self.from_remote_buffer_raw.split(bytes(SPLITCHAR, "UTF-8"))
            # TODO: Use Async
            for Index in range(len(bytessplit)):
                if Index < len(bytessplit) - 1:
                    decryptedtext = self.cipher.decrypt(bytessplit[Index])
                    try:
                        cli_id = decryptedtext[:2].decode("ASCII")
                    except Exception as err:
                        logging.warning("decode error")
                        cli_id = None
                    if cli_id in self.clientreceivers:
                        if decryptedtext[2:] != bytes(CLOSECHAR, "ASCII"):
                            self.clientreceivers[cli_id].from_remote_buffer += decryptedtext[2:]
                        else:
                            self.clientreceivers[cli_id].close()
                        read_count += len(decryptedtext) - 2
                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            logging.info('%04i from server' % read_count)

    def begin_auth(self):
        # Deal with the beginning authentication
        read = b''
        try:
                read += self.recv(768)
                if len(read) >= 768:
                    read = read[:768]
                    blank = read[:512]
                    if not self.ctl.remotepub.verify(bytes(self.ctl.str, "UTF-8"), (int(blank, 16), None)):
                        logging.warning("Authentication failed, socket closing")
                        self.close()
                    else:
                        self.cipher = AESCipher(self.ctl.localcert.decrypt(read[-256:]), bytes(self.ctl.str, "UTF-8"))
                        self.full = False
                        self.ctl.newconn(self)
                else:
                    if len(read) == 0:
                        self.no_data_count += 1
                    if self.no_data_count >= 10:
                        self.close()
        except Exception as err:
                logging.warning("Authentication failed, socket closing")
                self.close()
    
    def writable(self):
        for cli_id in self.clientreceivers:
            if self.clientreceivers[cli_id] is None:
                logging.warning("Client receiver %s NoneType error" % cli_id)
                del self.clientreceivers[cli_id]
            else:
                if len(self.clientreceivers[cli_id].to_remote_buffer) > 0:
                    return True
        return False

    def handle_write(self):
        # Called when writable
        if self.cipher is not None:
            for cli_id in self.clientreceivers:
                if self.clientreceivers[cli_id].to_remote_buffer:
                    self.id_write(cli_id)
        else:
            self.handle_read()

    def handle_close(self):
        self.ctl.closeconn()
        self.reallocateclientreceivers()
        self.close()
    
    def add_clientreceiver(self, clientreceiver, cli_id=None):
        # Called to add a client receiver
        if self.full:
            return None
        if cli_id is None:
            while (cli_id is None) or (cli_id in self.clientreceivers):
                a = list(string.ascii_letters)
                random.shuffle(a)
                cli_id = ''.join(a[:2])
        else:
            if cli_id in self.clientreceivers:
                return None
        self.clientreceivers[cli_id] = clientreceiver
        if len(self.clientreceivers) >= MAX_HANDLE:
            self.full = True
        return cli_id
        
    def id_write(self, cli_id, lastcontents=None):
        # Write to a certain cli_id. Lastcontents is used for CLOSECHAR
        if len(self.clientreceivers[cli_id].to_remote_buffer) <= 4096:
            sent = len(self.clientreceivers[cli_id].to_remote_buffer)
            self.send(self.cipher.encrypt(bytes(cli_id, "UTF-8") + self.clientreceivers[cli_id].to_remote_buffer) + bytes(SPLITCHAR, "UTF-8"))
        else:
            self.send(self.cipher.encrypt(bytes(cli_id, "UTF-8") + self.clientreceivers[cli_id].to_remote_buffer[:4096]) + bytes(SPLITCHAR, "UTF-8"))
            sent = 4096
        if lastcontents is not None:
            self.send(self.cipher.encrypt(bytes(cli_id, "UTF-8") + bytes(lastcontents, "UTF-8")) + bytes(SPLITCHAR, "UTF-8"))
            sent += len(lastcontents)
        logging.info('%04i to server' % sent)
        self.clientreceivers[cli_id].to_remote_buffer = self.clientreceivers[cli_id].to_remote_buffer[sent:]
        
    def remove_clientreceiver(self, cli_id):
        # Called when a client conn is closed
        if self.cipher is not None:
            self.id_write(cli_id, CLOSECHAR)
        del self.clientreceivers[cli_id]
        if len(self.clientreceivers) < MAX_HANDLE:
            self.full = False
    
    def reallocateclientreceivers(self):
        # Called when server conn is closing, try to make sure that everything goes smoothly
        self.full = True
        for cli_id in self.clientreceivers:
            dest = self.ctl.pickconn()
            if dest is not None:
                if dest.add_clientreceiver(self.clientreceivers[cli_id], cli_id) is None:
                    self.clientreceivers[cli_id].sreceiver = None
                    self.clientreceivers[cli_id].close() 
                else: self.clientreceivers[cli_id].sreceiver = dest
            else:
                self.clientreceivers[cli_id].sreceiver = None
                self.clientreceivers[cli_id].close
        
