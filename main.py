import socket,asyncore,threading

class servercontrol(asyncore.dispatcher):
    def __init__(self, serverip, serverport, clientip, clientport, backlog=5):
        self.clientip=clientip
        self.clientport=clientport
        self.receivernum = 0
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((serverip,serverport))
        self.listen(backlog)
 
    def handle_accept(self):
        conn, addr = self.accept()
        print 'Serv_recv_Accept'
        self.receivernum += 1
        print 'Current Receivers = %d',self.receivernum
        serverreceiver(conn, self.clientip, self.clientport)

class serverreceiver(asyncore.dispatcher):
    def __init__(self,conn, clientip, clientport):
        self.clientip=clientip
        self.clientport=clientport
        asyncore.dispatcher.__init__(self,conn)
        self.from_remote_buffer=''
        self.to_remote_buffer=''
        t1=threading.Thread(target=self.clientctl)
        t1.start()

    def clientctl(self):
        clientcontrol(self, self.clientip, self.clientport)

    def handle_connect(self):
        pass
 
    def handle_read(self):
        read = self.recv(4096)
        # print '%04i -->'%len(read)
        self.from_remote_buffer += read
 
    def writable(self):
        return (len(self.to_remote_buffer) > 0)
 
    def handle_write(self):
        sent = self.send(self.to_remote_buffer)
        # print '%04i <--'%sent
        self.to_remote_buffer = self.to_remote_buffer[sent:]
 
    def handle_close(self):
        self.close()
        
class clientcontrol(asyncore.dispatcher):
    def __init__(self, receiver, clientip, clientport, backlog=5):
        self.receiver=receiver
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET,socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((clientip,clientport))
        self.listen(backlog)

    def handle_accept(self):
        conn, addr = self.accept()
        print 'Client_recv_Accept'
        clientreceiver(conn, self.receiver)

class clientreceiver(asyncore.dispatcher):
    def __init__(self,conn, serverreceiver):
        self.serverreceiver=serverreceiver
        asyncore.dispatcher.__init__(self,conn)
        self.from_remote_buffer=''
        self.to_remote_buffer=''

    def handle_connect(self):
        pass
 
    def handle_read(self):
        read = self.recv(4096)
        print '%04i -->'%len(read)
        self.serverreceiver.to_remote_buffer +=read
 
    def writable(self):
        return (len(self.serverreceiver.from_remote_buffer) > 0)

    def handle_write(self):
        sent = self.send(self.serverreceiver.from_remote_buffer)
        print '%04i <--'%sent
        self.serverreceiver.from_remote_buffer = serverreceiver.from_remote_buffer[sent:]
 
    def handle_close(self):
        self.close()

if __name__=='__main__':
    servercontrol('0.0.0.0', 8000, '0.0.0.0', 8001)
    asyncore.loop()
