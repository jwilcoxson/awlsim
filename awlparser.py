# -*- coding: utf-8 -*-
#
# AWL parser
# Copyright 2012-2013 Michael Buesch <m@bues.ch>
#
# Licensed under the terms of the GNU General Public License version 2.
#

import sys
import re

from util import *


class RawAwlInsn(object):
	def __init__(self, block):
		self.block = block
		self.lineNr = 0
		self.label = None
		self.name = None
		self.ops = []

	__labelRe = re.compile(r'^[_a-zA-Z][_0-9a-zA-Z]{0,3}$')

	@classmethod
	def isValidLabel(cls, labelString):
		# Checks if string is a valid label or
		# label reference (without colons).
		return bool(cls.__labelRe.match(labelString))

	def __repr__(self):
		ret = []
		if self.hasLabel():
			ret.append(self.getLabel() + ':\t')
		else:
			ret.append('\t')
		ret.append(self.getName())
		ret.extend(self.getOperators())
		return "\t".join(ret)

	def setLineNr(self, newLineNr):
		self.lineNr = newLineNr

	def getLineNr(self):
		return self.lineNr

	def setLabel(self, newLabel):
		self.label = newLabel

	def getLabel(self):
		return self.label

	def hasLabel(self):
		return bool(self.getLabel())

	def setName(self, newName):
		self.name = newName

	def getName(self):
		return self.name

	def setOperators(self, newOperators):
		self.ops = newOperators

	def getOperators(self):
		return self.ops

	def hasOperators(self):
		return bool(self.getOperators())

class RawAwlBlock(object):
	def __init__(self, tree, index):
		self.tree = tree
		self.index = index

	def hasLabel(self, string):
		return False

class RawAwlCodeBlock(RawAwlBlock):
	def __init__(self, tree, index):
		RawAwlBlock.__init__(self, tree, index)
		self.insns = []
		self.vars_in = []
		self.vars_out = []
		self.vars_inout = []
		self.vars_static = []
		self.vars_temp = []

	def hasLabel(self, string):
		if RawAwlInsn.isValidLabel(string):
			for insn in self.insns:
				if insn.getLabel() == string:
					return True
		return False

class RawAwlDataField(object):
	def __init__(self, name, valueTokens, typeTokens):
		self.name = name
		self.valueTokens = valueTokens
		self.typeTokens = typeTokens

class RawAwlDB(RawAwlBlock):
	def __init__(self, tree, index):
		RawAwlBlock.__init__(self, tree, index)
		self.fields = []
		self.fb = None

	def isInstanceDB(self):
		return bool(self.fb)

	def getByName(self, name):
		for field in self.fields:
			if field.name == name:
				return field
		return None

class RawAwlOB(RawAwlCodeBlock):
	def __init__(self, tree, index):
		RawAwlCodeBlock.__init__(self, tree, index)

class RawAwlFB(RawAwlCodeBlock):
	def __init__(self, tree, index):
		RawAwlCodeBlock.__init__(self, tree, index)

class RawAwlFC(RawAwlCodeBlock):
	def __init__(self, tree, index):
		RawAwlCodeBlock.__init__(self, tree, index)

class AwlParseTree(object):
	def __init__(self):
		self.dbs = {}
		self.fbs = {}
		self.fcs = {}
		self.obs = {}

		self.curBlock = None

