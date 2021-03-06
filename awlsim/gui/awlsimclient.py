# -*- coding: utf-8 -*-
#
# AWL simulator - GUI simulator client access
#
# Copyright 2014-2016 Michael Buesch <m@bues.ch>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

from awlsim.gui.util import *
from awlsim.gui.blocktreewidget import *

from awlsim.coreclient.client import *


class OnlineData(QObject):
	"""Container for data retrieved from the server.
	"""

	# Symbol table signal.
	# Contains only SymTabSources that can be parsed without errors.
	# Parameter: a list of tuples such as:
	#		[ (SymTabSource, SymbolTable), ... ]
	symTabsUpdate = Signal(list)

	def __init__(self, client):
		QObject.__init__(self)
		self.__client = client

		self.reset()

	def reset(self):
		self.__symTabCache = {}

	def __getSymTabByIdent(self, identHash):
		try:
			symTabSrc = self.__client.getSymTabSource(identHash)
			if symTabSrc:
				return SymTabParser.parseSource(symTabSrc)
		except AwlSimError as e:
			return None
		return None

	def handle_IDENTS(self, msg):
		# Parse the symbol table sources
		symTabCache = {}
		symTabList = []
		for symTabSrc in msg.symTabSources:
			identHash = symTabSrc.identHash
			symTab = self.__symTabCache.get(identHash, None)
			if symTab is None:
				symTab = self.__getSymTabByIdent(identHash)
			symTabCache[identHash] = symTab
			if symTab is not None:
				symTabList.append((symTabSrc, symTab))
		self.__symTabCache = symTabCache
		self.symTabsUpdate.emit(symTabList)

