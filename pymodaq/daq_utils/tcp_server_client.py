# -*- coding: utf-8 -*-
"""
Created on Fri Aug 30 12:21:56 2019

@author: Weber
"""
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread
from PyQt5 import QtWidgets
import socket
import select
import numpy as np
from pymodaq.daq_utils.daq_utils import getLineInfo, ThreadCommand
from pymodaq.daq_utils.tcpip_utils import Socket
#check_received_length, send_scalar, send_string, send_list, get_scalar,\
#    get_int, get_string, send_array, get_list
from pyqtgraph.parametertree import Parameter, ParameterTree
import pyqtgraph.parametertree.parameterTypes as pTypes
import pymodaq.daq_utils.custom_parameter_tree as custom_tree
from collections import OrderedDict

tcp_parameters = [{'title': 'Port:', 'name': 'port_id', 'type': 'int', 'value': 6341, 'default': 6341},
                  {'title': 'IP:', 'name': 'socket_ip', 'type': 'str', 'value': '10.47.0.39',
                   'default': '10.47.0.39'},
                  {'title': 'Settings PyMoDAQ Client:', 'name': 'settings_client', 'type': 'group', 'children': []},
                  {'title': 'Infos Client:', 'name': 'infos', 'type': 'group', 'children': []},
                  {'title': 'Connected clients:', 'name': 'conn_clients', 'type': 'table',
                   'value': dict(), 'header': ['Type', 'adress']}, ]
# %%

