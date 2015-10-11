# ssh-agent-nanny
Ask the user for permission each time SSH is trying to access a stored key.

Before using this, consider using ProxyCommand instead. This proxy is meant to
make ssh-agent forwarding usable. Each time SSH will try to access stored key -
a dialog will popup showing process info and asking for permission.

In case someone hacks a server you're logged in - he won't be able to use your
keys without your consent. 

It's not 100% secure though - attacker can wait for you to use your key,
substitute his own request and sign it. Then your request would either fail or
cause another - double - dialog. With this in mind - it's quite ok.

It would be possible to ask for permission on specific keys, but it requires to
implement partial ssh-agent protocol support - possible in future if there's
interest.


# How to use
Simple usage instructions are in the comment at the top of the script.

In general - you start the script if it's not running already with a
SSH_AUTH_SOCK variable pointing at your real ssh-agent. Then you substitute
this variable to point at the new socket - $HOME/.ssh/agent-fw