class GuiAwlSimClient(AwlSimClient, QObject):
	# CPU exception signal.
	haveException = Signal(AwlSimError)

	# CPU-dump signal.
	# Parameter: The dump text.
	haveCpuDump = Signal(str)

	# Instruction dump signal.
	# Parameter: AwlSimMessage_INSNSTATE instance.
	haveInsnDump = Signal(AwlSimMessage_INSNSTATE)

	# Memory update signal.
	# Parameter: A list of MemoryArea instances.
	haveMemoryUpdate = Signal(list)

	# Ident hashes signal.
	# Parameter: AwlSimMessage_IDENTS instance.
	haveIdentsMsg = Signal(AwlSimMessage_IDENTS)

	# Block info signal.
	# Parameter: AwlSimMessage_BLOCKINFO instance.
	haveBlockInfoMsg = Signal(AwlSimMessage_BLOCKINFO)

	# The client mode
	EnumGen.start
	MODE_OFFLINE	= EnumGen.item # Not connected
	MODE_ONLINE	= EnumGen.item # Connected to an existing core
	MODE_FORK	= EnumGen.item # Online to a newly forked core
	EnumGen.end

	def __init__(self):
		QObject.__init__(self)
		AwlSimClient.__init__(self)

		self.onlineData = OnlineData(self)

		self.__setMode(self.MODE_OFFLINE)

		self.__blockTreeModelManager = None
		self.__blockTreeModel = None

	# Override sleep handler
	def sleep(self, seconds):
		end = monotonic_time() + seconds
		eventFlags = QEventLoop.AllEvents |\
			     QEventLoop.ExcludeUserInputEvents
		while monotonic_time() < end:
			QApplication.processEvents(eventFlags, 10)
			QThread.msleep(10)

	# Override exception handler
	def handle_EXCEPTION(self, exception):
		# Emit the exception signal.
		self.haveException.emit(exception)
		# Call the default exception handler.
		AwlSimClient.handle_EXCEPTION(self, exception)

	# Override cpudump handler
	def handle_CPUDUMP(self, dumpText):
		self.haveCpuDump.emit(dumpText)

	# Override memory update handler
	def handle_MEMORY(self, memAreas):
		self.haveMemoryUpdate.emit(memAreas)

	# Override instruction state handler
	def handle_INSNSTATE(self, msg):
		self.haveInsnDump.emit(msg)

	# Override ident hashes handler
	def handle_IDENTS(self, msg):
		self.onlineData.handle_IDENTS(msg)
		self.haveIdentsMsg.emit(msg)

	# Override block info handler
	def handle_BLOCKINFO(self, msg):
		self.haveBlockInfoMsg.emit(msg)

	def getMode(self):
		return self.__mode

	def __setMode(self, mode, host = None, port = None):
		self.__mode = mode
		self.__host = host
		self.__port = port
		self.onlineData.reset()

	def shutdown(self):
		# Shutdown the client.
		# If we are in FORK mode, this will also terminate
		# the forked core.
		# If we are in ONLINE mode, this will only
		# close the connection.
		AwlSimClient.shutdown(self)
		self.__setMode(self.MODE_OFFLINE)

	def setMode_OFFLINE(self):
		if self.__mode == self.MODE_OFFLINE:
			return
		if self.serverProcess:
			# Put the spawned core into STOP state.
			try:
				if not self.setRunState(False):
					raise RuntimeError
			except (AwlSimError, RuntimeError) as e:
				CALL_NOEX(self.killSpawnedServer)
		self.shutdownTransceiver()
		self.__setMode(self.MODE_OFFLINE)

	def setMode_ONLINE(self, host, port, timeout=3.0):
		if self.__mode == self.MODE_ONLINE:
			if self.__host == host and\
			   self.__port == port:
				# We are already up and running.
				return
		self.__serverExecutable = None
		self.__interpreterList = None
		self.shutdown()
		try:
			self.connectToServer(host = host,
					     port = port,
					     timeout = timeout)
		except AwlSimError as e:
			CALL_NOEX(self.shutdown)
			raise e
		self.__setMode(self.MODE_ONLINE, host = host, port = port)

	def setMode_FORK(self, portRange,
			 serverExecutable=None,
			 interpreterList=None):
		host = "localhost"
		if self.__mode == self.MODE_FORK:
			if self.__port in portRange and\
			   self.__serverExecutable == serverExecutable and\
			   self.__interpreterList == interpreterList:
				assert(self.__host == host)
				# We are already up and running.
				return
		try:
			if self.serverProcess:
				if self.serverProcessPort not in portRange or\
				   self.__serverExecutable != serverExecutable or\
				   self.__interpreterList != interpreterList:
					self.killSpawnedServer()
			if self.serverProcess:
				port = self.serverProcessPort
			else:
				for port in portRange:
					if not AwlSimServer.portIsUnused(host, port):
						continue
					# XXX: There is a race-window here. Another process might
					#      allocate the port that we just checked
					#      before our server is able to allocate it.
					if serverExecutable:
						self.spawnServer(serverExecutable = serverExecutable,
								 listenHost = host,
								 listenPort = port)
					else:
						self.spawnServer(interpreter = interpreterList,
								 listenHost = host,
								 listenPort = port)
					break
				else:
					raise AwlSimError("Did not find a free port to run the "
						"awlsim core server on.\nTried port %d to %d on '%s'." %\
						(portRange[0], portRange[-1], host))
			self.shutdownTransceiver()
			self.connectToServer(host = host, port = port)
		except AwlSimError as e:
			CALL_NOEX(self.shutdown)
			raise e
		self.__setMode(self.MODE_FORK, host = host, port = port)
		self.__serverExecutable = serverExecutable
		self.__interpreterList = interpreterList

	def getBlockTreeModelRef(self):
		"""Get an ObjRef to the BlockTreeModel object."""

		if not self.__blockTreeModelManager:
			# Create a new block tree model
			self.__blockTreeModelManager = ObjRefManager("BlockTreeModel",
				allDestroyedCallback = self.__allBlockTreeModelRefsDestroyed)
			self.__blockTreeModel = BlockTreeModel(self)
			# Connect block tree message handlers
			self.haveIdentsMsg.connect(self.__blockTreeModel.handle_IDENTS)
			self.haveBlockInfoMsg.connect(self.__blockTreeModel.handle_BLOCKINFO)
			self.onlineData.symTabsUpdate.connect(self.__blockTreeModel.handle_symTabInfo)

		return ObjRef.make("BlockTreeModel", self.__blockTreeModelManager,
				   self.__blockTreeModel)

	def blockTreeModelActive(self):
		"""Returns True, if there is at least one active ref to
		the BlockTreeModel."""

		if self.__blockTreeModelManager:
			return self.__blockTreeModelManager.hasReferences
		return False

	def __allBlockTreeModelRefsDestroyed(self):
		# The last block tree model reference died. Destroy it.
		self.__blockTreeModelManager = None
		self.__blockTreeModel = None
