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

> Currently this does not work.  See
> [Issue 1](https://github.com/hilbix/hcloud-console/issues/1#issuecomment-533910979)


## FAQ

Install?

- Not needed.  Runs out of the box

MongoDB?

- Be sure not to expose your MongoDB to other net than localhost!
- `sudo apt-get install mongodb` to install MongoDB should be all you need.
  - This works up for Debian Stretch, but Debian Buster no more includes MongoDB!
  - Ubuntu 18.04 still supports MongoDB
- It was just too easy to wrap it into MongoDB.
- You probably can create a Wrapper to other Databases yourself if you need that.

Contact?  Bug?  Contrib?

- Open Issue/PR on GitHub.  Eventually I listen.

License?

- This Works is placed under the terms of the Copyright Less License,  
  see file COPYRIGHT.CLL.  USE AT OWN RISK, ABSOLUTELY NO WARRANTY.
- Free as free beer, free speech and free baby.

