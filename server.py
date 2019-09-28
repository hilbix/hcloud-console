#!/usr/bin/env python3
#
# This Works is placed under the terms of the Copyright Less License,
# see file COPYRIGHT.CLL.  USE AT OWN RISK, ABSOLUTELY NO WARRANTY.
#
# This is not meant to be pretty.
# It is meant to be easy to use.
#
# Have a local MongoDB running.
# Do one time: ./server.py setup
#
# Afterwards you can do things like:
# ./server.py help		# see all the commands
# ./server.py create vm-1	# create a VM (warning! This costs money!)
# ./server.py settag some-vm	# mark some-vm to be managed by this
# ./server.py deltag vm-1	# make VM independent of this here
# ./server.py sync		# pull in the VM status in our DB


_APPNAME='hcloud-console CLI'
_VERSION='0.0.0'
_ENVNAME='HCLOUD_CONSOLE_CONF'		# ENV-var to take config from
_DEFCONF='~/.hcloud-console.conf'	# default config location

import os
import sys
import copy
import json
import time
import hcloud
import pymongo


def OOPS(*args):
	"""
	Housten .. you know the rest
	"""
	s	= ' '.join(['OOPS:']+[str(x) for x in args])
	print(s, file=sys.stderr)
	raise RuntimeError(s)


import zlib
import base64
import hashlib
import secrets
def scramble(s, scramble):
	"""
	A weird scrambler/descrambler.

	As we cannot see that scrambled values are OK,
	use gzip to protect their value.  Sort of.
	"""
	if s is None:
		return None
	if not scramble:
		kv	= s.split(' ')
		x	= base64.b64decode(kv[0])
		y	= base64.b64decode(kv[1])
		return zlib.decompress(bytes([c ^ y[i] for i,c in enumerate(x)])).decode()

	b	= zlib.compress(s.encode(), 1)
	k	= secrets.token_bytes(len(b))
#	for i,c in enumerate(b): print('b', str(i),str(c))
#	for i,c in enumerate(k): print('k', str(i),str(c))
	o	= bytes([c ^ k[i] for i,c in enumerate(b)])
	return base64.b64encode(o).decode()+' '+base64.b64encode(k).decode()


def progress(s):
	if s:
		sys.stderr.write(s)
		sys.stderr.flush()


class MongoConfig:
	CONF =	{
		'db':	['Mongo DB', 'hetzner'],
		'data':	['Mongo Data', 'vms'],
		'queue':['Mongo Queue', 'msg'],
		'cap':	['Mongo Queue Cap', '100000'],
		}

class Mongo:
	"""
	Wrapper to MongoDB
	"""

	@classmethod
	def configuration(klass):
		return MongoConfig

	def __init__(self, db, data, queue, cap, mongoargs={}):
		self.mo	= pymongo.MongoClient(**mongoargs)
		self.db	= self.mo[db]
		self.tb	= self.db[data]
		assert	self.tb
		try:
			assert int(cap)>9999, 'Mongo Queue Cap must be at least 10000, please run setup'
			self.q	= self.db.create_collection(queue, capped=True, size=int(cap))
			assert	self.q
		except pymongo.errors.CollectionInvalid:
			self.q	= self.db[queue]
			assert self.q.options()["capped"]

	def set(self, name, data):
		ob		= copy.copy(data)
		data['name']	= name
		res	= self.tb.replace_one({'name':name}, data, upsert=True)
		assert res
		return res

	def mix(self, name, **kw):
		res	= self.tb.update_one({'name':name}, {'$set': kw})
		assert res
		return res

	def check(self, name):
		return self.tb.find_one({'name':name})

	def get(self, name):
		res	= self.check(name)
		assert res
		return res

	def kill(self, name):
		res	= self.tb.delete_one({'name':name})
		assert res
		return res

	def list(self):
		for a in self.tb.find():
			yield a['name']

	def put(self, msg):
		res	= self.q.insert_one({'msg':msg})
		assert res
		return res

	def pull(self, debug=None):
		d1	= None if debug is None else debug[0] if len(debug)>0 else '.'
		d2	= None if debug is None else debug[1] if len(debug)>1 else 'x'
		d3	= None if debug is None else debug[2] if len(debug)>2 else '_'
		d4	= None if debug is None else debug[3] if len(debug)>3 else ':'
		d5	= None if debug is None else debug[4] if len(debug)>4 else '-'
		n	= self.q.estimated_document_count()
		if n:	n-=1
		id	= self.put(None).inserted_id	# create a dummy data with a given id for TAIL to work
		# self.q must be a capped collection
		c	= self.q.find(cursor_type=pymongo.CursorType.TAILABLE_AWAIT)
		while c.alive:
			for a in c:
				if id:
					if n and a['_id']!=id:
						progress(d5)
						# only skip past n entries
						n	-= 1
						continue
					progress(d4)
					id=None
					continue
				if a['msg'] is None:
					progress(d3)
				else:
					progress(d2)
					yield a['msg']
