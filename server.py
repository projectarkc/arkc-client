import socket
import asyncore
import random
import string

from Crypto.Cipher import AES


#Need to switch to asyncio

SPLITCHAR = chr(30) * 5
CLOSECHAR = chr(4) *5

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
        self.from_remote_buffers = {}
        self.from_remote_buffer_raw = b''
        self.to_remote_buffers = {}
        self.cipher = None
        self.cipherinstance = None
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
                if Index < len(bytessplit) -1:
                    decryptedtext = self.cipherinstance.decrypt(bytessplit[Index])
                    self.cipherinstance = self.cipher
                    if decryptedtext != CLOSECHAR:
                        self.from_remote_buffers[decryptedtext[:2]] += decryptedtext[-2:]
                        read_count += len(decryptedtext[-2:])
                    else:
                        self.clientreceivers[id].close()
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
        return self.checkwrite()

    def handle_write(self):
        if self.cipherinstance is not None:
            for cli_id in self.to_remote_buffers:
                self.id_write(cli_id)
        else:
            self.handle_read()

    def handle_close(self):
        self.ctl.closeconn()
        self.closeclientreceivers()
        self.close()
    
    def add_clientreceiver(self, clientreceiver):
        cli_id = None
        looptime = 0
        while (cli_id is None) or (self.clientreceivers.has_key(cli_id)):
            a = list(string.ascii_letters)
            random.shuffle(a)
            cli_id = ''.join(a[:2])
            if looptime > 100:
                print("100 times failed generating connection ID")
                quit()
                #should label the connection as fully used and break
            else:
                looptime += 1
        self.clientreceivers[cli_id] = clientreceiver
        self.to_remote_buffers[cli_id] = b''
        self.from_remote_buffers[cli_id] = b''
        return cli_id
        
    def id_write(self, cli_id, lastcontents = None):
        if len(self.to_remote_buffers[cli_id])<=4096:
            sent = len(self.to_remote_buffers[cli_id])
            self.send(self.cipherinstance.encrypt(cli_id + self.to_remote_buffers[cli_id]) + bytes(SPLITCHAR, "UTF-8"))
        else:
            self.send(self.cipherinstance.encrypt(cli_id + self.to_remote_buffers[cli_id][:4096]) + bytes(SPLITCHAR, "UTF-8"))
            sent = 4096
        if lastcontents is not None:
            self.send(self.cipherinstance.encrypt(cli_id + lastcontents + bytes(SPLITCHAR, "UTF-8")))
        self.cipherinstance = self.cipher
        print('%04i to server' % sent)
        self.to_remote_buffers[cli_id] = self.to_remote_buffers[cli_id][sent:]
        
    def remove_clientreceiver(self, cli_id):
        del self.clientreceivers[cli_id]
        del self.from_remote_buffers[cli_id]
        self.id_write(cli_id, CLOSECHAR)
        del self.to_remote_buffers[cli_id]
    
    def closeclientreceivers(self):
        for cli_id in self.clientreceivers:
            self.clientreceivers[cli_id].close()
    
    def checkwrite(self):
        writeable = False
        for cli_id in self.to_remote_buffers:
            if len(self.to_remote_buffers[cli_id]) > 0:
                writeable = True
                break
        return writeable
        