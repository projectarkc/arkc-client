import logging
import asyncio

# Need to switch to asyncio


class clientcontrol(asyncio.Protocol):

    """ a standard client service dispatcher """

    def __init__(self, control, loop):
        self.control = control
        self.loop = loop
        self.write_event = asyncio.Event()
        self.write_event.clear()

        self.from_remote_buffer = {}
        self.from_remote_buffer_index = 100
        self.to_remote_buffer = b''
        self.to_remote_buffer_index = 100

    def connection_made(self, transport):
        peername = transport.get_extra_info('peername')
        logging.info('Client_recv_Accept from %s'.format(peername))
        self.idchar = self.control.register(self)
        if self.idchar is None:
            self.transport.close()
        else:
            self.transport = transport
            self.loop.create_task(self.handle_write())

    def data_received(self, data):
        data
        logging.debug('%04i from client' % len(data))
        self.to_remote_buffer += data

    def writable(self):
        if self.from_remote_buffer_index in self.from_remote_buffer:
            self.write_event.set()
        else:
            self.write_event.lock()

    @asyncio.coroutine
    def handle_write(self):
        while True:
            sent = 0
            self.write_event.wait()
            sent = sent + \
                self.transport.write(
                    self.from_remote_buffer.pop(self.from_remote_buffer_index))
            self.next_from_remote_buffer()
            logging.debug('%04i to client' % sent)
            if not(self.writable()):
                yield from asyncio.sleep(0.01)

    def handle_close(self):
        self.control.remove(self.idchar)
        self.transport.close()

    def next_to_remote_buffer(self):
        self.to_remote_buffer_index += 1
        if self.to_remote_buffer_index == 1000:
            self.to_remote_buffer_index = 100

    def next_from_remote_buffer(self):
        self.from_remote_buffer_index += 1
        if self.from_remote_buffer_index == 1000:
            self.from_remote_buffer_index = 100