class TCPClient(QObject):
    """
    PyQt5 object initializing a TCP socket client. Can be used by any module but is a builtin functionnality of all
    actuators and detectors of PyMoDAQ

    The module should init TCPClient, move it in a thread and communicate with it using a custom signal connected to
    TCPClient.queue_command slot. The module should also connect TCPClient.cmd_signal to one of its methods inorder to
    get info/data back from the client

    The client itself communicate with a TCP server, it is best to use a server object subclassing the TCPServer
    class defined within this python module

    """
    cmd_signal = pyqtSignal(ThreadCommand) #signal to connect with a module slot in order to start communication back
    params = []

    def __init__(self, ipaddress="192.168.1.62", port=6341, params_state=None, client_type="GRABBER"):
        """Create a socket client particularly fit to be used with PyMoDAQ's TCPServer

        Parameters
        ----------
        ipaddress: (str) the IP address of the server
        port: (int) the port where to communicate with the server
        params_state: (dict) state of the Parameter settings of the module instantiating this client and wishing to
                            export its settings to the server. Obtained from param.saveState() where param is an
                            instance of Parameter object, see pyqtgraph.parametertree::Parameter
        client_type: (str) should be one of the accepted client_type by the TCPServer instance (within pymodaq it is
                            either 'GRABBER' or 'ACTUATOR'
        """
        super().__init__()

        self.ipaddress = ipaddress
        self.port = port
        self._socket = None
        self.settings = Parameter.create(name='Settings', type='group', children=self.params)
        if params_state is not None:
            if isinstance(params_state, dict):
                self.settings.restoreState(params_state)
            elif isinstance(params_state, Parameter):
                self.settings.restoreState(params_state.saveState())

        self.client_type = client_type #"GRABBER" or "ACTUATOR"

    @property
    def socket(self):
        return self._socket

    @socket.setter
    def socket(self, sock):
        self._socket = sock

    def send_data(self, data_list):
        # first send 'Done' and then send the length of the list
        self.socket.send_string('Done')
        self.socket.send_list(data_list)

    def send_infos_xml(self, infos):
        self.socket.send_string('Infos')
        self.socket.send_string(infos)

    def send_info_scalar(self, info_to_display, value_as_string):
        self.socket.send_string('Info') #the command
        if not isinstance(info_to_display, str):
            info_to_display = str(info_to_display)
        self.socket.send_string(info_to_display) #the actual info to display as a string
        if not isinstance(value_as_string, str):
            value_as_string = str(value_as_string)
        self.socket.send_string(value_as_string)

    @pyqtSlot(ThreadCommand)
    def queue_command(self, command=ThreadCommand()):
        """
        when this TCPClient object is within a thread, the corresponding module communicate with it with signal and slots
        from module to client: module_signal to queue_command slot
        from client to module: self.cmd_signal to a module slot
        """
        if command.command == "ini_connection":
            status = self.init_connection()

        elif command.command == "quit":
            try:
                self.socket.close()
            except Exception as e:
                pass
            finally:
                self.cmd_signal.emit(ThreadCommand('disconnected'))

        elif command.command == 'update_connection':
            self.ipaddress = command.attributes['ipaddress']
            self.port = command.attributes['port']

        elif command.command == 'data_ready':
            self.data_ready(command.attributes)

        elif command.command == 'send_info':
            path = command.attributes['path']
            param = command.attributes['param']

            self.socket.send_string('Info_xml')
            self.socket.send_list(path)

            # send value
            data = custom_tree.parameter_to_xml_string(param)
            self.socket.send_string(data)

        elif command.command == 'position_is':
            self.socket.send_string('position_is')
            self.socket.send_scalar(command.attributes[0])

        elif command.command == 'move_done':
            self.socket.send_string('move_done')
            self.socket.send_scalar(command.attributes[0])

        elif command.command == 'x_axis':
            self.socket.send_string('x_axis')
            x_axis = dict(label='', units='')
            if isinstance(command.attributes[0], np.ndarray):
                x_axis['data'] = command.attributes[0]
            elif isinstance(command.attributes[0], dict):
                x_axis.update(command.attributes[0].copy())

            self.socket.send_array(x_axis['data'])
            self.socket.send_string(x_axis['label'])
            self.socket.send_string(x_axis['units'])

        elif command.command == 'y_axis':
            self.socket.send_string('y_axis')
            y_axis = dict(label='', units='')
            if isinstance(command.attributes[0], np.ndarray):
                y_axis['data'] = command.attributes[0]
            elif isinstance(command.attributes[0], dict):
                y_axis.update(command.attributes[0].copy())

            self.socket.send_array(y_axis['data'])
            self.socket.send_string(y_axis['label'])
            self.socket.send_string(y_axis['units'])


    def init_connection(self):
        # %%
        try:
            # create an INET, STREAMing socket
            self.socket = Socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            # now connect to the web server on port 80 - the normal http port
            self.socket.connect((self.ipaddress, self.port))
            self.cmd_signal.emit(ThreadCommand('connected'))
            self.socket.send_string(self.client_type)

            self.send_infos_xml(custom_tree.parameter_to_xml_string(self.settings))
            self.cmd_signal.emit(ThreadCommand('get_axis'))
            # %%
            while True:

                try:
                    ready_to_read, ready_to_write, in_error = \
                        select.select([self.socket.socket], [self.socket.socket], [self.socket.socket], 0)

                    if len(ready_to_read) != 0:
                        message = self.socket.get_string()
                        # print(message)
                        self.get_data(message)

                    if len(in_error) != 0:
                        self.cmd_signal.emit(ThreadCommand('disconnected'))

                    QtWidgets.QApplication.processEvents()

                except Exception as e:
                    try:
                        self.cmd_signal.emit(ThreadCommand('Update_Status', [getLineInfo() + str(e), 'log']))
                        self.socket.send_string('Quit')
                        self.socket.close()
                    except:
                        pass
                    finally:
                        break

        except ConnectionRefusedError as e:
            self.cmd_signal.emit(ThreadCommand('disconnected'))
            self.cmd_signal.emit(ThreadCommand('Update_Status', [getLineInfo() + str(e), 'log']))

    # %%
    def get_data(self, message):
        """

        Parameters
        ----------
        message

        Returns
        -------

        """
        messg = ThreadCommand(message)

        if message == 'set_info':
            path = self.socket.get_list('string')
            param_xml = self.socket.get_string()
            messg.attributes = [path, param_xml]

        elif message == 'move_abs':
            position = self.socket.get_scalar()
            messg.attributes = [position]

        elif message == 'move_rel':
            position = self.socket.get_scalar()
            messg.attributes = [position]

        self.cmd_signal.emit(messg)

        # data = 100 * np.random.rand(100, 200)
        # self.data_ready([data.astype(np.int)])






    @pyqtSlot(list)
    def data_ready(self, datas):
        self.send_data(datas[0]['data'])  # datas from viewer 0 and get 'data' key (within the ordereddict list of datas


