> This is not complete yet.
>
> You can control VMs, but accessing the Console with VNC currently is manual labour.

# Hetzner Cloud Console

Control the Hetzner Cloud from commandline.  Including access to the VM's console.


## Usage

	git clone https://github.com/hilbix/hetzner-console.git
	cd hetzner-console
	git submodule update --init

Have a local MongoDB running.

	./server.py setup

Then you can do:

	./server.py create vm1
	./server.py console vm1

The latter prints out the `wss://`-URL of Hetzner.

- Currently I have not found out, how to access this URL properly.
- This will hopefully be availabe very soon

From time to time do:

	./server.py sync

This reads the Hetzner Cloud status into the local database.

To see all possible commands, run

	./server.py help


## Web

There is a folder `www/` which contains the web pages.
Just make it available somewhere in your web tree.

Be sure to include following in your CSP:

	connect-src 'self' wss://web-console.hetzner.cloud/

To access the VNC console, use following URL:

	l.html?wss://URL#password

You can add something like `https://example.org/l.html?` as `Console baseurl` prefix in `./server.py setup`
such that the URL printed directly opens the console.


## Notification

There now is a message queue.  It is in the queue collection (see `setup`).

Note that the size of the message queue is limited and it is not an exact LIFO-Queue.
So any number of signals can get lost!  It is just meant for notification,
such that you do not need to implement your own notification/waiting method.

	./server.py wait | while read -r msg; do while read -rt0.01 ignore; do :; done; process_signal; done

Then

	./server.py put 'hello world'		# send a signal.  Just add a message to the collection


## Autostart

Subdirectory `autostart/` is my way on how to run something in the background.
For this it just needs to be linked to the user based `$HOME/autostart/` directory:

	mkdir -p ~/bin ~/autostart
	ln -s --relative autostart ~/autostart/hcloud-console

Then install [ptybuffer](https://github.com/hilbix/ptybuffer/):

	cd
	cd git
	git clone https://github.com/hilbix/ptybuffer.git
	cd ptybuffer
	git submodule update --init
	make
	cp ptybuffer script/autostart.sh ~/bin/
	{ crontab -l; echo '* * * * * bin/autostart.sh >/dev/null'; } | crontab -
	~/bin/autostart.sh

Now you can easily watch the running process with `socat`

	socat - unix:"/var/tmp/autostart/$LOGNAME/hcloud-console.sock"

or with something like [watcher](https://github.com/hilbix/watcher/):

	watcher.py "/var/tmp/autostart/$LOGNAME/"*.sock

Be sure to rotate `/var/tmp/autostart/*/*.log` and `/var/tmp/autostart/*.out` from time to time.
Alternatively you can modify `autostart.sh` to not output logs.  Whatever suits you best.  It's straight forward.


## UI

This part is currently missing, sorry.

Currently there is no example on how to link the Web and the Autostart part together, sorry,
because this is implemented on a closed source backend at my side.

Perhaps some example might be added in future.  But I doubt I find the time myself.

The trick is to add commands to the `hetzner.cmd` collection and then trigger processing through
the `hetzner.msg` collection.  Afterwards the web page polls the `hetzner.vms` to see if the state
of the VM changes accordingly or the `URL` show up to start a console etc.

As this all happens in the local MongoDB, there is a good separation between the Hetzner API and the webservice.

There is no direct reporting back, because this whole thing is meant to be highly fault tolerant.
For example the connection from `server.py` to Hetzner might break any time, such that the
commands cannot be processed properly.  Also even if the commands are delivered, various things might break,
like some error in the infrastructure, a global power blackout, some bigger disaster earthquake,
Mars Attacks, plain everything.  One just cannot prepare in advance against all possibilities.

Hence doing it stateful and reliably would mean to implement a very complex and error prone retry logic
including some very cumbersome error processing, with trainloads of different states and incomprehensable interfaces,
and nothing even near some sane state diagram.

No way.  Hence all these logic is left up to the UI, which depends on your own web service.
There you should add some timer and retries including some error reporting to the user etc.

Also be prepared to create some additional cleanup processes for your backend, just in case things go sideways.
And things will go sideways.  Not neccessarily today, but sometime in the future if you have forgotten about it.

But all this should be quick customization which cannot be done in a generic way which suits all.
Only noVNC part is plain static HTML with JavaScript, so this is drop dead easy.

But which dynamic webservice do you prefer?  Node?  PHP?  Ruby?  Tomcat?  `awk`?  `bash`?

(Not kidding, in the last Millenium I had a web service running which was implemented in `awk`.
And the CGI of my oldest web service was done over 20 yeare agoe in plain `bash` ..
and it is still up and running this code unchanged, [except for ShellShock](https://github.com/hilbix/shellshock)!)


## FAQ

Install?

- Not needed.  Runs out of the box after `./server.py setup` is completed

MongoDB?

- `sudo apt-get install mongodb` to install MongoDB should be all you need on a Debian derivative.
  - Be sure not to expose your MongoDB to any external network!  You have been warned.
  - The default install of Debian Stretch does only run MongoDB on localhost.  (I did not test others.)
  - This here currently assumes MongoDB is available on localhost without passwords.
  - A networked setup can be certainly be added easily if needed.
- MongoDB is used only as a Cache and Messaging gateway here
  - A "sync from scratch" feature is missing, but would be easy to add.
- MongoDB 3.2 has [tailable cursors](https://docs.mongodb.com/manual/reference/method/cursor.tailable/).
  - Other databases do not have such a feature, so it must be emulated (i. E. by using ZeroMQ, lockfiles, etc.)
  - An alternative to this would be [Redis BLPOP](https://redis.io/commands/blpop),
    so probably a Redis driver would be wise.
- MongoDB is supported for:
  - Debian Stretch (oldstable), Version 3.2
  - Ubuntu 18.04, Version 3.6
- MongDB is not supported for:
  - Debian Buster (stable) and later Debian releases
- Using MongoDB is just too easy, a complete no-brainer.  This is why it is supported first.
- MongoDB scales very well just in case you need it
- I can use the MongoDB GitHub repository, as if MongoDB goes away, ever, we need another driver anyway

noVNC?

- As noVNC is crucial for this repository, I use clone of the official repository
  - So if noVNC goes away, ever, we do not need to change anything
- If you clone this repository here you can easily make your clone independent of my GitHub user:
  - `git config --global url.https://github.com/novnc/noVNC.git.insteadOf https://github.com/hilbix/noVNC.git`
  - Adapt `https://github.com/novnc/noVNC.git` as needed
- **Therefor you never need to alter `.gitmodules`!**
  - This way PRs are possible easily and naturally without tweaks.
- Please note that `insteadOf` is a (mighty) `git` standard feature.
  - It's white magic.  Get used to it.  Now.

Contact?  Bug?  Contrib?

- Open Issue/PR on GitHub.  Eventually I listen.

License?

- This Works is placed under the terms of the Copyright Less License,  
  see file COPYRIGHT.CLL.  USE AT OWN RISK, ABSOLUTELY NO WARRANTY.
- Free as free beer, free speech and free baby.

