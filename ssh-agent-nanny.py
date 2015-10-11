#!/usr/bin/env python3
"""
Example entry in .bashrc or .zshrc:

SMITH=~/.ssh-agent-nanny.py
SMITH_SOCKET=~/.ssh/agent-fw
SSH_AGENT=/usr/bin/ssh-agent
SSH_AGENT_ARGS="-s"
SSH_AGENT_CONFIG=~/.ssh-agent-cfg

# Start ssh-agent
if [ -f $SSH_AGENT_CONFIG ]; then
        source $SSH_AGENT_CONFIG > /dev/null
fi

if [ ! -S "$SSH_AUTH_SOCK" ]; then
        $SSH_AGENT $SSH_AGENT_ARGS >| $SSH_AGENT_CONFIG
        source $SSH_AGENT_CONFIG
        # This script calls ssh-add
        ~/.add_keys.sh
fi

# Start agent smith
if [ ! -S "$SMITH_SOCKET" ]; then
        $SMITH > /dev/null &|
fi

# Forward SSH questions to smith instead of agent
export SSH_AUTH_SOCK=$SMITH_SOCKET

"""

import os
import stat

from circuits import Debugger
from circuits import Component
from circuits.net.sockets import UNIXServer, UNIXClient
from circuits.net.events import write, connect, close
from circuits.tools import graph

def get_client_data(sock):
    "Create human-readable description for a PID"
    import socket
    import struct

    # Get client data
    creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize('3i'))
    pid, uid, gid = struct.unpack('3i',creds)

    with open('/proc/{}/cmdline'.format(pid), 'r') as f:
        cmdline = f.read()
        cmdline = cmdline.replace('\x00', ' ')
    return "'{}' (pid {})".format(cmdline, pid)

def show_msg(message):
    """
    Show dialog, get an answer. Could be tweaked to drop requirement on pymsgbox
    """
    import pymsgbox
    response = pymsgbox.confirm(message)
    if response == 'OK':
        return True
    else:
        return False

class ProxyClient(Component):
    """
    Handle connection to ssh-agent.
    """
    channel = "client"

    def init(self, sock, agent_socket, channel):
        """
        Args:
        sock - related client socket
        agent_socket - path to agent UNIX socket
        channel - unique client ID
        """
        self.agent_socket = agent_socket
        self.sock = sock

        print("Initialized a client with channel", channel)
        print("Opening unix client to socket {}".format(agent_socket))
        UNIXClient(channel=channel).register(self)

    def ready(self, sock):
        "Connect to SSH Agent"
        self.fire(connect(self.agent_socket))

    def disconnect(self, *args):
        self.fire(close(self.sock), self.parent.channel)

    def read(self, data):
        "Data read from ssh agent - pass back to the client always"
        self.fire(write(self.sock, data), self.parent.channel)

    def error(self, msg):
        import errno
        print("ERROR CAUGHT WHILE CONNECTING TO SSH AGENT", msg)
        print([k for k, v in vars(errno).items() if v == 111])


class ProxyServer(Component):
    channel = "server"

    def init(self, socket_fw, socket_agent):
        self.socket_agent = socket_agent
        self.socket_fw = socket_fw

        self.client_count = 0
        self.clients = {}
        UNIXServer(self.socket_fw).register(self)
        os.chmod(socket_fw, stat.S_IRUSR | stat.S_IWUSR)

    def connect(self, sock):
        # Describe client somehow
        client_desc = get_client_data(sock)

        # Display blocking popup

        ret = show_msg("Client {} is attempting to connect to ssh-agent".format(client_desc))
        if ret is False:
            # Disconnect this client
            sock.close()
            print("Dropping connection - denied")
            return
        print("Accepted client")

        # Create client object, connect to agent
        channel = 'client_{}'.format(self.client_count)
        self.client_count += 1

        client = ProxyClient(sock, self.socket_agent,
                             channel=channel)
        client.register(self)
        self.clients[sock] = client

        #print("GRAPH AFTER CLIENT CONNECTED")
        #print(graph(self.root))

    def disconnect(self, sock):
        "Disconnect client"
        client = self.clients.get(sock)
        if client is not None:
            client.unregister()
            del self.clients[sock]

    def read(self, sock, data):
        client = self.clients[sock]
        self.fire(write(data), client.channel)


def main():
    socket_agent = os.environ['SSH_AUTH_SOCK']
    socket_fw = os.path.join(os.environ['HOME'],
                             '.ssh',
                             'agent-fw')

    if not os.path.exists(socket_agent):
        print("Unable to find agent socket", agent_socket)
        return

    try:
        app = ProxyServer(socket_fw, socket_agent)
        #Debugger().register(app)
        app.run()
    finally:
        os.unlink(socket_fw)

if __name__ == "__main__":
    main()