class AwlParser(object):
	STATE_GLOBAL			= 0
	STATE_IN_DB_HDR			= 100
	STATE_IN_DB_HDR_STRUCT		= 101
	STATE_IN_DB			= 102
	STATE_IN_FB_HDR			= 200
	STATE_IN_FB_HDR_VAR		= 201
	STATE_IN_FB_HDR_VARIN		= 202
	STATE_IN_FB_HDR_VAROUT		= 203
	STATE_IN_FB_HDR_VARINOUT	= 204
	STATE_IN_FB_HDR_VARTEMP		= 205
	STATE_IN_FB			= 206
	STATE_IN_FC_HDR			= 300
	STATE_IN_FC_HDR_VARIN		= 301
	STATE_IN_FC_HDR_VAROUT		= 302
	STATE_IN_FC_HDR_VARINOUT	= 303
	STATE_IN_FC_HDR_VARTEMP		= 304
	STATE_IN_FC			= 305
	STATE_IN_OB_HDR			= 400
	STATE_IN_OB_HDR_VARTEMP		= 401
	STATE_IN_OB			= 402

	class TokenizerState(object):
		def __init__(self):
			self.reset()

		def reset(self):
			self.tokens = []
			self.curToken = ""
			self.inComment = False
			self.inQuote = False
			self.inParens = False

		def tokenEnd(self):
			self.curToken = self.curToken.strip()
			if self.curToken:
				self.tokens.append(self.curToken)
			self.curToken = ""

	def __init__(self):
		self.reset()

	def reset(self):
		self.state = self.STATE_GLOBAL
		self.tree = AwlParseTree()

	def __setState(self, newState):
		self.state = newState

	def __inAnyHeader(self):
		if self.flatLayout:
			return False
		return self.state in (self.STATE_IN_DB_HDR,
				      self.STATE_IN_DB_HDR_STRUCT,
				      self.STATE_IN_FB_HDR,
				      self.STATE_IN_FC_HDR,
				      self.STATE_IN_OB_HDR)

	def __inAnyHeaderOrGlobal(self):
		if self.flatLayout:
			return False
		return self.__inAnyHeader() or\
		       self.state == self.STATE_GLOBAL

	def __tokenize(self, data):
		self.reset()
		self.lineNr = 0

		t = self.TokenizerState()
		for i, c in enumerate(data):
			if c == '\n':
				self.lineNr += 1
			if t.inComment:
				# Consume all comment chars up to \n
				if c == '\n':
					t.inComment = False
				continue
			if c == '"':
				# Quote begin or end
				t.inQuote = not t.inQuote
			if t.inQuote:
				t.curToken += c
				continue
			if c == ';':
				# Semicolon ends statement.
				self.__parseTokens(t)
				continue
			if c == '/' and i + 1 < len(data) and\
			   data[i + 1] == '/':
				# A //comment ends the statement.
				self.__parseTokens(t)
				t.inComment = True
				continue
			if t.tokens:
				if c == '(':
					# Parenthesis begin
					t.inParens = True
					t.curToken += c
					t.tokenEnd()
					continue
				if t.inParens and c == ')':
					# Parenthesis end
					t.inParens = False
					t.tokenEnd()
					t.tokens.append(c)
					continue
				if (self.__inAnyHeaderOrGlobal() and\
				    c in ('=', ':', '[', ']', '..')) or\
				   (c == ','):
					# Handle non-space token separators.
					t.tokenEnd()
					t.tokens.append(c)
					continue
			if c == '\n' and not t.inParens:
				self.__parseTokens(t)
				continue
			if c.isspace():
				t.tokenEnd()
			else:
				t.curToken += c
		if t.inQuote:
			raise AwlParserError("Unterminated quote")
		if t.inParens:
			raise AwlParserError("Unterminated parenthesis pair")
		if t.tokens:
			self.__parseTokens(t)

	def __parseTokens(self, tokenizerState):
		tokenizerState.tokenEnd()
		tokens = tokenizerState.tokens
		if not tokens:
			return

		if self.state == self.STATE_GLOBAL or\
		   self.flatLayout:
			self.__parseTokens_global(tokens)
		elif self.state == self.STATE_IN_DB_HDR:
			self.__parseTokens_db_hdr(tokens)
		elif self.state == self.STATE_IN_DB_HDR_STRUCT:
			self.__parseTokens_db_hdr_struct(tokens)
		elif self.state == self.STATE_IN_DB:
			self.__parseTokens_db(tokens)
		elif self.state == self.STATE_IN_FB_HDR:
			self.__parseTokens_fb_hdr(tokens)
		elif self.state == self.STATE_IN_FB_HDR_VAR:
			self.__parseTokens_fb_hdr_var(tokens)
		elif self.state == self.STATE_IN_FB_HDR_VARIN:
			self.__parseTokens_fb_hdr_varin(tokens)
		elif self.state == self.STATE_IN_FB_HDR_VAROUT:
			self.__parseTokens_fb_hdr_varout(tokens)
		elif self.state == self.STATE_IN_FB_HDR_VARINOUT:
			self.__parseTokens_fb_hdr_varinout(tokens)
		elif self.state == self.STATE_IN_FB_HDR_VARTEMP:
			self.__parseTokens_fb_hdr_vartemp(tokens)
		elif self.state == self.STATE_IN_FB:
			self.__parseTokens_fb(tokens)
		elif self.state == self.STATE_IN_FC_HDR:
			self.__parseTokens_fc_hdr(tokens)
		elif self.state == self.STATE_IN_FC_HDR_VARIN:
			self.__parseTokens_fc_hdr_varin(tokens)
		elif self.state == self.STATE_IN_FC_HDR_VAROUT:
			self.__parseTokens_fc_hdr_varout(tokens)
		elif self.state == self.STATE_IN_FC_HDR_VARINOUT:
			self.__parseTokens_fc_hdr_varinout(tokens)
		elif self.state == self.STATE_IN_FC_HDR_VARTEMP:
			self.__parseTokens_fc_hdr_vartemp(tokens)
		elif self.state == self.STATE_IN_FC:
			self.__parseTokens_fc(tokens)
		elif self.state == self.STATE_IN_OB_HDR:
			self.__parseTokens_ob_hdr(tokens)
		elif self.state == self.STATE_IN_OB_HDR_VARTEMP:
			self.__parseTokens_ob_hdr_vartemp(tokens)
		elif self.state == self.STATE_IN_OB:
			self.__parseTokens_ob(tokens)
		else:
			assert(0)
		tokenizerState.reset()

	def __parseTokens_global(self, tokens):
		if self.flatLayout:
			if not self.tree.obs:
				self.tree.obs[1] = RawAwlOB(self.tree, 1)
			if not self.tree.curBlock:
				self.tree.curBlock = self.tree.obs[1]
			insn = self.__parseInstruction(tokens)
			self.tree.obs[1].insns.append(insn)
			return

		try:
			if tokens[0].upper() == "DATA_BLOCK":
				self.__setState(self.STATE_IN_DB_HDR)
				if tokens[1].upper() != "DB":
					raise AwlParserError("Invalid DB name")
				try:
					dbNumber = int(tokens[2], 10)
				except ValueError:
					raise AwlParserError("Invalid DB number")
				self.tree.curBlock = RawAwlDB(self.tree, dbNumber)
				self.tree.dbs[dbNumber] = self.tree.curBlock
				return
			if tokens[0].upper() == "FUNCTION_BLOCK":
				self.__setState(self.STATE_IN_FB_HDR)
				if tokens[1].upper() != "FB":
					raise AwlParserError("Invalid FB name")
				try:
					fbNumber = int(tokens[2], 10)
				except ValueError:
					raise AwlParserError("Invalid FB number")
				self.tree.curBlock = RawAwlFB(self.tree, fbNumber)
				self.tree.fbs[fbNumber] = self.tree.curBlock
				return
			if tokens[0].upper() == "FUNCTION":
				self.__setState(self.STATE_IN_FC_HDR)
				if tokens[1].upper() != "FC":
					raise AwlParserError("Invalid FC name")
				try:
					fcNumber = int(tokens[2], 10)
				except ValueError:
					raise AwlParserError("Invalid FC number")
				self.tree.curBlock = RawAwlFC(self.tree, fcNumber)
				self.tree.fcs[fcNumber] = self.tree.curBlock
				return
			if tokens[0].upper() == "ORGANIZATION_BLOCK":
				self.__setState(self.STATE_IN_OB_HDR)
				if tokens[1].upper() != "OB":
					raise AwlParserError("Invalid OB name")
				try:
					obNumber = int(tokens[2], 10)
				except ValueError:
					raise AwlParserError("Invalid OB number")
				self.tree.curBlock = RawAwlOB(self.tree, obNumber)
				self.tree.obs[obNumber] = self.tree.curBlock
				return
		except IndexError as e:
			raise AwlParserError("Missing token")
		except ValueError as e:
			raise AwlParserError("Invalid value")
		raise AwlParserError("Unknown statement")

	def __parseInstruction(self, tokens):
		insn = RawAwlInsn(self.tree.curBlock)
		insn.setLineNr(self.lineNr)
		if tokens[0].endswith(":"):
			# First token is a label
			if len(tokens) <= 1:
				raise AwlParserError("Invalid standalone label")
			label = tokens[0][0:-1]
			if not label or not RawAwlInsn.isValidLabel(label):
				raise AwlParserError("Invalid label")
			insn.setLabel(label)
			tokens = tokens[1:]
		if not tokens:
			raise AwlParserError("No instruction name")
		insn.setName(tokens[0])
		tokens = tokens[1:]
		if tokens:
			# Operators to insn are specified
			insn.setOperators(tokens)
		return insn

	def __parseTokens_db_hdr(self, tokens):
		if tokens[0].upper() == "BEGIN":
			self.__setState(self.STATE_IN_DB)
		elif tokens[0].upper() == "TITLE":
			pass#TODO
		elif tokens[0].upper() == "VERSION":
			pass#TODO
		elif tokens[0].upper() == "STRUCT":
			self.__setState(self.STATE_IN_DB_HDR_STRUCT)
		elif tokens[0].upper() in ("FB", "SFB"):
			try:
				if len(tokens) != 2:
					raise ValueError
				fbName = tokens[0].upper()
				fbNumber = int(tokens[1], 10)
			except ValueError:
				raise AwlParserError("Invalid FB/SFB binding")
			self.tree.curBlock.fb = (fbName, fbNumber)
		else:
			raise AwlParserError("In DB header: Unknown tokens")

	def __parse_var_generic(self, tokens, varList,
				endToken,
				mayHaveInitval=True):
		if tokens[0].upper() == endToken:
			return False
		colonIdx = listIndex(tokens, ":")
		assignIdx = listIndex(tokens, ":=")
		if mayHaveInitval and colonIdx == 1 and assignIdx > colonIdx + 1:
			name = tokens[0]
			type = tokens[colonIdx+1:assignIdx]
			val = tokens[assignIdx+1:]
			field = RawAwlDataField(name, val, type)
			varList.append(field)
		elif colonIdx == 1:
			name = tokens[0]
			type = tokens[colonIdx+1:]
			field = RawAwlDataField(name, None, type)
			varList.append(field)
		else:
			raise AwlParserError("In variable section: Unknown tokens")
		return True

	def __parseTokens_db_hdr_struct(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.fields,
				endToken = "END_STRUCT",
				mayHaveInitval = False):
			self.__setState(self.STATE_IN_DB_HDR)

	def __parseTokens_db(self, tokens):
		if tokens[0].upper() == "END_DATA_BLOCK":
			self.__setState(self.STATE_GLOBAL)
			return
		if len(tokens) >= 3 and tokens[1] == ":=":
			name, valueTokens = tokens[0], tokens[2:]
			db = self.tree.curBlock
			field = db.getByName(name)
			if field:
				field.valueTokens = valueTokens
			else:
				field = RawAwlDataField(name, valueTokens,
							None)
				db.fields.append(field)
		else:
			raise AwlParserError("In DB: Unknown tokens")

	def __parseTokens_fb_hdr(self, tokens):
		if tokens[0].upper() == "BEGIN":
			self.__setState(self.STATE_IN_FB)
		elif tokens[0].upper() == "TITLE":
			pass#TODO
		elif tokens[0].upper() == "VERSION":
			pass#TODO
		elif tokens[0].upper() == "VAR":
			self.__setState(self.STATE_IN_FB_HDR_VAR)
		elif tokens[0].upper() == "VAR_INPUT":
			self.__setState(self.STATE_IN_FB_HDR_VARIN)
		elif tokens[0].upper() == "VAR_OUTPUT":
			self.__setState(self.STATE_IN_FB_HDR_VAROUT)
		elif tokens[0].upper() == "VAR_IN_OUT":
			self.__setState(self.STATE_IN_FB_HDR_VARINOUT)
		elif tokens[0].upper() == "VAR_TEMP":
			self.__setState(self.STATE_IN_FB_HDR_VARTEMP)
		else:
			raise AwlParserError("In FB: Unknown token")

	def __parseTokens_fb_hdr_var(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_static,
				endToken = "END_VAR"):
			self.__setState(self.STATE_IN_FB_HDR)

	def __parseTokens_fb_hdr_varin(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_in,
				endToken = "END_VAR"):
			self.__setState(self.STATE_IN_FB_HDR)

	def __parseTokens_fb_hdr_varout(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_out,
				endToken = "END_VAR"):
			self.__setState(self.STATE_IN_FB_HDR)

	def __parseTokens_fb_hdr_varinout(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_inout,
				endToken = "END_VAR"):
			self.__setState(self.STATE_IN_FB_HDR)

	def __parseTokens_fb_hdr_vartemp(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_temp,
				endToken = "END_VAR",
				mayHaveInitval = False):
			self.__setState(self.STATE_IN_FB_HDR)

	def __parseTokens_fb(self, tokens):
		if tokens[0].upper() == "END_FUNCTION_BLOCK":
			self.__setState(self.STATE_GLOBAL)
			return
		if tokens[0].upper() == "NETWORK" or\
		   tokens[0].upper() == "TITLE":
			return # ignore
		insn = self.__parseInstruction(tokens)
		self.tree.curBlock.insns.append(insn)

	def __parseTokens_fc_hdr(self, tokens):
		if tokens[0].upper() == "BEGIN":
			self.__setState(self.STATE_IN_FC)
		elif tokens[0].upper() == "TITLE":
			pass#TODO
		elif tokens[0].upper() == "VAR_INPUT":
			self.__setState(self.STATE_IN_FC_HDR_VARIN)
		elif tokens[0].upper() == "VAR_OUTPUT":
			self.__setState(self.STATE_IN_FC_HDR_VAROUT)
		elif tokens[0].upper() == "VAR_IN_OUT":
			self.__setState(self.STATE_IN_FC_HDR_VARINOUT)
		elif tokens[0].upper() == "VAR_TEMP":
			self.__setState(self.STATE_IN_FC_HDR_VARTEMP)
		else:
			raise AwlParserError("In FC header: Unknown token")

	def __parseTokens_fc_hdr_varin(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_in,
				endToken = "END_VAR",
				mayHaveInitval=False):
			self.__setState(self.STATE_IN_FC_HDR)

	def __parseTokens_fc_hdr_varout(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_out,
				endToken = "END_VAR",
				mayHaveInitval=False):
			self.__setState(self.STATE_IN_FC_HDR)

	def __parseTokens_fc_hdr_varinout(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_inout,
				endToken = "END_VAR",
				mayHaveInitval=False):
			self.__setState(self.STATE_IN_FC_HDR)

	def __parseTokens_fc_hdr_vartemp(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_temp,
				endToken = "END_VAR",
				mayHaveInitval=False):
			self.__setState(self.STATE_IN_FC_HDR)

	def __parseTokens_fc(self, tokens):
		if tokens[0].upper() == "END_FUNCTION":
			self.__setState(self.STATE_GLOBAL)
			return
		if tokens[0].upper() == "NETWORK" or\
		   tokens[0].upper() == "TITLE":
			return # ignore
		insn = self.__parseInstruction(tokens)
		self.tree.curBlock.insns.append(insn)

	def __parseTokens_ob_hdr(self, tokens):
		if tokens[0].upper() == "BEGIN":
			self.__setState(self.STATE_IN_OB)
		elif tokens[0].upper() == "VAR_TEMP":
			self.__setState(self.STATE_IN_OB_HDR_VARTEMP)
		elif tokens[0].upper() == "TITLE":
			pass#TODO
		elif tokens[0].upper() == "VERSION":
			pass#TODO
		else:
			raise AwlParserError("In OB header: Unknown token")

	def __parseTokens_ob_hdr_vartemp(self, tokens):
		if not self.__parse_var_generic(tokens,
				varList = self.tree.curBlock.vars_temp,
				endToken = "END_VAR",
				mayHaveInitval=False):
			self.__setState(self.STATE_IN_OB_HDR)

	def __parseTokens_ob(self, tokens):
		if tokens[0].upper() == "END_ORGANIZATION_BLOCK":
			self.__setState(self.STATE_GLOBAL)
			return
		if tokens[0].upper() == "NETWORK" or\
		   tokens[0].upper() == "TITLE":
			return # ignore
		insn = self.__parseInstruction(tokens)
		self.tree.curBlock.insns.append(insn)

	def parseFile(self, filename):
		self.parseData(awlFileRead(filename))

	def parseData(self, data):
		self.flatLayout = not re.match(r'.*^\s*ORGANIZATION_BLOCK\s+.*',
					       data, re.DOTALL | re.MULTILINE)
		ex = None
		try:
			self.__tokenize(data)
		except AwlParserError as e:
			ex = e
		if ex:
			raise AwlParserError("Parser ERROR at AWL line %d:\n%s" %\
				(self.lineNr, str(ex)))

	def getParseTree(self):
		return self.tree
