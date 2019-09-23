> This is not complete yet.
>
> You can control VMs, but accessing the Console with VNC currently does not work.

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

