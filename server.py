import socket
import asyncore
import random
import string

from Crypto.Cipher import AES

#Need to switch to asyncio

SPLITCHAR = chr(30) * 5
CLOSECHAR = chr(4) *5

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
        print('Serv_recv_Accept from %s' % str(addr))
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
        self.cipherinstance = None
        self.full = False
        self.ctl.newconn(self)

    def handle_connect(self):
        pass

    def handle_read(self):
        if self.cipher == None:
            self.begin_auth()
        else:
            read_count = 0
            self.from_remote_buffer_raw += self.recv(8192)
            bytessplit = self.from_remote_buffer_raw.split(bytes(SPLITCHAR, "UTF-8"))
            #TODO: Use Async
            for Index in range(len(bytessplit)):
                if Index < len(bytessplit) - 1:
                    decryptedtext = self.cipherinstance.decrypt(bytessplit[Index])
                    self.cipherinstance = self.cipher
                    try:
                        cli_id = decryptedtext[:2].decode("UTF-8")
                    except Exception as err:
                        print("decode error")
                        cli_id = None
                    if cli_id in self.clientreceivers:
                        if decryptedtext[2:] != CLOSECHAR:
                            self.clientreceivers[cli_id].from_remote_buffer += decryptedtext[2:]
                        else:
                            self.clientreceivers[cli_id].close()
                        read_count += len(decryptedtext) - 2
                else:
                    self.from_remote_buffer_raw = bytessplit[Index]
            print('%04i from server' % read_count)

    def begin_auth(self):
        read = b''
        try:
                read += self.recv(768)
                if len(read) >= 768:
                    read = read[:768]
                    blank = read[:512]
                    if not self.ctl.remotepub.verify(bytes(self.ctl.str, "UTF-8"), (int(blank, 16), None)):
                        print("Authentication failed, socket closing")
                        self.ctl.closeconn()
                        self.close()
                    else:
                        self.cipher = AES.new(self.ctl.localcert.decrypt(read[-256:]), AES.MODE_CFB, bytes(self.ctl.str, "UTF-8"))
                        self.cipherinstance = self.cipher
        except Exception as err:
                print("Authentication failed, socket closing")
                self.ctl.closeconn()
                self.close()
    
    def writable(self):
        able = False
        for cli_id in self.clientreceivers:
            if len(self.clientreceivers[cli_id].to_remote_buffer) > 0:
                able = True
                break
        return able

    def handle_write(self):
        if self.cipherinstance is not None:
            for cli_id in self.clientreceivers:
                self.id_write(cli_id)
        else:
            self.handle_read()

    def handle_close(self):
        self.ctl.closeconn()
        self.reallocateclientreceivers()
        self.close()
    
    def add_clientreceiver(self, clientreceiver, cli_id = None):
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
        
    def id_write(self, cli_id, lastcontents = None):
        if len(self.clientreceivers[cli_id].to_remote_buffer)<=4096:
            sent = len(self.clientreceivers[cli_id].to_remote_buffer)
            self.send(self.cipherinstance.encrypt(bytes(cli_id, "UTF-8") + self.clientreceivers[cli_id].to_remote_buffer) + bytes(SPLITCHAR, "UTF-8"))
        else:
            self.send(self.cipherinstance.encrypt(bytes(cli_id, "UTF-8") + self.clientreceivers[cli_id].to_remote_buffer[:4096]) + bytes(SPLITCHAR, "UTF-8"))
            sent = 4096
        if lastcontents is not None:
            self.send(self.cipherinstance.encrypt(bytes(cli_id, "UTF-8") + bytes(lastcontents, "UTF-8") + bytes(SPLITCHAR, "UTF-8")))
            sent += len(lastcontents)
        self.cipherinstance = self.cipher
        print('%04i to server' % sent)
        self.clientreceivers[cli_id].to_remote_buffer = self.clientreceivers[cli_id].to_remote_buffer[sent:]
        
    def remove_clientreceiver(self, cli_id):
        self.id_write(cli_id, CLOSECHAR)
        del self.clientreceivers[cli_id]
        if len(self.clientreceivers) < MAX_HANDLE:
            self.full = False
    
    def reallocateclientreceivers(self): #TODO: reallocate
        for cli_id in self.clientreceivers:
            dest = self.ctl.pickconn()
            if dest is not None:
                if dest.add_clientreceiver(self.clientreceivers[cli_id].close(), cli_id) is None:
                    self.clientreceivers[cli_id].close() 
            else:
                self.clientreceivers[cli_id].close
        