#			self.q.update_one({'_id':a['_id']},{'$set':{'msg':None}})	# impossible
			id=None
			progress(d1)
			time.sleep(0.1)

def props(o, props):
	"""
	extract propertis from object o into newly created dict

	props is a of mapping (dict) of index:property
	"""
	d	= {}
	for k,v in props.items():
		d[k]	= getattr(o,v)
	return d


def confirm(q):
	"""
	Easy confirmation question
	"""
	return 'y' == input(q+' [y/N]? ')


def inputn(a, b, q):
	"""
	Enter an integer in the range a..b
	"""
	x	= input(q+' (RETURN for no change)? ')
	if x=='':	return ''
	try:
		n	= int(x)
	except:
		return None
	return n if a<=n<=b else None


def select(entries):
	"""
	Let the user select some values
	"""
	while 1:
		n	= []
		for s in tabular(entries, head=True, countstart=1, countwidth=2, countsep=') '):
			print(s)
		a	= inputn(1, len(entries), 'select row')
		if a is not None: return a


def tabular(it, head=True, headdash=False, datadash=True, footdash=False, linedash=False, coldash=True, enddash=False, colspc=1, padleft=False, padright=False, countstart=0, countwidth=0, countsep=''):
	"""
	Yield lines which render some iterator which returns dicts into a tabular-like output.
	[{a:1,b:2},{a:3,b:4}] becomes something like

	a   b
	--+--
	1 ! 2
	3 ! 4
	"""

	cols	= []
	width	= {}
	data	= []
	for a in it:
		o={}
		for k,v in a.items():
			s	= str(v)
			t	= str(k)
			o[t]	= s
			if t not in cols:
				cols.append(t)
				width[t]	= 0
			width[t]	= max(width[t], len(s), len(t))
		data.append(o)

	def mkdash():
		if countwidth:
			yield ' '*(countwidth+len(countsep))
		if linedash:
			yield '+'
			yield '-'*colspc
		had=False
		for c in cols:
			if had:
				yield '-'*colspc
				if coldash:
					yield '+'
					yield '-'*colspc
			had	= True
			yield '-'*width[c]
		if enddash:
			yield '-'*colspc
			yield '+'

	def mkhead():
		if countwidth:
			yield ' '*(countwidth+len(countsep))
		if linedash:
			yield '!'
			yield ' '*colspc
		had=False
		for c in cols:
			if had:
				yield ' '*colspc
				if coldash:
					yield '!'
					yield ' '*colspc
			had	= True
			pl	= 0
			pr	= width[c]-len(c)
			if padleft==padright:
				pl	= pr//2
				pr	-= pl
			elif padleft:
				pl	= pr
				pr	= 0
			yield ' '*pl
			yield c
			yield ' '*pr
		if enddash:
			yield ' '*colspc
			yield '!'

	def mkrow(i,d):
		if countwidth:
			s	= str(i)
			if len(s)<countwidth:
				yield ' '*(countwidth-len(s))
			yield s
			yield countsep
		if linedash:
			yield '!'
			yield ' '*colspc
		had=False
		for c in cols:
			if had:
				yield ' '*colspc
				if coldash:
					yield '!'
					yield ' '*colspc
			had	= True
			pl	= 0
			pr	= width[c]-len(d[c])
			if padleft and padright:
				pl	= pr//2
				pr	-= pl
			elif padleft:
				pl	= pr
				pr	= 0
			yield ' '*pl
			yield d[c]
			yield ' '*pr
		if enddash:
			yield ' '*colspc
			yield '!'

	dash	= ''.join(mkdash())
	if headdash:	yield dash
	if head:	yield ''.join(mkhead())
	if datadash:	yield dash

	for i,a in enumerate(data):
		yield	''.join(mkrow(i+countstart, a))

	if footdash:	yield dash


