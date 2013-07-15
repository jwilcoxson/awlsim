# -*- coding: utf-8 -*-
#
# AWL simulator - CPU call stack
# Copyright 2012-2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2.
#

from awlsim.datatypes import *
from awlsim.blocks import *
from awlsim.statusword import *
from awlsim.parameters import *
from awlsim.objectcache import *
from awlsim.util import *


class CallStackElem(object):
	"Call stack element"

	localdataCache = ObjectCache(lambda cpu:
		[ LocalByte()
		  for _ in range(cpu.specs.nrLocalbytes) ]
	)

	@classmethod
	def resetCache(cls):
		cls.localdataCache.reset()

	def __init__(self, cpu, block, instanceDB=None,
		     interfaceDB=None, parameters=()):
		(self.cpu,
		 self.status,
		 self.parenStack,
		 self.ip,
		 self.localdata,
		 self.block,
		 self.insns,
		 self.labels,
		 self.instanceDB,
		 self.interfaceDB) = (
			cpu,
			S7StatusWord(),
			[],
			0,
			self.localdataCache.get(cpu),
			block,
			block.insns,
			block.labels,
			instanceDB,
			interfaceDB if interfaceDB else instanceDB,
		)

		# Handle parameters
		self.__outboundParams = []
		if parameters:
			blockInterface, interfaceDB, structInstance, callByRef_Types =\
				block.interface, \
				self.interfaceDB, \
				self.interfaceDB.structInstance, \
				BlockInterface.callByRef_Types
			for param in parameters:
				if param.isOutbound(blockInterface):
					# This is an outbound parameter.
					self.__outboundParams.append(param)
				if param.isInbound(blockInterface):
					# This is an inbound parameter.
					# Transfer data into DBI
					structField = param.getLvalueStructField(interfaceDB)
					if structField.dataType.type in callByRef_Types:
						data = param.rvalueOp.value.byteOffset
					else:
						data = cpu.fetch(param.rvalueOp)
					structInstance.setFieldData(structField, data)

	# Transfer data out of DBI
	def handleOutParameters(self):
		if self.__outboundParams:
			cpu, interfaceDB, structInstance =\
				self.cpu, \
				self.interfaceDB, \
				self.interfaceDB.structInstance
			for param in self.__outboundParams:
				cpu.store(
					param.rvalueOp,
					structInstance.getFieldData(param.getLvalueStructField(interfaceDB))
				)

	def destroy(self):
		# Only put it back into the cache, if the size didn't change.
		if len(self.localdata) == self.cpu.specs.nrLocalbytes:
			self.localdataCache.put(self.localdata)

	def __repr__(self):
		return str(self.block)
