# -*- coding: utf-8 -*-
#
# AWL simulator - operators
# Copyright 2012-2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2.
#

from awlstatusword import *
from util import *


class AwlOperator(object):
	# Operator types
	IMM		= 0	# Immediate value (constant)
	IMM_REAL	= 1	# Real
	IMM_S5T		= 2	# S5T immediate
	IMM_TIME	= 3	# T# immediate
	IMM_DATE	= 4	# D# immediate
	IMM_TOD		= 5	# TOD# immediate

	MEM_E		= 100	# Input
	MEM_A		= 101	# Output
	MEM_M		= 102	# Flags
	MEM_L		= 103	# Localstack
	MEM_DB		= 104	# Global datablock
	MEM_DI		= 105	# Instance datablock
	MEM_T		= 106	# Timer
	MEM_Z		= 107	# Counter
	MEM_PA		= 108	# Peripheral output
	MEM_PE		= 109	# Peripheral input

	MEM_STW		= 200	# Status word bit read
	MEM_STW_Z	= 201	# Status word "==0" read
	MEM_STW_NZ	= 202	# Status word "<>0" read
	MEM_STW_POS	= 203	# Status word ">0" read
	MEM_STW_NEG	= 204	# Status word "<0" read
	MEM_STW_POSZ	= 205	# Status word ">=0" read
	MEM_STW_NEGZ	= 206	# Status word "<=0" read
	MEM_STW_UO	= 207	# Status word "UO" read

	LBL_REF		= 300	# Label reference

	BLKREF_FC	= 400	# FC reference
	BLKREF_SFC	= 401	# SFC reference
	BLKREF_FB	= 402	# FB reference
	BLKREF_SFB	= 403	# SFB reference
	BLKREF_DB	= 404	# DB reference
	BLKREF_DI	= 405	# DI reference

	NAMED_LOCAL	= 500	# Named local reference (#abc)

	# Virtual operators used for debugging of the simulator
	VIRT_ACCU	= 1000	# Accu
	VIRT_AR		= 1001	# AR

	# TODO: Use AwlOffset
	def __init__(self, type, width, offset, bitOffset=0):
		self.type = type
		self.width = width
		self.offset = offset
		self.bitOffset = bitOffset
		self.labelIndex = None
		self.insn = None
		self.setExtended(False)

	def setInsn(self, newInsn):
		self.insn = newInsn

	def setExtended(self, isExtended):
		self.isExtended = isExtended

	@property
	def immediate(self):
		return self.offset

	@property
	def label(self):
		return self.offset

	def setLabelIndex(self, newLabelIndex):
		self.labelIndex = newLabelIndex

	def assertType(self, types, lowerLimit=None, upperLimit=None):
		if not isinstance(types, list) and\
		   not isinstance(types, tuple):
			types = [ types, ]
		if not self.type in types:
			raise AwlSimError("Operator is type is invalid")
		if lowerLimit is not None:
			if self.offset < lowerLimit:
				raise AwlSimError("Operator value too small")
		if upperLimit is not None:
			if self.offset > upperLimit:
				raise AwlSimError("Operator value too big")

	type2str = {
		MEM_STW_Z	: "==0",
                MEM_STW_NZ	: "<>0",
                MEM_STW_POS	: ">0",
                MEM_STW_NEG	: "<0",
                MEM_STW_POSZ	: ">=0",
                MEM_STW_NEGZ	: "<=0",
                MEM_STW_UO	: "UO",
	}

	type2prefix = {
		MEM_E		: "E",
		MEM_A		: "A",
		MEM_M		: "M",
		MEM_L		: "L",
		MEM_T		: "T",
		MEM_Z		: "Z",
	}

	def __repr__(self):
		try:
			return self.type2str[self.type]
		except KeyError as e:
			pass
		if self.type == self.IMM:
			if self.width == 16:
				return str(self.immediate)
			elif self.width == 32:
				return "L#" + str(self.immediate)
		if self.type == self.IMM_REAL:
			return str(dwordToPyFloat(self.immediate))
		elif self.type == self.IMM_S5T:
			return "S5T#" #TODO
		elif self.type == self.IMM_TIME:
			return "T#" #TODO
		elif self.type == self.IMM_DATE:
			return "D#" #TODO
		elif self.type == self.IMM_TOD:
			return "TOD#" #TODO
		elif self.type in (self.MEM_A, self.MEM_E,
				   self.MEM_M, self.MEM_L):
			pfx = self.type2prefix[self.type]
			if self.width == 1:
				return "%s %d.%d" %\
					(pfx, self.offset, self.bitOffset)
			elif self.width == 8:
				return "%sB %d" % (pfx, self.offset)
			elif self.width == 16:
				return "%sW %d" % (pfx, self.offset)
			elif self.width == 32:
				return "%sD %d" % (pfx, self.offset)
		elif self.type == self.MEM_DB:
			if self.width == 1:
				return "DBX %d.%d" % (self.offset, self.bitOffset)
			elif self.width == 8:
				return "DBB %d" % self.offset
			elif self.width == 16:
				return "DBW %d" % self.offset
			elif self.width == 32:
				return "DBD %d" % self.offset
		elif self.type == self.MEM_DI:
			if self.width == 1:
				return "DIX %d.%d" % (self.offset, self.bitOffset)
			elif self.width == 8:
				return "DIB %d" % self.offset
			elif self.width == 16:
				return "DIW %d" % self.offset
			elif self.width == 32:
				return "DID %d" % self.offset
		elif self.type == self.MEM_T:
			return "T %d" % self.offset
		elif self.type == self.MEM_Z:
			return "Z %d" % self.offset
		elif self.type == self.MEM_PA:
			if self.width == 8:
				return "PAB %d" % self.offset
			elif self.width == 16:
				return "PAW %d" % self.offset
			elif self.width == 32:
				return "PAD %d" % self.offset
		elif self.type == self.MEM_PE:
			if self.width == 8:
				return "PEB %d" % self.offset
			elif self.width == 16:
				return "PEW %d" % self.offset
			elif self.width == 32:
				return "PED %d" % self.offset
		elif self.type == self.MEM_STW:
			return "__STW " + S7StatusWord.nr2name[self.bitOffset]
		elif self.type == self.LBL_REF:
			return self.label
		elif self.type == self.BLKREF_FC:
			return "FC %d" % self.offset
		elif self.type == self.BLKREF_SFC:
			return "SFC %d" % self.offset
		elif self.type == self.BLKREF_FB:
			return "FB %d" % self.offset
		elif self.type == self.BLKREF_SFB:
			return "SFB %d" % self.offset
		elif self.type == self.BLKREF_DB:
			return "DB %d" % self.offset
		elif self.type == self.BLKREF_DI:
			return "DI %d" % self.offset
		elif self.type == self.NAMED_LOCAL:
			return "#%s" % self.offset
		elif self.type == self.VIRT_ACCU:
			return "__ACCU %d" % self.offset
		elif self.type == self.VIRT_AR:
			return "__AR %d" % self.offset
		assert(0)

	@classmethod
	def fetchFromByteArray(cls, array, operator):
		width, byteOff, bitOff =\
			operator.width, operator.offset, operator.bitOffset
		try:
			if width == 1:
				return array[byteOff].getBit(bitOff)
			elif width == 8:
				assert(bitOff == 0)
				return array[byteOff].get()
			elif width == 16:
				assert(bitOff == 0)
				return (array[byteOff].get() << 8) |\
				       array[byteOff + 1].get()
			elif width == 32:
				assert(bitOff == 0)
				return (array[byteOff].get() << 24) |\
				       (array[byteOff + 1].get() << 16) |\
				       (array[byteOff + 2].get() << 8) |\
				       array[byteOff + 3].get()
		except IndexError as e:
			raise AwlSimError("fetch: Operator offset out of range")
		assert(0)

	@classmethod
	def storeToByteArray(cls, array, operator, value):
		width, byteOff, bitOff =\
			operator.width, operator.offset, operator.bitOffset
		try:
			if width == 1:
				array[byteOff].setBitValue(bitOff, value)
			elif width == 8:
				assert(bitOff == 0)
				array[byteOff].set(value)
			elif width == 16:
				assert(bitOff == 0)
				array[byteOff].set(value >> 8)
				array[byteOff + 1].set(value)
			elif width == 32:
				assert(bitOff == 0)
				array[byteOff].set(value >> 24)
				array[byteOff + 1].set(value >> 16)
				array[byteOff + 2].set(value >> 8)
				array[byteOff + 3].set(value)
			else:
				assert(0)
		except IndexError as e:
			raise AwlSimError("store: Operator offset out of range")