class Config:
	"""
	Centralized data driven configuration
	"""

	def confs_(self, conf, prefix):
		"""
		Parse configuration of a class.
		This should work with the class, a configuration class or an instance of those.
		Separate configutation classes are good to separate the configuration properties from the class itself.

		conf.CONF = { 'configname': [ 'title', 'help' ] }	# mandatory
		conf.SCRAMBLE = [ 'configname' ]			# optional
		conf_configname(self, 'configname', value) must return some subclass with it's own config
		- klass.configuration() must return the configuration class (can be klass)
		get_configname(self, 'configname', value) returns an augmented value
		sel_configname(self, 'configname', helper) returns a list of possible options using the helper class
		hide_configname(self, 'configname', value) returns a string to hide this option from displaying in setup
		"""
		for a in getattr(conf, 'SCRAMBLE', []):
			self._hide[prefix+a]	= True
		for a in conf.CONF:
			self._confs[prefix+a]	= conf.CONF[a]
			self._base[prefix+a]	= conf

			# Do sub-configuration of instantiable classes
			k	= getattr(conf, 'conf_'+a, None)
			v	= self._conf.get(a)
			if k and v is not None:
				klass			= k(conf, a, v)
				self._klass[prefix+a]	= klass
				if klass:
					# pull in the sub-configuration for instantiation
					sub			= klass.configuration()
					if sub:
						self.confs_(sub, prefix+v+'_')
					self._sub[prefix+a]	= sub

	def confs(self):
		"""
		calculate self._confs to include all sub-configs, too
		"""
		self._confs	= {}
		self._base	= {}
		self._hide	= {}
		self._klass	= {}
		self._sub	= {}
		self.confs_(self._confclass, '')

	def __init__(self, confclass, config=None, configenv=_ENVNAME, **kw):
		"""
		Config(self.configuration(), **kw) where self.configuration() returns the config class (can be self)

		This ignores excess keywords, such that you can pass config=/configenv= easily
		"""
		self._confclass	= confclass
		self._config	= config or os.getenv(configenv) or _DEFCONF
		self.load()

	def load(self, config=None):
		self.changed	= False
		self.filename	= os.path.expanduser(config or self._config)
		assert self.filename
		try:
			with open(self.filename) as f:
				self._conf	= json.load(f)
		except FileNotFoundError:
			self._conf	= {}

		self.confs()

		for a in self._confs:
			if a not in self._conf:
				self._conf[a]	= None
		for a in self._conf:
			if self._conf[a] is None:
				self._conf['complete']	= None

		self._conf	= self.unscramble(self._conf)

	def save(self):
		"""
		write config as JSON
		"""
		with open(self.filename+'.tmp', "w+") as f:
			json.dump(self.scramble(copy.copy(self._conf)), f)
		os.rename(self.filename+'.tmp', self.filename)
		self.changed	= False

	def scramble(self, conf):
		"""
		Obfuscate config values a bit
		"""
		return self._scramble(True, conf)

	def unscramble(self, conf):
		"""
		Deobfuscate config
		"""
		return self._scramble(False, conf)

	def _scramble(self, mode, conf):
		"""
		Do the scrambling/unscrambling
		"""
		for a in self._hide:
			if a in conf and conf[a] is not None:
				conf[a]	= scramble(conf[a], mode)
		return conf

	def has(self, *args):
		"""
		check if given configs are present (not None)
		"""
		for a in args:
			if self._conf[a] is None:
				return False
		return True

	def set(self, k, v, key='name'):
		"""
		set a config value.

		If a dict is passed as value, use some key value instead.
		(We only support simple values in our config.)
		"""
		assert k in self._confs
		if isinstance(v, dict):		# This is black magic
			v	= v[key]
		if self._conf[k]==v: return
		self._conf[k]	= v
		self.changed	= True

	def ask(self, key, helper=None):
		"""
		Interactively as a config.

		If sel_CONF is defined for the given config,
		then fetch possible values from there for easy setup.
		"""
		c	= self._confs
		assert key in c
		print('key {}'.format(key))
		print('{}: {}'.format(*c[key]))
		print('current value: {}'.format(self.current(key)))
		b	= self._base[key]
		d	= getattr(b, 'sel_'+key, None)
		if d:
			d	= list(d(b, key, helper, self))
			if len(d) == 1:
				print('automatically selected:', d[0])
				return self.set(key, d[0])
			n	= select(d)
			if n:
				return self.set(key, d[n-1])

		v	= input('set to (RETURN for no change): ')
		if v:
			self.set(key, v)
			return True
		return False
	
	def save_interactive(self):
		"""
		Prompt for save (if changed only)
		"""
		if self.changed and confirm('data changed, save'):
			self.save()

	def setup_interactive(self, helper=None):
		"""
		A little interactive setup script

		For your convenience.  Because I hate difficult and long commandlines.
		"""
		once	= True
		while 1:
			self.confs()

			n=[]
			m=0
			for a in self._confs:
				n.append(a)
				m	= max(m, len(self._confs[a][0]))
			for i,a in enumerate(n):
				print('{n:2}) {c:{w}} {v}'.format(n=i+1, c=self._confs[a][0]+':', v=self.current(a), w=m+1))

			if once:
				self.save_interactive()
				once	= False
				had	= False
				for a in n:
					if self._conf[a] is None:
						had	= True
						print()
						if	self.ask(a, helper):
							once	= True
				if had:
					continue

			ans	= inputn(1, len(n), 'change entry')
			if ans is None: continue
			if not ans: break

			self.ask(n[ans-1], helper)

		self.save_interactive()

	def current(self, key):
		"""
		Access config such, that it hides values which should be kept hidden
		"""
		b	= self._base[key]
		a	= getattr(b, 'hide_'+key, None)
		return a(b, key, self._conf[key]) if a else self._conf[key]

	@property
	def access(self):
		"""
		access config as properties
		"""
		class acc:
			def __getitem__(ign, name):
				c	= self._conf[name]
				b	= self._base[name]
				return '' if c is None else getattr(b, 'get_'+name, lambda c,k,v: v)(b, name, c)
			def __getattribute__(me, name):
				return me[name]
		return acc()

	@property
	def instantiate(self):
		"""
		instantiate a subclass
		"""
		class acc:
			def __getitem__(ign, name):
				def run(**kw):
					"""
					Proxy function

					Can be used like the original classname,
					but also adds missing keywords from the default config.
					"""

					# Transfer missing keywords from config to the driver
					d	= self._conf[name]
					for a in self._sub[name].CONF:
						if a not in kw:
							kw[a]	= self._conf[d+'_'+a]
					# Instantiate the driver
					return self._klass[name](**kw)

				return run

			def __getattribute__(me, name):
				return me[name]

		return acc()

	def __getitem__(self, name):
		"""
		access config as dict
		"""
		return self._conf[name]

	def __setitem__(self, name, val):
		"""
		We do not support setting config this way (yet)
		But allow store of same value
		"""
		assert self._conf[name] == val


