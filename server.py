#!/usr/bin/env python3

_APPNAME='hcloud-console CLI'
_VERSION='0.0.0'

import os
import sys
import copy
import json
import hcloud
import pymongo


def OOPS(*args):
	s	= ' '.join(['OOPS:']+[str(x) for x in args])
	print(s, file=sys.stderr)
	return RuntimeError(s)

class Mo:
	def __init__(self, db='hetzner', table='vms'):
		self.mo	= pymongo.MongoClient()
		self.db	= self.mo[db]
		self.tb	= self.db[table]
		assert self.tb

	def set(self, name, data):
		ob		= copy.copy(data)
		data['name']	= name
		res	= self.tb.replace_one({'name':name}, data, upsert=True)
		assert res
		return res

	def check(self, name):
		return self.tb.find_one({'name':name})

	def get(self, name):
		res	= check(name)
		assert res
		return res

	def kill(self, name):
		res	= self.tb.delete_one({'name':name})
		assert res
		return res

	def list(self):
		for a in self.tb.find():
			yield a['name']

class Server:
	__APPNAME	= _APPNAME
	__APPVERS	= _VERSION

	def __init__(self, apikey='~/.api.ignore', poll=10, tag='managed', arg0=None, **kw):
		with open(os.path.expanduser(apikey)) as f:
			self.token	= f.readline().strip()
			self.__dc	= f.readline().strip()
			self.__os	= f.readline().strip()
			self.__typ	= f.readline().strip()
		assert self.token
		self.__poll	= poll
		self.__mo	= None
		self.__cli	= None
		self.__cache	= {}
		self.__arg0	= arg0
		self.__kw	= kw
		self.tag	= tag

	@property
	def mo(self):
		if self.__mo:
			return self.__mo
		self.__mo	= Mo(**self.__kw)
		assert self.__mo
		return self.__mo

	@property
	def cli(self):
		if self.__cli:
			return self.__cli
		if len(self.token)!=64:	raise OOPS('no token', len(self.token))
		self.__cli	= hcloud.Client(self.token,
						application_name=self.__APPNAME,
						application_version=self.__APPVERS,
						poll_interval=self.__poll)
		assert self.__cli
		return self.__cli

	def servers(self, all=False):
		sel	= {} if all else { 'label_selector':self.tag+'=1' }
		return self.cache('servers', lambda: self.cli.servers.get_all(**sel))

	def byname(self, name):
		sv	= self.cli.servers.get_by_name(name)
		if self.tag not in sv.labels:
			raise OOPS('server not managed:', name)
		return sv

	def cache(self, what, cb):
		if what not in self.__cache:
			self.__cache[what]	= cb()
		return self.__cache[what]

	def cmd_list(self):
		"""
		:	list all servers
		"""
		sv	= {}
		for a in self.servers(all=True):
			sv[a.name]	= { 'stat':a.status, 'date':str(a.created), 'id':a.id, 'labels':a.labels, 'ip4':a.public_net.ipv4.ip, 'ip6':a.public_net.ipv6.ip }
		for a in self.mo.list():
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

	def cmd_images(self):
		"""
		:	list available images
		"""
		for a in self.cli.images.get_all(type='system', sort='name'):
			yield { 'name':a.name, 'desc':a.description, 'os':a.os_flavor, 'v':a.os_version, 'id':a.id }

	def cmd_dc(self):
		"""
		:	list available datacenters
		"""
		for a in self.cli.datacenters.get_all():
			yield { 'name':a.name, 'desc':a.description, 'id':a.id }
#			yield { 'name':a.name, 'desc':a.description, 'loc':self.location(a), 'types':self.server_types(a), 'id':a.id }
		
	def cmd_reset(self, name):
		"""
		name:	unconditionally reboot the given server
		"""
		self.byname(name).reboot()
		yield "ok"

	def cmd_force(self, name):
		"""
		name:	unconditionally stop the given server
		"""
		self.byname(name).power_off()
		yield "ok"

	def cmd_stop(self, name):
		"""
		name:	try to stop the given server
		"""
		self.byname(name).shutdown()
		yield "ok"

	def cmd_start(self, name):
		"""
		name:	start the given server
		"""
		self.byname(name).power_on()
		yield "ok"

	def cmd_kill(self, name):
		"""
		name:	kill the given server
		"""
		self.byname(name).delete()
		self.mo.kill(name)
		yield "ok"
		
	def cmd_settag(self, name):
		"""
		name:	set tag on given server name
		"""
		sv	= self.cli.servers.get_by_name(name)
		lb	= copy.copy(sv.labels)
		lb[self.tag]="1"
		sv.update(labels=lb)
		yield "ok"

	def cmd_deltag(self, name):
		"""
		name:	delete tag on given server name
		"""
		sv	= self.cli.servers.get_by_name(name)
		lb	= copy.copy(sv.labels)
		del lb[self.tag]
		sv.update(labels=lb)
		yield "ok"

	def server_types(self, a):
		ret	= []
		for a in a.server_types.available:
			ob	= {}
			for i in ['name','description','cores','memory','disk','prices','storage_type','cpu_type','id']:
				ob[i]	= getattr(a,i)
			ret.append(ob)
		return ret

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
		old	= self.mo.check(name) or {}
		data	= { 'id':sv.id, 'status':sv.status, 'created':str(sv.created), 'ip4':sv.public_net.ipv4.ip, 'ip6':sv.public_net.ipv6.ip, 'dc':{ 'id':sv.datacenter.id, 'name':sv.datacenter.name, 'desc':sv.datacenter.description, 'loc':self.location(sv.datacenter) } }
		for a in data:
			old[a]	= data[a]
		for a in kw:
			old[a]	= kw[a]
		self.mo.set(name, old)

	def cmd_sync(self, name):
		"""
		name:	sync local from remote data
		"""
		sv	= self.byname(name)
		self.sync(name, sv)
		yield "ok"

	def cmd_create(self, name, dc='fsn1-dc14', os='ubuntu-18.04', typ='cx11'):
		"""
		name [dc [os [type]]]:	create a server
		The defaults are defined in the api-key
		"""
		name	= self.tag+name
		if	self.mo.get(name):	OOPS('known server', name)
		if	self.cli.servers.get_by_name(name): OOPS('remote known server', name)
		self.mo.set(name, {'stage':'new'})
		ok	= self.cli.servers.create(name,
						image=hcloud.images.domain.Image(name=os or self.__os),
						server_type=hcloud.server_types.domain.ServerType(name=typ or self.__typ),
						datacenter=hcloud.datacenters.domain.Datacenter(name=dc or self.__dc),
						labels={self.tag:"1"}
						)
		assert ok
		data	= [ self.action(ok.action) ]
		for a in ok.next_actions:
			data.append(self.action(a))
		sv	= ok.server
		assert sv
		self.sync(name, sv, pw=ok.root_password, stage=created, act=data)
		yield "ok"

	def cmd_help(self, cmd=None):
		"""
		[cmd]:	print help of command
		"""
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

	def cmd(self, cmd, *args):
		def wrong(*args):
			yield 'unknown command: '+cmd+' (try: help)'
		return getattr(self, 'cmd_'+cmd, wrong)(*args)

def main(arg0,cmd,*args):
	lb	= Server(tag='vnc', arg0=arg0, db='vnc', table='sess')
	for a in lb.cmd(cmd, *args):
		print(a)
	return 0

if __name__ == '__main__':
	sys.exit(main(*sys.argv))

