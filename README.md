> This is not a complete solution yet.
> You still have to implement the Web Service yourself.


# Hetzner Cloud Console

Control the Hetzner Cloud from commandline.  Including access to the VM's console via noVNC web service.

You additionally need:

- Python3 and `git`
- A Hetzner Cloud API token
- A locally running MongoDB

You additionally need to implement:

- A Web Service where you serve the contents `www/` directory (following SymLinks)


## Usage

	git clone https://github.com/hilbix/hetzner-console.git
	cd hetzner-console
	git submodule update --init

Then run:

	./server.py setup

- Set the Hetzner Cloud API token
- Set the base URL `https://example.org/vnc/l.html?` where `https://example.org/vnc/l.html` serves `www/l.html`
- Change all the other parameters according to your needs.
- Note that this currently assumes that MongoDB is locally available where `server.py` runs
  - You can pass additional parameters to the MongoDB driver via `Server(param=val, param=val)`, see `main`
  - In future I might make this configurable via `setup`, too.
  - It's easy to add, though, but I haven't done it yet because I then need to test this feature somehow.

Then you can do:

	./server.py create vm1
	./server.py console vm1

The latter prints out the URL you need to open in the Browser.

- `xdg-open $(./server.py console vm1)` is your friend.

Please note that the URL is only valid for a limited time.

- The limitation is done by Hetzner for security purpose

From time to time do:

	./server.py sync

This reads the Hetzner Cloud status into the local database.

To see all possible commands, run

	./server.py help


## VNC access via Web