class ServerConfig:

	driver	= { 'mongo':Mongo }

	CONF =	{
		'token':	['API-token',		'Create one in project keys at hetzner.cloud'],
		'dc':		['Datacenter',		'Hetzner Datacenter to create VM in'],
		'typ':		['Default type',	 'VM type.  Example: cx11'],
		'os':		['Default OS',		'VM OS.  Example: ubuntu-18.04'],
		'label':	['VM label',		'Label to mark VM is managed.  Example: managed'],
		'prefix':	['VM name prefix',	'managed VMs prefix, - for none.  Example: m-'],
		'driver':	['Database driver',	'Currently there only is: mongo'],
		'console':	['Console baseurl',	'URL prefix to print for console, - for none'],
		'complete':	['Setup complete',	'leave empty if Setup is not complete'],
		}

	SCRAMBLE=['token']	# obfuscate these config values

	def dash_for_nothing(self, key, c):
		return '' if c=='-' else c

	def hidden(self, key, value):
		return '['+key+' not shown to keep it secure]'

	def conf_driver(self, key, value):
		"""
		get the driver config
		"""
		return getattr(self, key).get(value)

	hide_token	= hidden

	def get_driver(self, key, c):
		return self.driver.get(c)

	get_console	= dash_for_nothing
	get_prefix	= dash_for_nothing

	def sel_dc(self, key, helper, conf):
		if helper and conf.has('token'):
			yield from helper.cmd_dc()

	def sel_typ(self, key, helper, conf):
		if helper and conf.has('token', 'dc'):
			yield from helper.server_types(conf.access.dc)

	def sel_os(self, key, helper, conf):
		if helper and conf.has('token'):
			yield from helper.cmd_images()

	def sel_driver(self, key, helper, conf):
		for a in self.driver:
			yield a

	def sel_complete(self, key, helper, conf):
		yield {'name':None, key:'No'}
		yield {'name':'ok', key:'Yes'}


