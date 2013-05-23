# -*- coding: utf-8 -*-
#
# AWL simulator - counters
# Copyright 2012-2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2.
#

from awlsim.util import *


class Counter(object):
	def __init__(self, cpu, index):
		self.cpu = cpu
		self.index = index
		self.prevVKE_FR = 0
		self.prevVKE_S = 0
		self.prevVKE_ZV = 0
		self.prevVKE_ZR = 0
		self.counter = 0

	def get(self):
		return 1 if self.counter else 0

	def getValueBin(self):
		return self.counter

	def getValueBCD(self):
		bcd = self.counter % 10
		bcd |= ((self.counter // 10) % 10) << 4
		bcd |= ((self.counter // 100) % 10) << 8
		return bcd

	def set(self, VKE):
		if (~self.prevVKE_S & VKE) & 1:
			counterBCD = self.cpu.accu1.get()
			a, b, c = (counterBCD & 0xF),\
				  ((counterBCD >> 4) & 0xF),\
				  ((counterBCD >> 8) & 0xF)
			if counterBCD > 0x999 or a > 9 or b > 9 or c > 9:
				raise AwlSimError("Invalid BCD value")
			self.counter = a + (b * 10) + (c * 100)
		self.prevVKE_S = VKE

	def reset(self):
		self.counter = 0

	def run_FR(self, VKE):
		if (~self.prevVKE_FR & VKE) & 1:
			self.prevVKE_S = 0
			self.prevVKE_ZV = 0
			self.prevVKE_ZR = 0
		self.prevVKE_FR = VKE

	def run_ZV(self, VKE):
		if (~self.prevVKE_ZV & VKE) & 1:
			if self.counter < 999:
				self.counter += 1
		self.prevVKE_ZV = VKE

	def run_ZR(self, VKE):
		if (~self.prevVKE_ZR & VKE) & 1:
			if self.counter > 0:
				self.counter -= 1
		self.prevVKE_ZR = VKE