> This is implemented based on [noVNC](https://github.com/novnc/noVNC)

There is a folder `www/` which contains the web pages.
Just make it available somewhere in your web tree.

Be sure to include following in your CSP:

	connect-src 'self' wss://web-console.hetzner.cloud/

To access the VNC console, use following URL (prefixed on where you serve the `www/` directory):

	l.html?wss://URL#password

You can add something like `https://example.org/vnc/l.html?` as `Console baseurl` prefix in `./server.py setup`
such that the URL printed then directly opens the console.

To get an idea how to automate it, here is how I do it.  (This part currently is closed source,
because it belongs to a Web Service, which does all the access protection and stuff to protect access
to this web part.)

- When a Console is needed, the UI sends sends a `console NAME` request via the Web Service
  - How to do this, see `./server.py push console NAME` (see `cmd_push`)
  - This basically sets `cmd="console"` and `for="NAME"` into the MongoDB `cmd`-Table
  - Also this raises a flag that something must be processed by stuffing `msg="cmd"` into the MongoDB message queue
  - This way `server.py pull` (and `server.py wait`) will know there is something to do
- `autostart/hcloud-console.sh` then receives this request and runs `server.py console NAME`
- `server.py console NAME` then updates `url`, `auth` and `ts`
- The frontend (Browser) then polls for the change in `ts`, then it knows the `url` is fresh, and calls
  `l.html?wss://URL#AUTH` where `URL` is what is in `url` and `AUTH` is what is in `auth`

Why is this so complex?  It isn't.  It is just implementend a way to be able to keep everything neatly in separated parts.
So we have several parts which shall only do their thing and be able to run on different Servers and in different Security Zones (DMZ):

- The Browser presents some UI.  The UI is entirely your stuff.
- A Web Service processes the requests of the Browser.  Again, this is entirely your stuff.
  - The Web Service only talks to the Browser and to MongoDB
  - The Web Service does all the session handling, access protection and so on
  - I use [NginX secure link](http://nginx.org/en/docs/http/ngx_http_secure_link_module.html) for access protection
    to the `www/` directory, but this is not really neccessary, because there is nothing secret in it.
  - The Web Service is completely independent from this here.
  - It only needs to serve the static `www/` directory (which needs the likewise static `noVNC/` submodule),
    but it does not need to run `server.py` nor `autostart/hcloud-console.sh` itself,
    as these are coupled entirely via MongoDB
  - So you are completely free how to handle the Web part.
- MongoDB is the central coupling between the Middleware (this here) and the Web Service
  - MongoDB contains all the states and dynamic data, everything else can mostly stay static
  - There shall be no other side channels nor other communication needs
  - So this fits into a minimal setup
- The Middleware (this here) centrally processes everything, which needs to be handled on the Hetzner side
  - It only talks to Mongo DB and Hetzner, nothing else
  - As everything is funneled through this Middleware, it intrinsically does proper rate limiting
  - There are clear natural interfaces and separations, where you can adapt it to what you need or want to do
- Also the Browser does the direct connection to Hetzner
  - So no need to handle any WebSockets (which are used by noVNC) or this traffic at your side
  - Hence handling of WebSockets does not need to be a part of this solution here.
  - However, you still can use your own WebSeockets if you like.  It's just a change in the URL.
- We definitively do not want to do something like Polling in the Middleware nor Backend
  - The Middleware is notified of changes using a MongoDB feature.  So it does no busy waiting.
  - The Web Service just talks to MongoDB and quickly processes requests as usual.
  - No long-living Web connections are needed, as the UI can do polling until the Middleware has updated the URL.
  - If you want long living Web connections (AKA Web Push Service), you can implement that yourself,
    but this here currently has no direct support for this.
  - One could implement some backchannel for this, like the `msg` queue, but in the other direction.
  - However this makes things more complex, so I leave it away for now.

Well, if you closely look into `autostart/hcloud-console.sh`, you will see that there is a service cycle
which `poll`s Hetzner (`./server.py sync`).  That's a fallback to just make things more easy.
It is not really neccessary, as the UI can issue `sync NAME` requests to get things updated.

> Please note that I did not find a better way than to poll at the Hetzner side currently,
> as there seems to be no REST API or similar to allow to receive push notifications
> when some state changes on the Hetzner Cloud.  I think on something like what can be used
> with pipedream.com or similar, like what GitHub does on repository changes etc.
>
> So this is no limitation of this Middleware, but one of Hetzner's Cloud API
>
> Perhaps we could leverage this, as the Hetzner API offers a list of `Actions`,
> so we could poll those and create some subscription based system ourself.
>
> But this still means, we need something like a service cycle..


## Notification

There is a message queue.  It is in the queue collection (see `setup`).

Note that the size of the message queue in MongoDB is limited and it is not an exact LIFO-Queue.
So any number of signals can get lost!  It is just meant for notification,
such that you do not need to implement your own notification/waiting method.

	./server.py wait | while read -r msg; do while read -rt0.01 ignore; do :; done; process_signal; done

Then send a signal:

	./server.py put 'hello world'

Note that the contents of the signal can be ignored, as it is just arbitrary and if too many
signals are delivered some might get lost.  To have some reliable communication, you can do:

	while cmd="$(./server.py next)"; do process_cmd "$cmd"; done
	# Note that this loops until something catastropically fails, like MongoDB is stopped.

and then

	./server.py push cmd ARG		# there is exactly one single ARG

You can implement the complete loop as follows (this is nearly what `autostart/hcloud-console.sh` does):

	SERVICE_CYCLE=100;	# seconds
	./server.py wait |
	while	while read -rt0.01 ignore; do :; done;
		while cmd="$(./server.py pull)"; do process_cmd "$cmd"; done;
		read -rt "$SERVICE_CYCLE" msg || service_cycle_done_when_idle;
	do
		service_cycle_done_always;
	done;

> I think that's quite easy.


## Autostart

> You do not need that if you implement your own loop, see above.

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

Currently there is no example on how to link the Web and the Autostart part together, sorry,
because this is implemented on a closed source Web Service at my side.

Perhaps some example service might be added in future.  But I doubt I find the time myself.

The trick is to add commands to the `hetzner.cmd` collection and then trigger processing through
the `hetzner.msg` collection.  Afterwards the web page polls the `hetzner.vms` to see if the state
of the VM changes accordingly or the `URL` is changed (`ts`) to start a console etc.

As this all happens in the local MongoDB, there is a good separation between the Hetzner API and the webservice.

There is no direct reporting back, because this whole thing is meant to be highly fault tolerant and independent.
For example the connection from `server.py` to Hetzner might break any time, such that the
commands cannot be processed properly.  Also even if the commands are delivered, various things might break,
like some error in the infrastructure, a global power blackout, some bigger disaster earthquake,
Mars Attacks, plain everything.  One just cannot prepare in advance against all possibilities.

Hence doing it stateful and reliably would mean to implement a very complex and error prone retry logic
including some very cumbersome error processing, with trainloads of different states and incomprehensable interfaces,
and nothing even near some sane state diagram.

No way.  Hence all these logic is left up to the UI, which depends on your own Web Service.
There you should add some timer and retries including some error reporting to the user etc.

Also be prepared to create some additional cleanup processes for your backend, just in case things go sideways.
And things will go sideways.  Not neccessarily today, but sometime in the future if you have forgotten about it.

But all this should be quick customization which cannot be done in a generic way which suits all.
Only noVNC part is plain static HTML with JavaScript, so this is drop dead easy.

But which dynamic webservice do you prefer?  Node?  PHP?  Ruby?  Tomcat?  `awk`?  `bash`?

This is entirely up to you.  This here is just the Middleware which does the communication with Hetzner.


## FAQ

Install?

- Not needed.  Runs out of the box after `./server.py setup` was run
- This is not a complete ready-to-use solution, it is just a cornerstone, a ready to use Middleware.


MongoDB?

- Using MongoDB is just too easy, a complete no-brainer.  This is why it is supported first.
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
    so probably a Redis driver would be wise, but this is not implemented, sorry.
- MongoDB is supported for:
  - Debian Stretch (oldstable), Version 3.2
  - Ubuntu 18.04, Version 3.6
- MongDB is not supported for:
  - Debian Buster (stable) and later Debian releases
  - At least from the Debian Project themselves.
  - There seems to be a Buster version from MongoDB directly, I haven't tested it yet.
- MongoDB is reported to scale very well just in case you need it (I did not need such a scaling yet.)
- There is the MongoDB GitHub repository
  - If this dependency goes away, this probably means MongoDB goes away as well, then we need another driver anyway


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