class Server:
	"""
	Hetzner Cloud Server API wrapper

	This combines the Hetzner Cloud API
	with a local database as a possible
	interface to some web service.

	This interface is currently not meant
	(tested) to run for a longer time.
	"""

	__APPNAME	= _APPNAME
	__APPVERS	= _VERSION

	def __init__(self, arg0=None, poll=10, **kw):
		"""
		Excess arguments are passed to the database driver
		"""
		self._conf	= Config(ServerConfig, **kw)
		self.__poll	= poll
		self.__db	= None
		self.__cli	= None
		self.__cache	= {}
		self.__arg0	= arg0
		self.__kw	= kw
		self.code	= 1

	@property
	def conf(self):
		return self._conf.access

	@property
	def need(self):
		"""
		do we need cmd_setup first?
		"""
		return None if self._conf.access.complete and self._conf.access.token else ('please first run: %s setup' % (self.__arg0,))

	@property
	def db(self):
		"""
		Get our database wrapper
		"""
		if self.__db:
			return self.__db
		self.__db	= self._conf.instantiate.driver(**self.__kw)
		assert self.__db
		return self.__db

	@property
	def cli(self):
		"""
		Access the Hetzner Cloud CLIent API
		"""
		if self.__cli:
			return self.__cli
		if len(self.conf.token)!=64:	OOPS('no token', len(self.conf['token']))
		self.__cli	= hcloud.Client(self.conf.token,
						application_name=self.__APPNAME,
						application_version=self.__APPVERS,
						poll_interval=self.__poll)
		assert self.__cli
		return self.__cli

	def servers(self, all=False):
		"""
		Get the list of all servers, possibly cached
		(This class ist not meant to be running for a long time)
		"""
		sel	= {} if all else { 'label_selector':self.conf.label+'=1' }
		return self.cache('servers', lambda: self.cli.servers.get_all(**sel))

	def cache(self, what, cb):
		"""
		Caching always is a good thing.

		However as we are supposed to be only short living,
		this perhaps is overkill today and a source of sorrow tomorrow ;)
		"""
		if what not in self.__cache:
			self.__cache[what]	= cb()
		return self.__cache[what]

	def byname(self, name):
		"""
		access a server by name

		For your safety this is limited to just the managed servers
		"""
		sv	= self.cli.servers.get_by_name(name)
		if sv is None:				OOPS('server missing on remote:', name)
		if self.conf.label not in sv.labels:	OOPS('server not managed:', name)
		return sv

	def cmd_setup(self):
		"""
		:	setup API-token etc
		"""
		self._conf.setup_interactive(self)
		yield 'ok'
		self.code	= 0

	def cmd_list(self):
		"""
		:	list all servers
		"""
		if	self.need:	yield self.need; return

		sv	= {}
		for a in self.servers(all=True):
			sv[a.name]	= { 'stat':a.status, 'date':str(a.created), 'id':a.id, 'labels':a.labels, 'ip4':a.public_net.ipv4.ip, 'ip6':a.public_net.ipv6.ip }
		for a in self.db.list():
			if a in sv:
				sv[a]['known'] = 'both'
			else:
				sv[a]	= { 'known':'local' }
		for a in sv:
			y	= {'name':a, 'known':'remote'}
			x	= sv[a]
			for b in x:
				y[b]	= x[b]
			yield y

		self.code	= 0

	def cmd_images(self):
		"""
		:	list available images
		"""
		if	not self.conf.token:	yield self.need; return
		for a in self.cli.images.get_all(type='system', sort='name'):
			yield { 'name':a.name, 'desc':a.description, 'os':a.os_flavor, 'v':a.os_version, 'id':a.id }
		self.code	= 0

	def cmd_dc(self):
		"""
		:	list available datacenters
		"""
		if	not self.conf.token:	yield self.need; return
		for a in self.cli.datacenters.get_all():
			yield { 'name':a.name, 'desc':a.description, 'id':a.id }