class TCPServer(QObject):
    """
    Abstract class to be used as inherited by DAQ_Viewer_TCP or DAQ_Move_TCP
    """
    def __init__(self, client_type='GRABBER'):
        QObject.__init__(self)

        self.connected_clients = []
        self.listening = True
        self.processing = False
        self.client_type = client_type

    def close_server(self):
        """
            close the current opened server.
            Update the settings tree consequently.

            See Also
            --------
            set_connected_clients_table, daq_utils.ThreadCommand
        """
        for sock_dict in self.connected_clients:
            try:
                sock_dict['socket'].close()
            except:
                pass
        self.connected_clients = []
        self.settings.child(('conn_clients')).setValue(self.set_connected_clients_table())

    def init_server(self):
        self.emit_status(ThreadCommand("Update_Status", [
            "Started new server for {:s}:{:d}".format(self.settings.child(('socket_ip')).value(),
                                                      self.settings.child(('port_id')).value()), 'log']))
        serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serversocket = Socket(serversocket)
        # bind the socket to a public host, and a well-known port
        try:
            self.serversocket.bind((self.settings.child(('socket_ip')).value(), self.settings.child(('port_id')).value()))
            #self.serversocket.bind((socket.gethostname(), self.settings.child(('port_id')).value()))
        except socket.error as msg:
            self.emit_status(ThreadCommand("Update_Status",
                                           ['Bind failed. Error Code : ' + str(msg.errno) + ' Message ' + msg.strerror,
                                            'log']))
            raise ConnectionError('Bind failed. Error Code : ' + str(msg.errno) + ' Message ' + msg.strerror)

        self.serversocket.listen(1)
        self.connected_clients.append(dict(socket=self.serversocket, type='server'))
        self.settings.child(('conn_clients')).setValue(self.set_connected_clients_table())

        self.timer = self.startTimer(100)  # Timer event fired every 100ms
        # self.listen_client()

    def timerEvent(self, event):
        """
            Called by set timers.
            If the process is free, start the listen_client function.

            =============== ==================== ==============================================
            **Parameters**   **Type**              **Description**

            *event*          QTimerEvent object    Containing id from timer issuing this event
            =============== ==================== ==============================================

            See Also
            --------
            listen_client
        """
        if not self.processing:
            self.listen_client()

    def set_connected_clients_table(self):
        """

        """
        con_clients = OrderedDict()
        for socket_dict in self.connected_clients:
            try:
                address = str(socket_dict['socket'].getsockname())
            except:
                address = ""
            con_clients[socket_dict['type']] = address
        return con_clients

    @pyqtSlot(list)
    def print_status(self, status):
        """
            Print the given status.

            =============== ============= ================================================
            **Parameters**    **Type**       **Description**
            *status*          string list    a string list representing the status socket
            =============== ============= ================================================
        """
        print(status)

    def select(self, rlist, wlist, xlist, timeout=0):
        read_sockets, write_sockets, error_sockets = select.select([sock.socket for sock in rlist],
                                                                   [sock.socket for sock in wlist],
                                                                   [sock.socket for sock in xlist],
                                                                   timeout)

        return ([Socket(sock) for sock in read_sockets], [Socket(sock) for sock in write_sockets],
                [Socket(sock) for sock in error_sockets])

    def remove_client(self, sock):
        sock_type = self.find_socket_type_within_connected_clients(sock)
        if sock_type is not None:
            self.connected_clients.remove(dict(socket=sock, type=sock_type))
            self.settings.child(('conn_clients')).setValue(self.set_connected_clients_table())
            try:
                sock.close()
            except:
                pass
            self.emit_status(ThreadCommand("Update_Status", ['Client ' + sock_type + ' disconnected', 'log']))

    def listen_client(self):
        """
            Server function.
            Used to listen incoming message from a client.
            Start a connection and :
            * if current socket corresponding to the serversocket attribute :

                * Read received command
                * Send the 'Update_Status' thread command if needed (log is not valid)

            * Else, in case of :

                * data received from client : process it reading commands from sock. Process the command or quit if asked.
                * client disconnected : remove from socket list


            See Also
            --------
            find_socket_type_within_connected_clients, set_connected_clients_table, daq_utils.ThreadCommand, read_commands, process_cmds, utility_classes.DAQ_Viewer_base.emit_status
        """
        try:
            self.processing = True
            # QtWidgets.QApplication.processEvents() #to let external commands in
            read_sockets, write_sockets, error_sockets = self.select(
                [client['socket'] for client in self.connected_clients], [],
                [client['socket'] for client in self.connected_clients],
                0)
            for sock in error_sockets:
                self.remove_client(sock)

            for sock in read_sockets:

                QThread.msleep(100)
                # New connection
                if sock == self.serversocket:
                    (client_socket, address) = self.serversocket.accept()
                    # client_socket.setblocking(False)

                    DAQ_type = self.read_commands(client_socket)
                    if DAQ_type not in self.socket_types:
                        self.emit_status(ThreadCommand("Update_Status", [DAQ_type + ' is not a valid type', 'log']))
                        client_socket.close()
                        break

                    self.connected_clients.append(dict(socket=client_socket, type=DAQ_type))
                    self.settings.child(('conn_clients')).setValue(self.set_connected_clients_table())
                    self.emit_status(ThreadCommand("Update_Status",
                                                   [DAQ_type + ' connected with ' + address[0] + ':' + str(address[1]),
                                                    'log']))
                    QtWidgets.QApplication.processEvents()
                # Some incoming message from a client
                else:
                    # Data received from client, process it
                    try:
                        message = self.read_commands(sock)
                        if message in ['Done', 'Info', 'Infos', 'Info_xml', 'position_is', 'move_done']:
                            self.process_cmds(message, command_sock=None)
                        elif message == 'Quit':
                            raise Exception("socket disconnect by user")
                        else:
                            self.process_cmds(message, command_sock=sock)

                    # client disconnected, so remove from socket list
                    except Exception as e:
                        self.remove_client(sock)

            self.processing = False

        except Exception as e:
            self.emit_status(ThreadCommand("Update_Status", [str(e), 'log']))

    def read_commands(self, sock):
        """
            Read the commands from the given socket.

            =============== ============
            **Parameters**    **Type**
            *sock*
            =============== ============

            Returns
            -------
            message_bytes
                The readed and decoded message

            See Also
            --------
            check_received_length
        """
        message = sock.get_string()
        return message

    def send_command(self, sock, command="move_at"):
        """
            Send one of the message contained in self.message_list toward a socket with identity socket_type.
            First send the length of the command with 4bytes.

            =============== =========== ==========================
            **Parameters**    **Type**    **Description**
            *sock*             ???        The current socket
            *command*         string      The command as a string
            =============== =========== ==========================

            See Also
            --------
            utility_classes.DAQ_Viewer_base.emit_status, daq_utils.ThreadCommand, message_to_bytes
        """
        if command not in self.message_list:
            self.emit_status(
                ThreadCommand("Update_Status", ['Command: ' + str(command) + ' not in the specified list', 'log']))
            return

        if sock is not None:
            sock.send_string(command)

    def find_socket_within_connected_clients(self, client_type):
        """
            Find a socket from a conneceted client with socket type corresponding.

            =============== =========== ================================
            **Parameters**    **Type**    **Description**
            *client_type*      string     The corresponding client type
            =============== =========== ================================

            Returns
            -------
            dictionnary
                the socket dictionnary
        """
        res = None
        for socket_dict in self.connected_clients:
            if socket_dict['type'] == client_type:
                res = socket_dict['socket']
        return res

    def find_socket_type_within_connected_clients(self, sock):
        """
            Find a socket type from a connected client with socket content corresponding.

            =============== =========== ===================================
            **Parameters**    **Type**   **Description**
            *sock*             ???       The socket content corresponding.
            =============== =========== ===================================

            Returns
            -------
            dictionnary
                the socket dictionnary
        """
        res = None
        for socket_dict in self.connected_clients:
            if socket_dict['socket'] == sock:
                res = socket_dict['type']
        return res

    def emit_status(self, status):
        print(status)


    def read_data(self, sock):
        pass

    def send_data(self, sock, data):
        pass

    def command_done(self, command_sock):
        pass

    def command_to_from_client(self, command):
        pass

    def process_cmds(self, command, command_sock=None):
        """
            Process the given command.
        """
        if command not in self.message_list:
            return

        if command == 'Done':  # means the given socket finished grabbing data and is ready to send them
            self.command_done(command_sock)


        elif command == "Infos":
            """replace entirely the client settings information onthe server widget
            should be done as the init of the client module"""
            try:
                sock = self.find_socket_within_connected_clients(self.client_type)
                if sock is not None:  # if client self.client_type is connected then send it the command
                    self.read_infos(sock)


            except Exception as e:
                self.emit_status(ThreadCommand("Update_Status", [str(e), 'log']))

        elif command == 'Info_xml':
            """update the state of one of the client settings on the server widget"""
            sock = self.find_socket_within_connected_clients(self.client_type)
            if sock is not None:
                path = sock.get_list()
                param_xml = sock.get_string()
                param_dict = custom_tree.XML_string_to_parameter(param_xml)[0]

                param_here = self.settings.child('settings_client', *path[1:])
                param_here.restoreState(param_dict)

        elif command == "Info":
            """
            add a custom info (as a string value) in the server widget settings. To be used if the client is not a 
            PyMoDAQ's module
            """
            try:
                sock = self.find_socket_within_connected_clients(self.client_type)
                if sock is not None:  # if client self.client_type is connected then send it the command
                    self.read_info(sock)
            except Exception as e:
                self.emit_status(ThreadCommand("Update_Status", [str(e), 'log']))

        else:
            self.command_to_from_client(command)






    def read_infos(self, sock):
        infos = sock.get_string()
        params = custom_tree.XML_string_to_parameter(infos)
        param_state = {'title': 'Infos Client:', 'name': 'settings_client', 'type': 'group', 'children': params}
        self.settings.child(('settings_client')).restoreState(param_state)

    def read_info(self, sock):
        """
        if the client is not from PyMoDAQ it can use this method to display some info into the server widget
        """
        try:

            ##first get the info type
            info = sock.get_string()
            data = sock.get_string()
            try:
                if info not in custom_tree.iter_children(self.settings.child(('infos')), []):
                    self.settings.child(('infos')).addChild({'name': info, 'type': 'str', 'value': data})
                else:
                    self.settings.child('infos', info).setValue(data)
            except Exception as e:
                self.emit_status(ThreadCommand('Update_Status', [str(e), 'log']))

        except Exception as e:
            data = ''

        return data


class MockServer(TCPServer):

    params = []

    def __init__(self, client_type='GRABBER'):
        super().__init__(client_type)

        self.settings = Parameter.create(name='settings', type='group', children=tcp_parameters)


if __name__ ==  '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)

    socket_types = ["GRABBER", "ACTUATOR"]
    server = MockServer()
    server.socket_types = socket_types
    server.settings.child(('socket_ip')).setValue('127.0.0.1')  # local host
    server.settings.child(('port_id')).setValue(6341)
    server.init_server()

    server_thread = QThread()
    server.moveToThread(server_thread)
    server_thread.start()



    QThread.msleep(1000)
    client = Socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    client.connect((server.settings.child(('socket_ip')).value(), server.settings.child(('port_id')).value()))
    # expect a valid client type:
    client.send_string("GRBER")


    QThread.msleep(1000)
    print(len(server.connected_clients))
    client.send_string("Quit")
    QThread.msleep(1000)
    print(len(server.connected_clients))
    while True:
        QThread.msleep(100)
    sys.exit(app.exec_())
