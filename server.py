#!/usr/bin/env python3

_APPNAME='hcloud-console CLI'
_VERSION='0.0.0'
_ENVNAME='HCLOUD_CONSOLE_CONF'
_DEFCONF='~/.hcloud-console.conf'

import os
import sys
import copy
import json
import hcloud
import pymongo


def OOPS(*args):
	s	= ' '.join(['OOPS:']+[str(x) for x in args])
	print(s, file=sys.stderr)
	raise RuntimeError(s)


import zlib
import base64
import hashlib
import secrets
def scramble(s, scramble):
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


class Mongo:
	"""
	Driver for MongoDB
	"""

	@classmethod
	def conf(self):
		return {
			'db':['Mongo DB', 'hetzner'],
			'table':['Mongo Table', 'vms']
			}

	def __init__(self, db, table, mongoargs={}):
		self.mo	= pymongo.MongoClient(**mongoargs)
		self.db	= self.mo[db]
		self.tb	= self.db[table]
		assert self.tb

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
	return 'y' == input(q+' [y/N]? ')


def inputn(a, b, q):
	x	= input(q+' (RETURN for no change)? ')
	if x=='':	return ''
	try:
		n	= int(x)
	except:
		return None
	return n if a<=n<=b else None


def select(entries):
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
	drivers	= { 'mongo':Mongo }
	CONF =	{
		'token':	['API-token',		'Create one in project keys at hetzner.cloud'],
		'dc':		['Datacenter',		'Hetzner Datacenter to create VM in'],
		'typ':		['Default type',	 'VM type.  Example: cx11'],
		'os':		['Default OS',		'VM OS.  Example: ubuntu-18.04'],
		'label':	['VM label',		'Label to mark VM is managed.  Example: managed'],
		'prefix':	['VM name prefix',	'created VMs get this prefix.  Example: m-'],
		'driver':	['Database driver',	'Currently there only is: mongo'],
		'console':	['Console baseurl',	'URL prefix to print for console, - for none'],
		'complete':	['Complete?',		'leave empty if Setup is not complete'],
		}

	def confs(self):
		self._confs	= {}
		for a in self.CONF:
			self._confs[a]	= self.CONF[a]
			p	= getattr(self, 'conf_'+a, None)
			if p:
				p(a)
	
	def conf_driver(self, i):
		"""
		Proxy to join driver config with our config
		"""
		if i not in self._conf:		return
		d	= self._conf[i]
		if d not in self.drivers:	return
		for k,v in self.drivers[d].conf().items():
			self._confs[d+'-'+k]	= v

	def __init__(self, config=None, env=_ENVNAME, **kw):
		self.changed	= False
		if config is None:
			config	= os.getenv(env)
			if config is None:
				config	= _DEFCONF
		self.filename	= os.path.expanduser(config)
		assert self.filename
		try:
			with open(self.filename) as f:
				self._conf	= self.unscramble(json.load(f))
		except FileNotFoundError:
			self._conf	= {}

		self.confs()
		for a in self._confs:
			if a not in self._conf:
				self._conf[a]	= None

	@property
	def driver(self):
		"""
		Database driver proxy.

		Can be used like the original driver,
		but also adds missing keywords from the default config.
		"""
		def run(**kw):
			# Transfer missing keywords from config to the driver
			d	= self._conf['driver']
			c	= self.drivers[d]
			for a in c.conf():
				if a not in kw:
					kw[a]	= self._conf[d+'-'+a]
			# Instantiate the driver
			return c(**kw)
		return run

	def save(self):
		with open(self.filename+'.tmp', "w+") as f:
			json.dump(self.scramble(copy.copy(self._conf)), f)
		os.rename(self.filename+'.tmp', self.filename)
		self.changed	= False

	def scramble(self, conf):
		return self._scramble(True, conf)

	def unscramble(self, conf):
		return self._scramble(False, conf)

	def _scramble(self, mode, conf):
		for a in ['token']:
			if a in conf and conf[a] is not None:
				conf[a]	= scramble(conf[a], mode)
		return conf

	def ok(self, *args):
		for a in args:
			if self._conf[a] is None:
				return False
		return True

	def set(self, k, v):
		assert k in self._confs
		if isinstance(v, dict):
			v	= v['name']
		if self._conf[k]==v: return
		self._conf[k]	= v
		self.changed	= True


	def ask(self, key, io=None):
		c	= self._confs
		assert key in c
		print('{}: {}'.format(*c[key]))
		print('current value: {}'.format(self._conf[key]))
		if getattr(self, 'sel_'+key, None):
			d	= list(getattr(self, 'sel_'+key)(io))
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
		if self.changed and confirm('data changed, save'):
			self.save()

	def setup_interactive(self, io=None):
		once	= True
		while 1:
			self.confs()

			n=[]
			m=0
			for a in self._confs:
				n.append(a)
				m	= max(m, len(self._confs[a][0]))
			for i,a in enumerate(n):
				print('{n:2}) {c:{w}} {v}'.format(n=i+1, c=self._confs[a][0]+':', v=self._conf[a], w=m+1))

			if once:
				self.save_interactive()
				once	= False
				had	= False
				for a in n:
					if self._conf[a] is None:
						had	= True
						print()
						if	self.ask(a, io):
							once	= True
				if had:
					continue

			ans	= inputn(1, len(n), 'change entry')
			if ans is None: continue
			if not ans: break

			self.ask(n[ans-1], io)

		self.save_interactive()

	@property
	def access(self):
		class acc:
			def __getitem__(ign, name):
				return '' if self._conf[name] is None else self._conf[name]
			def __getattribute__(me, name):
				return me[name]
		return acc()

	def __getitem__(self, name):
		return self._conf[name]

	def __setitem__(self, name, val):
		assert self._conf[name] == val

	def sel_dc(self, io):
		if io and self.ok('token'):
			yield from io.cmd_dc()

	def sel_typ(self, io):
		if io and self.ok('token', 'dc'):
			yield from io.server_types(self._conf['dc'])

	def sel_os(self, io):
		if io and self.ok('token'):
			yield from io.cmd_images()

	def sel_driver(self, io):
		for a in self.drivers:
			yield a

	def sel_ref(self, io):
		return conf['label']

	def sel_complete(self, io):
		yield {'name':None, 'complete':'No'}
		yield {'name':'ok', 'complete':'Yes'}