#			yield { 'name':a.name, 'desc':a.description, 'loc':self.location(a), 'types':self.server_types(a), 'id':a.id }
		self.code	= 0
		
	def cmd_reset(self, name):
		"""
		name:	unconditionally reboot the given server
		"""
		if	self.need:	yield self.need; return
		self.byname(name).reboot()
		yield "ok"
		self.code	= 0

	def cmd_force(self, name):
		"""
		name:	unconditionally stop the given server
		"""
		if	self.need:	yield self.need; return
		self.byname(name).power_off()
		yield "ok"
		self.code	= 0

	def cmd_stop(self, name):
		"""
		name:	try to stop the given server
		"""
		if	self.need:	yield self.need; return
		self.byname(name).shutdown()
		yield "ok"
		self.code	= 0

	def cmd_start(self, name):
		"""
		name:	start the given server
		"""
		if	self.need:	yield self.need; return
		self.byname(name).power_on()
		yield "ok"
		self.code	= 0

	def cmd_kill(self, name):
		"""
		name:	kill the given server
		"""
		if	self.need:	yield self.need; return
		self.byname(name).delete()
		self.db.kill(name)
		yield "ok"
		self.code	= 0
		
	def cmd_settag(self, name):
		"""
		name:	set tag on given server name
		"""
		if	self.need:	yield self.need; return
		sv	= self.cli.servers.get_by_name(name)
		lb	= copy.copy(sv.labels)
		lb[self.conf.label]="1"
		sv.update(labels=lb)
		yield "ok"
		self.code	= 0

	def cmd_deltag(self, name):
		"""
		name:	delete tag on given server name
		"""
		if	self.need:	yield self.need; return
		sv	= self.cli.servers.get_by_name(name)
		lb	= copy.copy(sv.labels)
		del lb[self.conf.label]
		sv.update(labels=lb)
		yield "ok"
		self.code	= 0

	def server_types(self, dc):
		"""
		Get the available server types in a datacenter
		"""
		if isinstance(dc, str):
			dc	= self.cli.datacenters.get_by_name(dc)
		for a in dc.server_types.available:
			ob	= {}					# 'prices'
			for i in ['name','description','cores','memory','disk','storage_type','cpu_type','id']:
				ob[i]	= getattr(a,i)
			yield props(a, {'name':'name', 'desc':'description', 'cpus':'cores', 'mem':'memory', 'gb':'disk', 'disk':'storage_type', 'cpu':'cpu_type', 'id':'id'})

	def location(self, a):
		"""
		Decode a location
		"""
		a	= a.location
		ret	= {}
		for i in ['name','description','country','city','latitude','longitude','network_zone','id']:
			ret[i]	= getattr(a,i)
		return ret

	def action(self, a):
		"""
		Decode an action
		"""
		ret	= {}
		for i in ['command','status','progress','resources']:
			ret[i]	= getattr(a,i)
		return ret

	def datacenter(self, dc):
		return { 'id':dc.id, 'name':dc.name, 'desc':dc.description, 'loc':self.location(dc) }

	def server_type(self, st, dc=None):
		return { 'id':st.id, 'name':st.name, 'desc':st.description, 'cpus':st.cores, 'mem':st.memory, 'gb':st.disk, 'disk':st.storage_type, 'cpu':st.cpu_type, 'price':self.price(st.prices, dc) }

	def price(self, pr, dc=None):
		if isinstance(dc, hcloud.datacenters.client.BoundDatacenter):
			dc	= dc.location.name
		vals	= []
		for a in pr:
			p	= a['price_monthly']['gross']
			if a['location'] == dc:
				return p
			vals.append(p)
		x	= min(vals)
		y	= max(vals)
		return x if x==y else [x,y]

	def image(self, im):
		return { 'id':im.id, 'name':im.name, 'desc':im.description, 'type':im.type, 'os':im.os_flavor, 'ver':im.os_version, 'fast':im.rapid_deploy, 'stat':im.status, 'labels':im.labels }

	def sync(self, name, sv, **kw):
		"""
		Pull Hetzner Cloud status into our local database
		(not vice versa!)
		"""
		old	= self.db.check(name) or {}
		data	= {
			'id':sv.id,
			'status':sv.status,
			'created':str(sv.created),
			'ip4':sv.public_net.ipv4.ip,
			'ip6':sv.public_net.ipv6.ip,
			'image': self.image(sv.image),
			'type': self.server_type(sv.server_type, sv.datacenter),
			'io': { 'in':sv.ingoing_traffic, 'out':sv.outgoing_traffic, 'max':sv.included_traffic },
			'dc': self.datacenter(sv.datacenter),
			'rescue': sv.rescue_enabled,
			'labels': sv.labels,
			'lock': sv.locked,
			'prot': sv.protection,
			}
		for a in data:
			old[a]	= data[a]
		for a in kw:
			old[a]	= kw[a]
		self.db.set(name, old)

	def cmd_sync(self, name=None):
		"""
		[name]:	sync local from remote data
			Without name: sync all known
		"""
		if	self.need:	yield self.need; return
		for a in [name] if name else self.db.list():
			sv	= self.cli.servers.get_by_name(a)
			if sv is None:
				yield (a, 'missing')
			else:
				self.sync(a, sv)
				yield a
		self.code	= 0

	def cmd_create(self, name, typ=None, os=None, dc=None):
		"""
		name [type [os [dc]]]:	create a server
		For the defaults see: setup
		"""
		if	self.need:	yield self.need; return
		if	not name.startswith(self.conf.prefix):	OOPS('server name must begin with', self.conf.prefix)
		if	self.db.check(name):			OOPS('known server', name)
		if	self.cli.servers.get_by_name(name):	OOPS('remote known server', name)
		self.db.set(name, {'stage':'new'})
		ok	= self.cli.servers.create(name,
						image=hcloud.images.domain.Image(name=os or self.conf.os),
						server_type=hcloud.server_types.domain.ServerType(name=typ or self.conf.typ),
						datacenter=hcloud.datacenters.domain.Datacenter(name=dc or self.conf.dc),
						labels={self.conf.label:"1"}
						)
		assert ok
		data	= [ self.action(ok.action) ]
		for a in ok.next_actions:
			data.append(self.action(a))
		sv	= ok.server
		assert sv
		self.sync(name, sv, pw=ok.root_password, stage='created', act=data)
		yield "ok"
		self.code	= 0

	def cmd_console(self, name):
		"""
		name:	update the console information
		"""
		if	self.need:	yield self.need; return
		con	= self.cli.servers.get_by_name(name).request_console()
		self.db.mix(name, url=con.wss_url, auth=con.password)
		yield self.conf.console+con.wss_url+'#'+con.password
		self.code	= 0

	def cmd_notify(self, message):
		"""
		message:	notify waiter with a message
		Note that messages are unreliable in the sense,
		that they might not reach any waiter
		"""
		self.db.put(message)
		yield "ok"

	def cmd_wait(self, *args):
		"""
		[debug]:	loop and dump new messages in the signal queue
		debug is a string which first 5 characters are used for progress output to stderr
		give empty to use standard progress, default: no progress
		"""
		yield from self.db.pull(*args)

	def cmd_help(self, cmd=None):
		"""
		[cmd]:	print help of command
		"""
		self.code	= 42
		if cmd:
			c	= getattr(self, 'cmd_'+cmd).__doc__.strip().split('\n')
			yield (cmd+' '+c[0])
			for a in c[1:]:
				yield "\t"+a.strip()
			return
		for a in dir(self):
			if a[0:4]=='cmd_':
				c	= getattr(self, a).__doc__.strip().split('\n',2)
				yield (a[4:]+' '+c[0])
		if	self.need:	yield self.need

	def cmd(self, *args):
		"""
		Run a command, probably from commandline
		"""
		if not args:
			OOPS('missing command, try: help')
		cmd	= args[0]
		args	= args[1:]
		def wrong(*args):
			OOPS('unknown command: '+cmd+' (try: help)')
		return getattr(self, 'cmd_'+cmd, wrong)(*args)

def main(arg0,*args):
	"""
	Simple variant of a commandline client

	Run a command and present the result
	"""
	sv	= Server(arg0=arg0)
	for a in sv.cmd(*args):
		print(a)
		sys.stdout.flush()
	return sv.code

if __name__ == '__main__':
	sys.exit(main(*sys.argv))

