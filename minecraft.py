print 'importing twisted'
from twisted.application import internet, service
from twisted.internet import reactor, protocol, defer
from twisted.protocols import basic
from twisted.python import components

from zope.interface import Interface, implements

print 'importing os'
import os, re, random as r, shlex, time


class LineEventer(basic.LineReceiver):

    delimiter = '\n'

    def lineReceived(self, line):
       print line 
    
class DummyTransport:
    disconnecting = 0

transport = DummyTransport()

class MinecraftProtocol(protocol.ProcessProtocol):

    service = None
    empty = 1
    
    def connectionMade(self):
        self.output = LineEventer()
        self.output.makeConnection(transport)

    def outReceived(self, data):
        self.output.dataReceived(data)
        self.empty = data[-1] == '\n'

    errReceived = outReceived

    def processEnded(self, reason):

        if not self.empty:
            self.output.dataReceived('\n')

        self.service.connectionLost()


    def say(self, msgs):
        for msg in msgs.split('\n'):
            self.transport.write('say ' + msg + '\n')

    def kick(self, player):
        self.transport.write('kick ' + player + '\n')

    def ban(self, player):
        self.transport.write('ban ' + player + '\n')

    def pardon(self, player):
        self.transport.write('pardon ' + player + '\n')

    def ban_ip(self, ip):
        self.transport.write('ban-ip ' + ip + '\n')
    
    def pardon_ip(self, ip):
        self.transport.write('pardon-ip ' + ip + '\n')

    def op(self, player):
        self.transport.write('op ' + player + '\n')

    def deop(self, player):
        self.transport.write('deop ' + player + '\n')

    def tp(self, player_from, player_to):
        self.transport.write('tp ' + player_from + ' ' + player_to + '\n')

    def give(self, player, id , num=None):

        if num:
            self.transport.write('give ' + player + ' ' + str(id) + ' ' + \
                    str(num) + '\n')
        else:
            self.transport.write('give ' + player + ' ' + str(id) + '\n')

    def tell(self, player, msg):
        self.transport.write('tell ' + player + ' ' + msg + '\n')

    def stop(self):
        self.transport.write('stop\n')

    def save_all(self):
        self.transport.write('save-all\n')

    def save_off(self):
        self.transport.write('save-off\n')

    def save_on(self):
        self.transport.write('save-on\n')

    def list(self):
        self.transport.write('list\n')

    def time(self, action, amount):
        self.transport.write('time ' + action + ' ' + str(amount) + '\n')


class MinecraftService(service.Service):
    fatal_time = 1
    active = 0
    eventer = None
    time_started = 0
    threshold = 1 # secounds
    minecraft_proc = None
    stopping_deferred = None

    def __init__(self, run_dir):
        self.run_dir = run_dir

    def startService(self):
        service.Service.startService(self)
        self.active = 1
        reactor.callLater(0, self.start_minecraft)

    def stopService(self):
        service.Service.stopService(self)
        self.active = 0
        self.minecraft_proc.stop()
        d = self.stopping_deferred = defer.Deferred()
        return d

    def start_minecraft(self):
        p = self.minecraft_proc = MinecraftProtocol()
        p.service = self
        self.time_started = time.time()
        reactor.spawnProcess(p, '/usr/bin/minecraft-server',
            args=['minecraft-server', 'nogui'],
            env=os.environ,
            path=self.run_dir,
            usePTY=True)

    def connectionLost(self):
        if self.active:
            if time.time() - self.time_started < self.threshold:
                print 'Minecraft died too quickly, giving up!'
            else:
                reactor.callLater(0, start_minecraft)
        else:
            print 'service stopping not restarting Minecraft'
            self.stopping_deferred.callback(None)


run_dir = os.path.dirname(__file__)

application = service.Application('minecraft')
minecraft = MinecraftService(run_dir)
minecraft.setServiceParent(application)