class Server:
	__APPNAME	= _APPNAME
	__APPVERS	= _VERSION

	def __init__(self, arg0=None, poll=10, **kw):
		self._conf	= Config(**kw)
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
		return None if self._conf.access.complete and self._conf.access.token else ('please first run: %ssetup' % (self.__arg0,))

	@property
	def db(self):
		if self.__db:
			return self.__db
		self.__db	= self._conf.driver(**self.__kw)
		assert self.__db
		return self.__db

	@property
	def cli(self):
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
		sel	= {} if all else { 'label_selector':self.conf.label+'=1' }
		return self.cache('servers', lambda: self.cli.servers.get_all(**sel))

	def byname(self, name):
		sv	= self.cli.servers.get_by_name(name)
		if self.conf.label not in sv.labels:	OOPS('server not managed:', name)
		return sv

	def cache(self, what, cb):
		if what not in self.__cache:
			self.__cache[what]	= cb()
		return self.__cache[what]

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
		if self.need:	yield self.need; return

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
		if not self.conf.token:	yield self.need; return
		for a in self.cli.images.get_all(type='system', sort='name'):
			yield { 'name':a.name, 'desc':a.description, 'os':a.os_flavor, 'v':a.os_version, 'id':a.id }
		self.code	= 0

	def cmd_dc(self):
		"""
		:	list available datacenters
		"""
		if not self.conf.token:	yield self.need; return
		for a in self.cli.datacenters.get_all():
			yield { 'name':a.name, 'desc':a.description, 'id':a.id }
