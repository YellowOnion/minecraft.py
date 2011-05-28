print 'importing twisted'
from twisted.internet import reactor, protocol, fdesc, task
from twisted.python import log

print 'importing os'
import os, re, random as r, shlex
run_dir = os.path.dirname(__file__)

class MinecraftServer(protocol.ProcessProtocol):
    def __init__(self):
        self.ops = [ x[:-1] for x in open(os.path.join(run_dir, 'ops.txt')).readlines() ]
        print self.ops
        self.chance = 5
        self.re_cmd = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[INFO\] (?:' + '|'.join(self.ops) + ') issued server command: (.+)$', re.I)

    def connectionMade(self):
        self.say('hello, world')
        
        self.day(False)

    def day(self, yesterday, today=None):
        def will_we_sleep_tonight():
            return r.choice([False] * (self.chance - 1) + [True])

        if today:
            self.say('night falls! Sunrise will be slow tonight. Hold close those dear, as it\'s not so safe any more.')
            reactor.callLater(510, self.day, today)
        else:
            if yesterday:
                tired = False
                reactor.callLater(690, self.day, today, tired)

            else:
                tired = will_we_sleep_tonight()
                self.time('set', -900) # in game ticks
                reactor.callLater(690, self.day, today, tired)
            

            if tired:
                self.say('Night will fall this evening.')

            else:
                self.say('Sunrise at night fall once again!')


    def outReceived(self, data):
        print data
        log.msg(data)
        self.chew(data)

    def chew(self, data):
        match = self.re_cmd.search(data)
        
        if match:
            print 'match found'
            cmd = shlex.split(match.group(1))
            try:
                {
                    'echo': self.say,
                    'chance': self.ch_chance,
                }[cmd[0]](*cmd[1:])
            except Exception, e:
                self.say(e.__repr__())
    def ch_chance(self, new_chance):
        try:
            self.chance = int(new_chance)
            self.say('chance for night fall has been changed')
        except:
            self.say('error! In command: chance')

    def say(self, msgs):
        for msg in msgs.split('\n'):
            self.transport.write('say ' + msg + '\n')

    def update(self):
        self.say('update needs downloading')

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
            self.transport.write('give ' + player + ' ' + str(id) + ' ' + str(num) + '\n')
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
    

        
print 'Creating Server interface'
ServerProtocol = MinecraftServer()
print 'spawning server'
reactor.spawnProcess(ServerProtocol,
    '/usr/bin/minecraft-server',
    args=['minecraft-server', 'nogui'],
    env=os.environ,
    path=run_dir,
    usePTY=True)
print 'actually do that stuff'
reactor.run()
