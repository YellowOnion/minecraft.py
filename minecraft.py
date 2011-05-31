print 'importing twisted'
from twisted.application import internet, service
from twisted.internet import reactor, protocol, defer, utils
from twisted.protocols import basic
from twisted.python import components

from zope.interface import Interface, implements

print 'importing os'
import os, re, random as r, shlex, time


class LineEventer(basic.LineReceiver):

    delimiter = '\n'
    service = None
    cmd_deffered = None
    
    def connectionMade(self):
        self.ops = [ x[:-1].lower() for x in open(os.path.join(run_dir, 'ops.txt'))\
                .readlines() ]
        print self.ops
        
        self.re_strip = re.compile(r'^\d{4}-\d{2}-\d{2} ' + \
                '\d{2}:\d{2}:\d{2} \[INFO\]' +\
                ' (.+)$')

        self.re_event = re.compile(r'^(\w+):? (.+)$')
        
        self.re_events = [
                (re.compile(r'issued server command: (.+)'), self.cmd),
#                (re.compile(r'Forcing save\.\.'), self.forcing_save),
                (re.compile(r'Save complete\.'), self.save_complete),
                (re.compile(r'lost connection: disconnect\.(.+)'), self.player_disconnect),
                (re.compile(r'.+logged in.+'), self.player_connect),
                ]

    def lineReceived(self, line):
        print line
        stripped = self.re_strip.search(line)
        if stripped:
            print 'stripped', stripped
            event = self.re_event.search(stripped.group(1))
            if event:
                print 'event', event
                for re, func in self.re_events:
                    match = re.search(event.group(2))
                    if match:
                        print 'match', match
                        def error(err):
                            err.printTraceback()
    
                        d = defer.Deferred()
                        d.addCallback(func, event.group(1).lower())
                        d.addErrback(error)
                        d.callback(match)
                        break

    def player_connect(self, match, player):
        self.service.player_connect(player)
        

    def player_disconnect(self, match, player):
        reason = match.group(1)
        self.service.player_disconnect(player, reason)
    
    def save_complete(self, match, player):
        self.service.save_complete()

    def cmd(self, match, player):
            if match:
                cmd_args = match.group(1)[:-1].split(' ', 1)
                try:
                    cmd, args = cmd_args
                except ValueError:
                    cmd, args = cmd_args[0], None
                

            c = getattr(self, 'cmd_' + cmd, None)
            if not c:
                builtins =  ['say', 'kick', 'ban', 'pardon', 'ban-ip',
                    'pardon-ip', 'op', 'deop', 'tp', 'give', 'tell',
                    'stop', 'save-all', 'save-off', 'save-on', 'list',
                    'time']
                if cmd not in builtins:
                    self.minecraft.tell(player, cmd + ' not found')
            else:
                d = c(player, args)

    def cmd_echo(self, player, args):
        if args:
            return defer.succeed(
                    self.minecraft.say(
                        player + ': ' + args))
        else:
            return defer.succeed(self.minecraft.say(
                    'well what do you want to echo?'))



    def cmd_backup(self, player, args):

        self.minecraft.say(player + ' issued command to backup')
        
        if player in self.ops:
            self.service.backup()
            
        
    
class DummyTransport:
    disconnecting = 0

transport = DummyTransport()

class MinecraftProtocol(protocol.ProcessProtocol):

    service = None
    empty = 1
    
    def connectionMade(self):
        self.output = LineEventer()
        self.output.minecraft = self
        self.output.service = self.service
        self.output.makeConnection(transport)

    def outReceived(self, data):
        self.output.dataReceived(data)
        self.empty = data[-1] == '\n'

    errReceived = outReceived

    def processEnded(self, reason):

        if not self.empty:
            self.output.dataReceived('\n')

        self.service.connectionLost()


    def say(self, *args):
        for msgs in args:
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

    def tell(self, player, *args):
        for msgs in args:
            for msg in msgs.split('\n'):
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
    minecraft = None
    stopping_deferred = None
    saving = None
    backingup = None
    playing = {}

    def __init__(self, run_dir):
        self.run_dir = run_dir

    def startService(self):
        service.Service.startService(self)
        self.active = 1
        reactor.callLater(0, self.start_minecraft)

    def stopService(self):
        service.Service.stopService(self)
        self.active = 0
        self.minecraft.stop()
        d = self.stopping_deferred = defer.Deferred()
        return d

    def start_minecraft(self):
        p = self.minecraft = MinecraftProtocol()
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
                reactor.callLater(0, self.start_minecraft)
        else:
            print 'service stopping not restarting Minecraft'
            self.stopping_deferred.callback(None)
        

    def backup(self):
        try:
            world = self.world
        except AttributeError:
               
            props_file = open(os.path.join(self.run_dir,
                'server.properties'))
            for line in props_file.readlines():
                if line.startswith('level-name'):
                    world = self.world = line.split('=')[1].strip()

        backup_dir = os.path.join(self.run_dir, 'backups')

        if not os.path.exists(backup_dir):
            os.mkdir(backup_dir)

        bu_dir_pre = os.path.join(backup_dir, 'minecraft_')

        self.saving = defer.Deferred()
        self.minecraft.save_off()
        self.minecraft.save_all()
            
        def finished(ignore):
            print 'tar exited with code', ignore
            self.saving = None
            self.backingup = None
            self.minecraft.say('backup complete')
            self.minecraft.save_on()

        def backup(ignore):
            if not self.backingup:
                print 'spawning tar'
                d = self.backingup = \
                        utils.getProcessOutputAndValue('/bin/tar',
                        args=['-cjf',
                            bu_dir_pre + \
                                    time.strftime('%F.%T%z') + \
                                    '.tar.bz2',
                            world],
                    env=os.environ,
                    path=self.run_dir)
                d.addCallbacks(finished, failed_backup)
            else:
                self.minecraft.say('already backing up!')

        def failed_backup(err):
            self.minecraft.say('backup failed')
            err.printTraceback()

        return self.saving.addCallbacks(backup, failed_backup)

    def save_complete(self):
        print 'function save_complete called'
        if self.saving:
            print 'saving deferred'
            self.saving.callback('done')           
        else:
            print 'saving deferred missing OH NO!'

    def player_disconnect(self, player, reason):
        print 'player disconnected:', player, reason
        self.playing[player].callback(reason)
        del self.playing[player]
        if not self.playing:
            self.backup()

    def player_connect(self, player):
        print 'player connected:', player
        self.playing[player] = defer.Deferred()


run_dir = os.path.dirname(__file__)

application = service.Application('minecraft')
minecraft = MinecraftService(run_dir)
minecraft.setServiceParent(application)