#			yield { 'name':a.name, 'desc':a.description, 'loc':self.location(a), 'types':self.server_types(a), 'id':a.id }
		self.code	= 0
		
	def cmd_reset(self, name):
		"""
		name:	unconditionally reboot the given server
		"""
		if self.need:	yield self.need; return
		self.byname(name).reboot()
		yield "ok"
		self.code	= 0

	def cmd_force(self, name):
		"""
		name:	unconditionally stop the given server
		"""
		if self.need:	yield self.need; return
		self.byname(name).power_off()
		yield "ok"
		self.code	= 0

	def cmd_stop(self, name):
		"""
		name:	try to stop the given server
		"""
		if self.need:	yield self.need; return
		self.byname(name).shutdown()
		yield "ok"
		self.code	= 0

	def cmd_start(self, name):
		"""
		name:	start the given server
		"""
		if self.need:	yield self.need; return
		self.byname(name).power_on()
		yield "ok"
		self.code	= 0

	def cmd_kill(self, name):
		"""
		name:	kill the given server
		"""
		if self.need:	yield self.need; return
		self.byname(name).delete()
		self.db.kill(name)
		yield "ok"
		self.code	= 0
		
	def cmd_settag(self, name):
		"""
		name:	set tag on given server name
		"""
		if self.need:	yield self.need; return
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
		if self.need:	yield self.need; return
		sv	= self.cli.servers.get_by_name(name)
		lb	= copy.copy(sv.labels)
		del lb[self.conf.label]
		sv.update(labels=lb)
		yield "ok"
		self.code	= 0

	def server_types(self, dc):
		if isinstance(dc, str):
			dc	= self.cli.datacenters.get_by_name(dc)
		for a in dc.server_types.available:
			ob	= {}					# 'prices'
			for i in ['name','description','cores','memory','disk','storage_type','cpu_type','id']:
				ob[i]	= getattr(a,i)
			yield props(a, {'name':'name', 'desc':'description', 'cpus':'cores', 'mem':'memory', 'gb':'disk', 'disk':'storage_type', 'cpu':'cpu_type', 'id':'id'})

	def location(self, a):
		a	= a.location
		ret	= {}
		for i in ['name','description','country','city','latitude','longitude','network_zone','id']:
			ret[i]	= getattr(a,i)
		return ret

	def action(self, a):
		ret	= {}
		for i in ['command','status','progress','resources']:
			ret[i]	= getattr(a,i)
		return ret

	def sync(self, name, sv, **kw):
		old	= self.db.check(name) or {}
		data	= { 'id':sv.id, 'status':sv.status, 'created':str(sv.created), 'ip4':sv.public_net.ipv4.ip, 'ip6':sv.public_net.ipv6.ip, 'dc':{ 'id':sv.datacenter.id, 'name':sv.datacenter.name, 'desc':sv.datacenter.description, 'loc':self.location(sv.datacenter) } }
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
		if self.need:	yield self.need; return
		for a in [name] if name else self.db.list():
			sv	= self.byname(a)
			self.sync(a, sv)
			yield a
		self.code	= 0

	def cmd_create(self, name, dc=None, os=None, typ=None):
		"""
		name [dc [os [type]]]:	create a server
		For the defaults see: config
		"""
		if self.need:	yield self.need; return
		if not name.startswith(self.conf.prefix):	OOPS('server name must begin with', self.conf.prefix)
		if	self.db.check(name):			OOPS('known server', name)
		if	self.cli.servers.get_by_name(name):	OOPS('remote known server', name)
		self.db.set(name, {'stage':'new'})
		ok	= self.cli.servers.create(name,
						image=hcloud.images.domain.Image(name=os or self.__os),
						server_type=hcloud.server_types.domain.ServerType(name=typ or self.__typ),
						datacenter=hcloud.datacenters.domain.Datacenter(name=dc or self.__dc),
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
		if self.need:	yield self.need; return
		con	= self.cli.servers.get_by_name(name).request_console()
		self.db.mix(name, url=con.wss_url, auth=con.password)
		yield (self.conf.console if self.conf.console!='-' else '')+con.wss_url+'#'+con.password
		self.code	= 0

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
		if self.need:	yield self.need

	def cmd(self, *args):
		if not args:
			OOPS('missing command, try: help')
		cmd	= args[0]
		args	= args[1:]
		def wrong(*args):
			OOPS('unknown command: '+cmd+' (try: help)')
		return getattr(self, 'cmd_'+cmd, wrong)(*args)

def main(arg0,*args):
	sv	= Server(arg0=arg0)
	for a in sv.cmd(*args):
		print(a)
	return sv.code

if __name__ == '__main__':
	sys.exit(main(*sys.argv))

